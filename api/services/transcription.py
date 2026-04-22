"""Services — Business logic for transcription jobs"""

import os
import json
import subprocess
import logging
import tempfile
import urllib.request
import urllib.parse
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


def _get_video_meta(url: str) -> dict[str, Any]:
    """Get video metadata via oembed (never blocked)."""
    try:
        video_id = ""
        if "youtu.be/" in url:
            video_id = url.split("youtu.be/")[1].split("?")[0].split("&")[0]
        elif "v=" in url:
            video_id = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("v", [""])[0]
        if not video_id:
            return {"title": "Unknown", "uploader": "Unknown", "duration": 0}

        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return {
            "title": data.get("title", "Unknown"),
            "uploader": data.get("author_name", "Unknown"),
            "duration": 0,
        }
    except Exception:
        return {"title": "Unknown", "uploader": "Unknown", "duration": 0}


def _download_ytdlp(url: str, tmp: str, log_fn: Any) -> bool:
    """Try yt-dlp with PO token plugin + proxy support."""
    try:
        import yt_dlp
    except ImportError:
        return False

    proxy = os.environ.get("YTDLP_PROXY", "")

    base_opts: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(tmp, "audio.%(ext)s"),
        "quiet": True, "no_warnings": True, "socket_timeout": 60,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "128"}],
        "http_headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"},
    }
    if proxy:
        base_opts["proxy"] = proxy
        log_fn(f"Using proxy: {proxy[:40]}...")

    strategies = [
        {"player_client": ["web"], "player_skip": ["webpage"]},
        {"player_client": ["android"]},
        {"player_client": ["ios"]},
        {"player_client": ["mweb"], "player_skip": ["webpage"]},
        {"player_client": ["tv"]},
    ]

    for s in strategies:
        name = s["player_client"][0]
        try:
            opts = {**base_opts, "extractor_args": {"youtube": s}}
            with yt_dlp.YoutubeDL(cast(Any, opts)) as ydl:
                ydl.extract_info(url, download=True)
            if any(f.startswith("audio.") for f in os.listdir(tmp)):
                log_fn(f"yt-dlp [{name}]: success")
                return True
        except Exception as e:
            log_fn(f"yt-dlp [{name}]: {str(e)[:60]}")
            for f in os.listdir(tmp):
                if f.startswith("audio."):
                    try:
                        os.remove(os.path.join(tmp, f))
                    except OSError:
                        pass
    return False


def _download_pytubefix(url: str, tmp: str, log_fn: Any) -> bool:
    """Fallback: use pytubefix."""
    try:
        from pytubefix import YouTube as PyTube
        log_fn("Trying pytubefix...")
        yt = PyTube(url, use_po_token=True)
        stream = yt.streams.filter(only_audio=True).order_by("abr").desc().first()
        if not stream:
            log_fn("pytubefix: no audio stream")
            return False
        out_file = stream.download(output_path=tmp, filename="audio_raw")
        mp3_path = os.path.join(tmp, "audio.mp3")
        subprocess.run(["ffmpeg", "-i", out_file, "-q:a", "2", mp3_path, "-y"], capture_output=True, timeout=120)
        return os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 10000
    except Exception as e:
        log_fn(f"pytubefix: {str(e)[:60]}")
        return False


