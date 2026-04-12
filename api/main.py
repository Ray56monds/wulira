"""
Wulira API — FastAPI backend
-----------------------------
Wulira: "to hear / to listen" in Luganda 🇺🇬
wulira.app | Made in Kampala, Uganda
"""

import os, uuid, tempfile
from typing import Any, Optional, cast
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Wulira API", version="1.0.0",
              description="Hear every word, in every language.")

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

jobs: dict[str, dict[str, object]] = {}

LANG_NAMES = {
    "sw":"Kiswahili","lg":"Luganda","en":"English","fr":"French",
    "ar":"Arabic","hi":"Hindi","es":"Spanish","de":"German",
    "yo":"Yoruba","ha":"Hausa","rw":"Kinyarwanda","am":"Amharic","so":"Somali",
}

def lang_display(code: str | None) -> str:
    if not code: return "Unknown"
    return LANG_NAMES.get(code.split("-")[0].lower(), code.upper())

class TranscribeRequest(BaseModel):
    url: str
    language: Optional[str] = None
    model: str = "base"
    timestamps: bool = True

async def run_job(job_id: str, url: str, language: str | None, model_name: str, timestamps: bool) -> None:
    jobs[job_id]["status"] = "processing"
    try:
        import yt_dlp
        import whisper  # type: ignore[import-untyped]
        with tempfile.TemporaryDirectory() as tmp:
            ydl_opts: dict[str, Any] = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(tmp, "audio.%(ext)s"),
                "quiet": True, "no_warnings": True,
                "postprocessors": [{"key":"FFmpegExtractAudio",
                                    "preferredcodec":"mp3","preferredquality":"128"}],
            }
            meta: dict[str, Any] = {}
            with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
                data = ydl.extract_info(url, download=True)
                meta = {"title": data.get("title",""), "uploader": data.get("uploader",""),
                        "duration": data.get("duration", 0)}

            audio = os.path.join(tmp, "audio.mp3")
            if not os.path.exists(audio):
                for f in os.listdir(tmp):
                    if f.startswith("audio."): audio = os.path.join(tmp,f); break

            w: Any = whisper
            model: Any = w.load_model(model_name)

            clip = w.pad_or_trim(w.load_audio(audio))
            mel = w.log_mel_spectrogram(clip).to(model.device)
            _, probs_list = model.detect_language(mel)
            probs: dict[str, float] = cast(dict[str, float], probs_list[0] if isinstance(probs_list, list) else probs_list)
            ranked: list[tuple[str, float]] = sorted(probs.items(), key=lambda x: x[1], reverse=True)
            detected: str = ranked[0][0]
            confidence = round(ranked[0][1]*100, 1)
            top5: list[dict[str, Any]] = [{"code":c,"name":lang_display(c),"confidence":round(p*100,1)}
                    for c,p in ranked[:5]]

            lang_to_use = language or detected
            result: dict[str, Any] = model.transcribe(audio, language=lang_to_use, verbose=False)
            raw_segments: list[dict[str, Any]] = result.get("segments", [])
            segments: list[dict[str, Any]]
            if timestamps:
                segments = [{"start": round(s["start"], 2), "end": round(s["end"], 2),
                             "text": s["text"].strip()} for s in raw_segments]
            else:
                segments = [{"text": s["text"].strip()} for s in raw_segments]

        jobs[job_id].update({
            "status": "done",
            "language_detected": lang_display(detected),
            "language_code": detected,
            "language_confidence": confidence,
            "language_top5": top5,
            "timestamps": timestamps,
            "transcript": segments,
            **meta,
        })
    except Exception as e:
        jobs[job_id].update({"status":"error","error":str(e)})

@app.get("/api/health")
def health():
    return {"status":"ok","service":"Wulira API","tagline":"Hear every word, in every language."}

@app.post("/api/transcribe")
async def transcribe(req: TranscribeRequest, bg: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status":"queued","job_id":job_id}
    bg.add_task(run_job, job_id, req.url, req.language, req.model, req.timestamps)
    return {"job_id":job_id,"status":"queued"}

@app.get("/api/job/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    job = jobs.get(job_id)
    if not job: raise HTTPException(404, "Job not found")
    return job

if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
