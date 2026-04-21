"""
Wulira API — FastAPI backend
-----------------------------
Wulira: "to hear / to listen" in Luganda 🇺🇬
wulira.app | Made in Kampala, Uganda
"""

import os
import re
import uuid
import time
import logging
import tempfile
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional, cast
from collections import defaultdict
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import PlainTextResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from lyrics import LyricsProcessor
from fingerprint import LyricsPipeline
from storage import create_store, JobStore
from auth import APIKeyManager, is_public_path
import translate as translator

load_dotenv()

# ── Configuration ──────────────────────────────────────
class Settings(BaseSettings):
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    env: str = "development"
    cors_origins: str = "http://localhost:8000"
    max_jobs_in_memory: int = 100
    job_timeout_seconds: int = 3600
    job_cleanup_interval_seconds: int = 300
    max_video_duration_seconds: int = 7200
    default_whisper_model: str = "base"
    allowed_whisper_models: str = "tiny,base,small,medium,large"
    log_level: str = "INFO"
    redis_url: str = ""

    class Config:
        env_file = ".env"

settings = Settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("wulira-api")

# ── Stores & Auth ──────────────────────────────────────
store: JobStore = create_store(settings.redis_url or None)
auth_mgr = APIKeyManager()

# ── Rate Limiter ───────────────────────────────────────
rate_limit_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 20

# ── WebSocket Manager ──────────────────────────────────
class ConnectionManager:
    def __init__(self) -> None:
        self.connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, ws: WebSocket, job_id: str) -> None:
        await ws.accept()
        self.connections[job_id].append(ws)

    def disconnect(self, ws: WebSocket, job_id: str) -> None:
        self.connections[job_id] = [c for c in self.connections[job_id] if c is not ws]

    async def broadcast(self, job_id: str, data: dict[str, Any]) -> None:
        for ws in self.connections.get(job_id, []):
            try:
                await ws.send_json(data)
            except Exception:
                pass

ws_manager = ConnectionManager()
model_cache: dict[str, Any] = {}

# ── Cleanup ────────────────────────────────────────────
async def cleanup_expired_jobs() -> None:
    while True:
        try:
            await asyncio.sleep(settings.job_cleanup_interval_seconds)
            removed = store.cleanup_expired(settings.job_timeout_seconds)
            if removed:
                logger.info(f"Cleaned up {removed} expired jobs")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

# ── Lifespan ───────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Wulira API v2.0...")
    task = asyncio.create_task(cleanup_expired_jobs())
    logger.info(f"Environment: {settings.env}")
    logger.info(f"Storage: {'Redis' if settings.redis_url else 'Memory'}")
    logger.info(f"Auth: {'enabled' if auth_mgr.enabled else 'disabled (set WULIRA_API_KEY to enable)'}")
    yield
    task.cancel()
    logger.info("Shutting down Wulira API")

# ── App ────────────────────────────────────────────────
app = FastAPI(
    title="Wulira API",
    version="2.0.0",
    description="Hear every word, in every language.",
    docs_url="/api/docs" if settings.env == "development" else None,
    lifespan=lifespan,
)

cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# ── Middleware: Rate Limit + Auth ──────────────────────
@app.middleware("http")
async def middleware_stack(request: Request, call_next):
    path = request.url.path

    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    rate_limit_store[client_ip] = [t for t in rate_limit_store[client_ip] if now - t < RATE_LIMIT_WINDOW]
    if len(rate_limit_store[client_ip]) >= RATE_LIMIT_MAX:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"}, headers={"Retry-After": str(RATE_LIMIT_WINDOW)})
    rate_limit_store[client_ip].append(now)

    # API key auth (skip for public paths and when auth is disabled)
    if auth_mgr.enabled and not is_public_path(path):
        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if not api_key or not auth_mgr.validate(api_key):
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})

    return await call_next(request)

# ── Language Names ────────────────────────────────────
LANG_NAMES = {
    "sw":"Kiswahili","lg":"Luganda","en":"English","fr":"French",
    "ar":"Arabic","hi":"Hindi","es":"Spanish","de":"German",
    "yo":"Yoruba","ha":"Hausa","rw":"Kinyarwanda","am":"Amharic","so":"Somali",
}