def _download_gallery_dl(url: str, tmp: str, log_fn: Any) -> bool:
    """Fallback: use gallery-dl + ffmpeg."""
    try:
        log_fn("Trying gallery-dl...")
        result = subprocess.run(
            ["gallery-dl", "--range", "1", "-D", tmp, url],
            capture_output=True, text=True, timeout=120,
        )
        # Find any downloaded media file and convert to mp3
        for f in os.listdir(tmp):
            if f.endswith((".webm", ".m4a", ".mp4", ".opus", ".ogg")):
                mp3_path = os.path.join(tmp, "audio.mp3")
                subprocess.run(["ffmpeg", "-i", os.path.join(tmp, f), "-q:a", "2", mp3_path, "-y"], capture_output=True, timeout=120)
                if os.path.exists(mp3_path):
                    return True
        log_fn("gallery-dl: no media found")
        return False
    except FileNotFoundError:
        return False
    except Exception as e:
        log_fn(f"gallery-dl: {str(e)[:60]}")
        return False


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
        import whisper

        log(f"Loading Whisper '{model_name}' model...")
        if model_name not in model_cache:
            model_cache[model_name] = whisper.load_model(model_name)
        model = model_cache[model_name]

        meta = _get_video_meta(url)
        log(f"Video: {meta['title']}")

        with tempfile.TemporaryDirectory() as tmp:
            await notify_fn(job_id, "downloading", 10)
            log("Downloading audio...")

            downloaded = _download_ytdlp(url, tmp, log)
            if not downloaded:
                downloaded = _download_pytubefix(url, tmp, log)
            if not downloaded:
                downloaded = _download_gallery_dl(url, tmp, log)
            if not downloaded:
                raise RuntimeError(
                    "All download methods failed. YouTube is blocking this server's IP. "
                    "Set YTDLP_PROXY env var to a SOCKS5/HTTP proxy to fix this. "
                    "Example: socks5://user:pass@proxy:1080"
                )

            audio_path = os.path.join(tmp, "audio.mp3")
            if not os.path.exists(audio_path):
                for f in os.listdir(tmp):
                    if f.startswith("audio."):
                        audio_path = os.path.join(tmp, f)
                        break
            if not os.path.exists(audio_path):
                raise FileNotFoundError("Audio file not found after download")

            log("Audio ready")

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

            # Duration from ffprobe
            if meta["duration"] == 0:
                try:
                    result = subprocess.run(
                        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", audio_path],
                        capture_output=True, text=True, timeout=10,
                    )
                    meta["duration"] = int(float(result.stdout.strip()))
                except Exception:
                    pass

            # Pipeline
            await notify_fn(job_id, "transcribing", 60)
            lang_to_use = language or detected
            log(f"Transcribing in {lang_display(lang_to_use)}...")

            from api.fingerprint import LyricsPipeline
            pipeline_result = LyricsPipeline.extract(
                url=url, audio_path=audio_path, whisper_model=model,
                language=lang_to_use, duration=meta.get("duration", 0),
            )
            segments = pipeline_result["segments"]
            source = pipeline_result["source"]
            log(f"Source: {source} ({len(segments)} segments)")

            if not timestamps:
                segments = [{"text": s["text"]} for s in segments]

        await notify_fn(job_id, "done", 100)
        log("Complete!")
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
        log(f"Error: {e}")
        job_data.update({"status": "error", "error": str(e)})
        store.save(job_id, job_data)


async def run_audio_transcription(
    job_id: str,
    audio_path: str,
    tmp_dir: str,
    language: str | None,
    model_name: str,
    timestamps: bool,
    title: str,
    store: Any,
    notify_fn: Any,
) -> None:
    """Process an already-downloaded audio file (from user upload)."""
    job_data: dict[str, Any] = {
        "job_id": job_id,
        "status": "processing",
        "created_at": datetime.now().isoformat(),
        "log": ["Audio uploaded", "Processing..."],
    }
    store.save(job_id, job_data)

    def log(msg: str) -> None:
        job_data.setdefault("log", []).append(msg)
        store.save(job_id, job_data)
        logger.info(f"[{job_id[:8]}] {msg}")

    try:
        import whisper
        import shutil

        log(f"Loading Whisper '{model_name}' model...")
        if model_name not in model_cache:
            model_cache[model_name] = whisper.load_model(model_name)
        model = model_cache[model_name]

        meta = {"title": title, "uploader": "Upload", "duration": 0}

        # Duration from ffprobe
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", audio_path],
                capture_output=True, text=True, timeout=10,
            )
            meta["duration"] = int(float(result.stdout.strip()))
        except Exception:
            pass

        log("Audio ready")

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

        # Transcribe
        await notify_fn(job_id, "transcribing", 60)
        lang_to_use = language or detected
        log(f"Transcribing in {lang_display(lang_to_use)}...")

        kwargs: dict[str, Any] = {"verbose": False}
        if lang_to_use:
            kwargs["language"] = lang_to_use
        raw = model.transcribe(audio_path, **kwargs)
        segments = [
            {"start": round(s["start"], 2), "end": round(s["end"], 2), "text": s["text"].strip()}
            for s in raw.get("segments", [])
            if s["text"].strip()
        ]
        log(f"Transcribed: {len(segments)} segments")

        if not timestamps:
            segments = [{"text": s["text"]} for s in segments]

        await notify_fn(job_id, "done", 100)
        log("Complete!")
        job_data.update({
            "status": "done",
            "language_detected": lang_display(detected),
            "language_code": detected,
            "language_confidence": confidence,
            "language_top5": top5,
            "timestamps": timestamps,
            "transcript": segments,
            "lyrics_source": "upload",
            "song_metadata": {},
            **meta,
        })
        store.save(job_id, job_data)

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        log(f"Error: {e}")
        job_data.update({"status": "error", "error": str(e)})
        store.save(job_id, job_data)
    finally:
        # Cleanup temp dir
        try:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass
