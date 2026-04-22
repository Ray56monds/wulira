"""Routes — Job management endpoints"""

import uuid
from datetime import datetime
from typing import Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from api.models.schemas import TranscribeRequest, BatchTranscribeRequest, TranslateRequest
from api.services.transcription import run_transcription, model_cache
from api.lyrics import LyricsProcessor
from api.storage import JobStore
from fastapi.responses import PlainTextResponse
import api.translate as translator

router = APIRouter(prefix="/api")


def create_router(store: JobStore, notify_fn: Any, max_duration: int) -> APIRouter:
    r = APIRouter(prefix="/api")

    @r.get("/health")
    def health():
        return {
            "status": "ok", "service": "Wulira API", "version": "2.0.0",
            "tagline": "Hear every word, in every language.",
            "translation_available": translator.is_available(),
        }

    @r.post("/transcribe")
    async def transcribe(req: TranscribeRequest, bg: BackgroundTasks):
        job_id = str(uuid.uuid4())
        store.save(job_id, {"job_id": job_id, "status": "queued", "created_at": datetime.now().isoformat(), "log": ["Queued"]})
        bg.add_task(run_transcription, job_id, req.url, req.language, req.model, req.timestamps, store, notify_fn, max_duration)
        return {"job_id": job_id, "status": "queued"}

    @r.get("/job/{job_id}")
    def get_job(job_id: str):
        job = store.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        return job

    @r.get("/job/{job_id}/log")
    def get_job_log(job_id: str):
        job = store.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        return {"job_id": job_id, "status": job.get("status"), "log": job.get("log", [])}

    @r.get("/jobs")
    def list_jobs(limit: int = 50, offset: int = 0):
        return {"jobs": store.list_all(limit, offset)}

    @r.delete("/job/{job_id}")
    def delete_job(job_id: str):
        if not store.delete(job_id):
            raise HTTPException(404, "Job not found")
        return {"status": "deleted", "job_id": job_id}

    @r.get("/stats")
    def get_stats():
        counts = store.count_by_status()
        return {
            "total_jobs": sum(counts.values()),
            "processing": counts.get("processing", 0),
            "done": counts.get("done", 0),
            "errors": counts.get("error", 0),
            "models_cached": list(model_cache.keys()),
        }

    @r.post("/batch-transcribe")
    async def batch_transcribe(req: BatchTranscribeRequest, bg: BackgroundTasks):
        job_ids = []
        for url in req.urls:
            job_id = str(uuid.uuid4())
            store.save(job_id, {"job_id": job_id, "status": "queued", "created_at": datetime.now().isoformat(), "log": ["Queued"]})
            bg.add_task(run_transcription, job_id, url, req.language, req.model, req.timestamps, store, notify_fn, max_duration)
            job_ids.append(job_id)
        return {"batch_id": str(uuid.uuid4()), "job_ids": job_ids, "count": len(job_ids), "status": "queued"}

    # Export
    @r.get("/job/{job_id}/export/{fmt}")
    def export_transcript(job_id: str, fmt: str):
        job = store.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        if job.get("status") != "done":
            raise HTTPException(400, "Job not done")
        transcript = job.get("transcript", [])
        if not transcript:
            raise HTTPException(400, "No transcript")
        meta = {k: job.get(k) for k in ("title", "uploader", "duration", "language_code", "language_detected")}
        f = fmt.lower()
        if f == "srt": return PlainTextResponse(LyricsProcessor.export_srt(transcript, meta))
        if f == "lrc": return PlainTextResponse(LyricsProcessor.export_lrc(transcript, meta))
        if f == "vtt": return PlainTextResponse(LyricsProcessor.export_vtt(transcript, meta), media_type="text/vtt")
        if f == "csv": return PlainTextResponse(LyricsProcessor.export_csv(transcript, meta), media_type="text/csv")
        if f == "json": return LyricsProcessor.export_json(transcript, meta)
        if f == "txt":
            lines = [f"Title: {meta.get('title','Unknown')}", f"Artist: {meta.get('uploader','Unknown')}", "-" * 60]
            lines += [s["text"] for s in transcript]
            return PlainTextResponse("\n".join(lines))
        raise HTTPException(400, f"Unknown format: {fmt}")

    # Search
    @r.get("/job/{job_id}/search")
    def search_lyrics(job_id: str, q: str):
        if len(q) < 2:
            raise HTTPException(400, "Query too short")
        job = store.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        if job.get("status") != "done":
            raise HTTPException(400, "Job not done")
        results = LyricsProcessor.search_lyrics(job.get("transcript", []), q)
        return {"query": q, "results_count": len(results), "results": results}

    # Stats
    @r.get("/job/{job_id}/lyrics-stats")
    def get_lyrics_stats(job_id: str):
        job = store.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        if job.get("status") != "done":
            raise HTTPException(400, "Job not done")
        stats = LyricsProcessor.get_statistics(job.get("transcript", []))
        stats["overall_confidence"] = LyricsProcessor.calculate_confidence(job.get("transcript", []))
        return {"job_id": job_id, "title": job.get("title"), "statistics": stats}

    # Translation
    @r.get("/translate/languages")
    def get_languages():
        return {"available": translator.is_available(), "languages": translator.get_installed_languages(), "pairs": translator.get_available_pairs()}

    @r.post("/job/{job_id}/translate")
    def translate_job(job_id: str, req: TranslateRequest):
        if not translator.is_available():
            raise HTTPException(400, "Translation not available (install deep-translator)")
        job = store.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        if job.get("status") != "done":
            raise HTTPException(400, "Job not done")
        translated = translator.translate_segments(job.get("transcript", []), req.from_code, req.to_code)
        return {"job_id": job_id, "from": req.from_code, "to": req.to_code, "translated": translated}

    return r