def lang_display(code: str | None) -> str:
    if not code: return "Unknown"
    return LANG_NAMES.get(code.split("-")[0].lower(), code.upper())

# ── Validation ────────────────────────────────────────
def validate_youtube_url(url: str) -> str:
    youtube_regex = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
    if not re.match(youtube_regex, url):
        raise ValueError("Invalid YouTube URL")
    return url

# ── Pydantic Models ────────────────────────────────────
class TranscribeRequest(BaseModel):
    url: str
    language: Optional[str] = None
    model: str = "base"
    timestamps: bool = True

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return validate_youtube_url(v)

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        allowed = settings.allowed_whisper_models.split(",")
        if v not in allowed:
            raise ValueError(f"Model must be one of: {', '.join(allowed)}")
        return v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 5:
            raise ValueError("Invalid language code")
        return v

class BatchTranscribeRequest(BaseModel):
    urls: list[str]
    language: Optional[str] = None
    model: str = "base"
    timestamps: bool = True

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v: list[str]) -> list[str]:
        if len(v) > 10: raise ValueError("Maximum 10 URLs per batch")
        if not v: raise ValueError("At least 1 URL required")
        return v

class TranslateRequest(BaseModel):
    from_code: str
    to_code: str

# ── Job Runner ─────────────────────────────────────────
async def notify_progress(job_id: str, stage: str, pct: int = 0) -> None:
    await ws_manager.broadcast(job_id, {"stage": stage, "progress": pct, "job_id": job_id})

async def run_job(job_id: str, url: str, language: str | None, model_name: str, timestamps: bool) -> None:
    job_data: dict[str, Any] = {
        "job_id": job_id,
        "status": "processing",
        "created_at": datetime.now().isoformat(),
    }
    store.save(job_id, job_data)
    logger.info(f"Starting job {job_id}")

    try:
        import yt_dlp
        import whisper  # type: ignore[import-untyped]

        if model_name not in model_cache:
            model_cache[model_name] = whisper.load_model(model_name)
        model: Any = model_cache[model_name]

        with tempfile.TemporaryDirectory() as tmp:
            await notify_progress(job_id, "downloading", 10)
            ydl_opts: dict[str, Any] = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(tmp, "audio.%(ext)s"),
                "quiet": True, "no_warnings": True, "socket_timeout": 60,
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "128"}],
            }
            meta: dict[str, Any] = {}
            with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
                data = ydl.extract_info(url, download=True)
                meta = {"title": data.get("title", "Unknown"), "uploader": data.get("uploader", "Unknown"), "duration": data.get("duration", 0)}
                if meta.get("duration", 0) > settings.max_video_duration_seconds:
                    raise ValueError(f"Video too long (max {settings.max_video_duration_seconds}s)")

            audio_path = os.path.join(tmp, "audio.mp3")
            if not os.path.exists(audio_path):
                for f in os.listdir(tmp):
                    if f.startswith("audio."): audio_path = os.path.join(tmp, f); break
            if not os.path.exists(audio_path):
                raise FileNotFoundError("Audio file not found")

            # Detect language
            await notify_progress(job_id, "detecting_language", 40)
            w: Any = whisper
            audio = w.pad_or_trim(w.load_audio(audio_path))
            mel = w.log_mel_spectrogram(audio).to(model.device)
            _, probs_list = model.detect_language(mel)
            probs = cast(dict[str, float], probs_list[0] if isinstance(probs_list, list) else probs_list)
            ranked = sorted(probs.items(), key=lambda x: x[1], reverse=True)
            detected = ranked[0][0]
            confidence = round(ranked[0][1] * 100, 1)
            top5 = [{"code": c, "name": lang_display(c), "confidence": round(p * 100, 1)} for c, p in ranked[:5]]

            # Pipeline
            await notify_progress(job_id, "transcribing", 60)
            lang_to_use = language or detected
            pipeline_result = LyricsPipeline.extract(url=url, audio_path=audio_path, whisper_model=model, language=lang_to_use, duration=meta.get("duration", 0))
            segments = pipeline_result["segments"]
            source = pipeline_result["source"]
            if not timestamps:
                segments = [{"text": s["text"]} for s in segments]

        await notify_progress(job_id, "done", 100)
        job_data.update({
            "status": "done",
            "language_detected": lang_display(detected), "language_code": detected,
            "language_confidence": confidence, "language_top5": top5,
            "timestamps": timestamps, "transcript": segments,
            "lyrics_source": source, "song_metadata": pipeline_result.get("metadata", {}),
            **meta,
        })
        store.save(job_id, job_data)
        logger.info(f"Job {job_id} done ({source})")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        job_data.update({"status": "error", "error": str(e)})
        store.save(job_id, job_data)

