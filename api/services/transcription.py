"""Services — Business logic for transcription jobs"""

import os
import logging
import tempfile
from datetime import datetime
from typing import Any, cast

logger = logging.getLogger("wulira-service")

LANG_NAMES = {
    "sw": "Kiswahili", "lg": "Luganda", "en": "English", "fr": "French",
    "ar": "Arabic", "hi": "Hindi", "es": "Spanish", "de": "German",
    "yo": "Yoruba", "ha": "Hausa", "rw": "Kinyarwanda", "am": "Amharic", "so": "Somali",
}

model_cache: dict[str, Any] = {}


def lang_display(code: str | None) -> str:
    if not code:
        return "Unknown"
    return LANG_NAMES.get(code.split("-")[0].lower(), code.upper())


async def run_transcription(
    job_id: str,
    url: str,
    language: str | None,
    model_name: str,
    timestamps: bool,
    store: Any,
    notify_fn: Any,
    max_duration: int = 7200,
) -> None:
    job_data: dict[str, Any] = {
        "job_id": job_id,
        "status": "processing",
        "created_at": datetime.now().isoformat(),
        "log": ["Job started"],
    }
    store.save(job_id, job_data)

    def log(msg: str) -> None:
        job_data.setdefault("log", []).append(msg)
        store.save(job_id, job_data)
        logger.info(f"[{job_id[:8]}] {msg}")

    try:
        import yt_dlp
        import whisper

        # Load model
        log(f"Loading Whisper '{model_name}' model...")
        if model_name not in model_cache:
            model_cache[model_name] = whisper.load_model(model_name)
        model = model_cache[model_name]

        with tempfile.TemporaryDirectory() as tmp:
            # Download
            await notify_fn(job_id, "downloading", 10)
            log("Downloading audio from YouTube...")
            ydl_opts: dict[str, Any] = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(tmp, "audio.%(ext)s"),
                "quiet": True, "no_warnings": True, "socket_timeout": 60,
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "128"}],
            }
            meta: dict[str, Any] = {}
            with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
                data = ydl.extract_info(url, download=True)
                meta = {
                    "title": data.get("title", "Unknown"),
                    "uploader": data.get("uploader", "Unknown"),
                    "duration": data.get("duration", 0),
                }
                if meta["duration"] > max_duration:
                    raise ValueError(f"Video too long (max {max_duration}s)")

            log(f"Downloaded: {meta['title']} ({meta['duration']}s)")

            audio_path = os.path.join(tmp, "audio.mp3")
            if not os.path.exists(audio_path):
                for f in os.listdir(tmp):
                    if f.startswith("audio."):
                        audio_path = os.path.join(tmp, f)
                        break
            if not os.path.exists(audio_path):
                raise FileNotFoundError("Audio file not found")

            # Detect language
            await notify_fn(job_id, "detecting_language", 40)
            log("Detecting language...")
            w = whisper
            audio = w.pad_or_trim(w.load_audio(audio_path))
            mel = w.log_mel_spectrogram(audio).to(model.device)
            _, probs_list = model.detect_language(mel)
            probs = cast(dict[str, float], probs_list[0] if isinstance(probs_list, list) else probs_list)
            ranked = sorted(probs.items(), key=lambda x: x[1], reverse=True)
            detected = ranked[0][0]
            confidence = round(ranked[0][1] * 100, 1)
            top5 = [{"code": c, "name": lang_display(c), "confidence": round(p * 100, 1)} for c, p in ranked[:5]]
            log(f"Detected: {lang_display(detected)} ({confidence}%)")

            # Pipeline
            await notify_fn(job_id, "transcribing", 60)
            lang_to_use = language or detected
            log(f"Running lyrics pipeline in {lang_display(lang_to_use)}...")

            from api.fingerprint import LyricsPipeline
            pipeline_result = LyricsPipeline.extract(
                url=url, audio_path=audio_path, whisper_model=model,
                language=lang_to_use, duration=meta.get("duration", 0),
            )
            segments = pipeline_result["segments"]
            source = pipeline_result["source"]
            log(f"Pipeline source: {source} ({len(segments)} segments)")

            if not timestamps:
                segments = [{"text": s["text"]} for s in segments]

        # Done
        await notify_fn(job_id, "done", 100)
        log("✓ Complete!")
        job_data.update({
            "status": "done",
            "language_detected": lang_display(detected),
            "language_code": detected,
            "language_confidence": confidence,
            "language_top5": top5,
            "timestamps": timestamps,
            "transcript": segments,
            "lyrics_source": source,
            "song_metadata": pipeline_result.get("metadata", {}),
            **meta,
        })
        store.save(job_id, job_data)

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        log(f"✗ Error: {e}")
        job_data.update({"status": "error", "error": str(e)})
        store.save(job_id, job_data)