# ── Endpoints ──────────────────────────────────────────
@app.get("/api/health")
def health():
    return {
        "status": "ok", "service": "Wulira API", "version": "2.0.0",
        "tagline": "Hear every word, in every language.",
        "storage": "redis" if settings.redis_url else "memory",
        "auth_enabled": auth_mgr.enabled,
        "translation_available": translator.is_available(),
    }

@app.post("/api/transcribe")
async def transcribe_endpoint(req: TranscribeRequest, bg: BackgroundTasks):
    job_id = str(uuid.uuid4())
    store.save(job_id, {"job_id": job_id, "status": "queued", "created_at": datetime.now().isoformat()})
    bg.add_task(run_job, job_id, req.url, req.language, req.model, req.timestamps)
    return {"job_id": job_id, "status": "queued"}

@app.get("/api/job/{job_id}")
def get_job(job_id: str):
    job = store.get(job_id)
    if not job: raise HTTPException(404, "Job not found")
    return job

@app.get("/api/jobs")
def list_jobs(limit: int = 50, offset: int = 0):
    return {"jobs": store.list_all(limit, offset)}

@app.delete("/api/job/{job_id}")
def delete_job(job_id: str):
    if not store.delete(job_id): raise HTTPException(404, "Job not found")
    return {"status": "deleted", "job_id": job_id}

@app.get("/api/stats")
def get_stats():
    counts = store.count_by_status()
    return {
        "total_jobs": sum(counts.values()),
        "processing": counts.get("processing", 0),
        "done": counts.get("done", 0),
        "errors": counts.get("error", 0),
        "models_cached": list(model_cache.keys()),
        "environment": settings.env,
    }

@app.post("/api/batch-transcribe")
async def batch_transcribe(req: BatchTranscribeRequest, bg: BackgroundTasks):
    job_ids = []
    for url in req.urls:
        validate_youtube_url(url)
        job_id = str(uuid.uuid4())
        store.save(job_id, {"job_id": job_id, "status": "queued", "created_at": datetime.now().isoformat()})
        bg.add_task(run_job, job_id, url, req.language, req.model, req.timestamps)
        job_ids.append(job_id)
    return {"batch_id": str(uuid.uuid4()), "job_ids": job_ids, "count": len(job_ids), "status": "queued"}

# ── Export ─────────────────────────────────────────────
@app.get("/api/job/{job_id}/export/{export_format}")
def export_transcript(job_id: str, export_format: str):
    job = store.get(job_id)
    if not job: raise HTTPException(404, "Job not found")
    if job.get("status") != "done": raise HTTPException(400, "Job not done")
    transcript = job.get("transcript", [])
    if not transcript: raise HTTPException(400, "No transcript")
    metadata = {k: job.get(k) for k in ("title", "uploader", "duration", "language_code", "language_detected")}
    fmt = export_format.lower()

    if fmt == "srt": return PlainTextResponse(LyricsProcessor.export_srt(transcript, metadata))
    if fmt == "lrc": return PlainTextResponse(LyricsProcessor.export_lrc(transcript, metadata))
    if fmt == "vtt": return PlainTextResponse(LyricsProcessor.export_vtt(transcript, metadata), media_type="text/vtt")
    if fmt == "csv": return PlainTextResponse(LyricsProcessor.export_csv(transcript, metadata), media_type="text/csv")
    if fmt == "json": return LyricsProcessor.export_json(transcript, metadata)
    if fmt == "txt":
        lines = [f"Title: {metadata.get('title','Unknown')}", f"Artist: {metadata.get('uploader','Unknown')}", "-" * 60]
        lines += [s["text"] for s in transcript]
        return PlainTextResponse("\n".join(lines))
    raise HTTPException(400, f"Unknown format: {export_format}")

# ── Search ─────────────────────────────────────────────
@app.get("/api/job/{job_id}/search")
def search_lyrics(job_id: str, q: str):
    if len(q) < 2: raise HTTPException(400, "Query too short")
    job = store.get(job_id)
    if not job: raise HTTPException(404, "Job not found")
    if job.get("status") != "done": raise HTTPException(400, "Job not done")
    results = LyricsProcessor.search_lyrics(job.get("transcript", []), q)
    return {"query": q, "results_count": len(results), "results": results, "title": job.get("title")}

# ── Lyrics Stats ───────────────────────────────────────
@app.get("/api/job/{job_id}/lyrics-stats")
def get_lyrics_stats(job_id: str):
    job = store.get(job_id)
    if not job: raise HTTPException(404, "Job not found")
    if job.get("status") != "done": raise HTTPException(400, "Job not done")
    stats = LyricsProcessor.get_statistics(job.get("transcript", []))
    stats["overall_confidence"] = LyricsProcessor.calculate_confidence(job.get("transcript", []))
    return {"job_id": job_id, "title": job.get("title"), "statistics": stats}

# ── Translation ────────────────────────────────────────
@app.get("/api/translate/languages")
def get_translation_languages():
    return {
        "available": translator.is_available(),
        "languages": translator.get_installed_languages(),
        "pairs": translator.get_available_pairs(),
    }

@app.post("/api/translate/install")
def install_translation_pair(req: TranslateRequest):
    if not translator.is_available():
        raise HTTPException(400, "argostranslate not installed. Run: pip install argostranslate")
    ok = translator.install_language_pair(req.from_code, req.to_code)
    if not ok: raise HTTPException(400, f"Could not install {req.from_code}→{req.to_code}")
    return {"status": "installed", "from": req.from_code, "to": req.to_code}

@app.post("/api/job/{job_id}/translate")
def translate_job(job_id: str, req: TranslateRequest):
    if not translator.is_available():
        raise HTTPException(400, "argostranslate not installed. Run: pip install argostranslate")
    job = store.get(job_id)
    if not job: raise HTTPException(404, "Job not found")
    if job.get("status") != "done": raise HTTPException(400, "Job not done")
    transcript = job.get("transcript", [])
    translated = translator.translate_segments(transcript, req.from_code, req.to_code)
    return {"job_id": job_id, "from": req.from_code, "to": req.to_code, "translated": translated}

# ── Auth Management ────────────────────────────────────
@app.post("/api/auth/keys")
def create_api_key(name: str = "default"):
    raw_key = auth_mgr.create_key(name)
    return {"api_key": raw_key, "name": name, "note": "Save this key — it cannot be retrieved again"}

@app.get("/api/auth/keys")
def list_api_keys():
    return {"keys": auth_mgr.list_keys()}

# ── WebSocket ──────────────────────────────────────────
@app.websocket("/ws/job/{job_id}")
async def ws_job_progress(ws: WebSocket, job_id: str):
    await ws_manager.connect(ws, job_id)
    try:
        job = store.get(job_id)
        if job:
            await ws.send_json({"stage": job.get("status", "unknown"), "job_id": job_id})
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(ws, job_id)

# ── Static / Dashboard ────────────────────────────────
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if not os.path.exists(static_dir):
    static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        index = os.path.join(static_dir, "index.html")
        with open(index, "r", encoding="utf-8") as f:
            return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host=settings.api_host, port=settings.api_port, reload=(settings.env == "development"))
