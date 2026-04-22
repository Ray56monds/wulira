"""
Audio Fingerprinting & Lyrics Lookup
--------------------------------------
Identify songs and fetch lyrics from external sources.
Works like Shazam — match audio fingerprint to a song,
then pull lyrics from databases.

Strategies (in order):
  1. YouTube captions (free, instant)
  2. Audio fingerprint → song ID → lyrics DB lookup
  3. Vocal separation (demucs) → Whisper on isolated vocals
  4. Raw Whisper on full audio (fallback)
"""

import os
import re
import json
import logging
import hashlib
import subprocess
import tempfile
from typing import Any, Optional
from pathlib import Path

logger = logging.getLogger("wulira-fingerprint")


class CaptionExtractor:
    """Strategy 1: Pull existing captions/subtitles from YouTube."""

    @staticmethod
    def extract(url: str, language: str | None = None) -> Optional[list[dict[str, Any]]]:
        """Try to get captions directly from YouTube (no transcription needed)."""
        try:
            import yt_dlp
        except ImportError:
            return None

        # Prefer manual subs, then auto-generated
        ydl_opts: dict[str, Any] = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitlesformat": "json3",
            "extractor_args": {"youtube": {"player_client": ["web", "android"]}},
            "http_headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"},
        }
        if language:
            ydl_opts["subtitleslangs"] = [language, f"{language}-*", "en", "en-*"]
        else:
            ydl_opts["subtitleslangs"] = ["all"]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                subs = info.get("subtitles", {}) or {}
                auto_subs = info.get("automatic_captions", {}) or {}

                # Pick best subtitle track
                chosen = None
                for source in (subs, auto_subs):
                    if language and language in source:
                        chosen = (language, source[language])
                        break
                    if "en" in source:
                        chosen = ("en", source["en"])
                        break
                    if source:
                        first_lang = next(iter(source))
                        chosen = (first_lang, source[first_lang])
                        break

                if not chosen:
                    return None

                lang_code, tracks = chosen
                # Find json3 format, fall back to first available
                track_url = None
                for t in tracks:
                    if t.get("ext") == "json3":
                        track_url = t.get("url")
                        break
                if not track_url and tracks:
                    track_url = tracks[0].get("url")

                if not track_url:
                    return None

                # Download and parse the subtitle data
                import urllib.request
                with urllib.request.urlopen(track_url, timeout=15) as resp:
                    raw = json.loads(resp.read().decode("utf-8"))

                segments = []
                for event in raw.get("events", []):
                    start_ms = event.get("tStartMs", 0)
                    dur_ms = event.get("dDurationMs", 0)
                    segs = event.get("segs", [])
                    text = "".join(s.get("utf8", "") for s in segs).strip()
                    text = re.sub(r"\n+", " ", text).strip()
                    if text and text != "\n":
                        segments.append({
                            "start": round(start_ms / 1000, 2),
                            "end": round((start_ms + dur_ms) / 1000, 2),
                            "text": text,
                        })

                if segments:
                    logger.info(f"Captions found: {len(segments)} segments ({lang_code})")
                return segments if segments else None

        except Exception as e:
            logger.debug(f"Caption extraction failed: {e}")
            return None


class SongIdentifier:
    """Strategy 2: Identify song by metadata/title, then fetch lyrics."""

    @staticmethod
    def identify_from_metadata(url: str) -> Optional[dict[str, str]]:
        """Extract artist + title from YouTube metadata."""
        try:
            import yt_dlp
        except ImportError:
            return None

        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, "extractor_args": {"youtube": {"player_client": ["web", "android"]}}, "http_headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}}) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "")
                artist = info.get("artist") or info.get("uploader") or info.get("channel", "")
                track = info.get("track") or ""

                # YouTube music often has "Artist - Song Title" format
                if " - " in title and not track:
                    parts = title.split(" - ", 1)
                    artist = parts[0].strip()
                    track = parts[1].strip()
                elif not track:
                    # Clean common suffixes
                    track = re.sub(
                        r"\s*[\(\[]?(official\s*(music\s*)?video|lyrics?\s*video|audio|hd|4k|visuali[sz]er|ft\..*?)[\)\]]?\s*$",
                        "", title, flags=re.IGNORECASE
                    ).strip()

                if track:
                    return {"artist": artist, "track": track, "raw_title": title}
        except Exception as e:
            logger.debug(f"Metadata extraction failed: {e}")
        return None

    @staticmethod
    def fetch_lyrics_genius(artist: str, track: str) -> Optional[str]:
        """Fetch lyrics from Genius API (requires GENIUS_API_TOKEN env var)."""
        token = os.environ.get("GENIUS_API_TOKEN")
        if not token:
            return None

        try:
            import urllib.request
            import urllib.parse

            query = urllib.parse.quote(f"{artist} {track}")
            req = urllib.request.Request(
                f"https://api.genius.com/search?q={query}",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            hits = data.get("response", {}).get("hits", [])
            if not hits:
                return None

            # Get the lyrics page URL
            song_url = hits[0]["result"]["url"]

            # Scrape lyrics from the page
            req2 = urllib.request.Request(song_url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; Wulira/1.0)"
            })
            with urllib.request.urlopen(req2, timeout=10) as resp2:
                html = resp2.read().decode("utf-8")

            # Extract lyrics from Genius HTML
            # Genius wraps lyrics in data-lyrics-container divs
            lyrics_parts = re.findall(
                r'<div[^>]*data-lyrics-container="true"[^>]*>(.*?)</div>',
                html, re.DOTALL
            )
            if not lyrics_parts:
                return None

            raw = "\n".join(lyrics_parts)
            # Clean HTML tags
            raw = re.sub(r"<br\s*/?>", "\n", raw)
            raw = re.sub(r"<[^>]+>", "", raw)
            # Decode HTML entities
            import html as html_mod
            raw = html_mod.unescape(raw).strip()

            if len(raw) > 20:
                logger.info(f"Genius lyrics found for: {artist} - {track}")
                return raw
        except Exception as e:
            logger.debug(f"Genius lookup failed: {e}")
        return None

    @staticmethod
    def lyrics_to_segments(lyrics_text: str, duration: float = 0) -> list[dict[str, Any]]:
        """Convert plain lyrics text into timed segments (estimated)."""
        lines = [ln.strip() for ln in lyrics_text.split("\n") if ln.strip()]
        if not lines:
            return []

        # Estimate timing: spread lines evenly across duration
        if duration > 0:
            interval = duration / len(lines)
        else:
            interval = 3.0  # default 3s per line

        segments = []
        for i, line in enumerate(lines):
            # Skip section headers like [Chorus], [Verse 1]
            if re.match(r"^\[.*\]$", line):
                continue
            segments.append({
                "start": round(i * interval, 2),
                "end": round((i + 1) * interval, 2),
                "text": line,
            })
        return segments


class VocalSeparator:
    """Strategy 3: Separate vocals from instrumentals using demucs."""

    @staticmethod
    def is_available() -> bool:
        """Check if demucs is installed."""
        try:
            import demucs  # noqa: F401
            return True
        except ImportError:
            return False

    @staticmethod
    def separate(audio_path: str, out_dir: str) -> Optional[str]:
        """
        Run demucs to isolate vocals.
        Returns path to the isolated vocals file, or None on failure.
        """
        try:
            result = subprocess.run(
                [
                    "python", "-m", "demucs",
                    "--two-stems", "vocals",
                    "-o", out_dir,
                    "--mp3",
                    audio_path,
                ],
                capture_output=True, text=True, timeout=600,
            )
            if result.returncode != 0:
                logger.warning(f"Demucs failed: {result.stderr[:200]}")
                return None

            # demucs outputs to out_dir/htdemucs/audio/vocals.mp3
            stem_name = Path(audio_path).stem
            vocals_path = os.path.join(out_dir, "htdemucs", stem_name, "vocals.mp3")
            if not os.path.exists(vocals_path):
                # Try .wav variant
                vocals_path = os.path.join(out_dir, "htdemucs", stem_name, "vocals.wav")

            if os.path.exists(vocals_path):
                logger.info(f"Vocal separation complete: {vocals_path}")
                return vocals_path

            logger.warning("Demucs ran but vocals file not found")
            return None

        except FileNotFoundError:
            logger.debug("demucs command not found")
            return None
        except subprocess.TimeoutExpired:
            logger.warning("Demucs timed out (>600s)")
            return None
        except Exception as e:
            logger.debug(f"Vocal separation failed: {e}")
            return None


class LyricsPipeline:
    """
    Multi-strategy lyrics extraction pipeline.
    Tries every method until lyrics are found.

    Order:
      1. YouTube captions
      2. Song identification → lyrics database
      3. Vocal separation → Whisper
      4. Raw Whisper (original fallback)
    """

    @staticmethod
    def extract(
        url: str,
        audio_path: str,
        whisper_model: Any,
        language: str | None = None,
        duration: float = 0,
    ) -> dict[str, Any]:
        """
        Run the full pipeline. Returns:
        {
            "segments": [...],
            "source": "captions" | "lyrics_db" | "vocal_separation" | "whisper",
            "language": str,
            "metadata": {...},
        }
        """
        metadata = SongIdentifier.identify_from_metadata(url) or {}
        result: dict[str, Any] = {
            "segments": [],
            "source": "whisper",
            "language": language or "unknown",
            "metadata": metadata,
        }

        # ── Strategy 1: YouTube captions ──
        logger.info("Strategy 1: Checking YouTube captions...")
        captions = CaptionExtractor.extract(url, language)
        if captions and len(captions) >= 3:
            result["segments"] = captions
            result["source"] = "captions"
            logger.info(f"✓ Captions found ({len(captions)} lines)")
            return result

        # ── Strategy 2: Song ID → lyrics database ──
        if metadata.get("track"):
            logger.info(f"Strategy 2: Looking up lyrics for '{metadata.get('artist')} - {metadata.get('track')}'...")
            lyrics_text = SongIdentifier.fetch_lyrics_genius(
                metadata.get("artist", ""),
                metadata.get("track", ""),
            )
            if lyrics_text:
                result["segments"] = SongIdentifier.lyrics_to_segments(lyrics_text, duration)
                result["source"] = "lyrics_db"
                result["raw_lyrics"] = lyrics_text
                logger.info(f"✓ Lyrics DB match ({len(result['segments'])} lines)")
                return result

        # ── Strategy 3: Vocal separation → Whisper ──
        if VocalSeparator.is_available():
            logger.info("Strategy 3: Separating vocals with demucs...")
            with tempfile.TemporaryDirectory() as sep_dir:
                vocals_path = VocalSeparator.separate(audio_path, sep_dir)
                if vocals_path:
                    segments = LyricsPipeline._whisper_transcribe(
                        vocals_path, whisper_model, language
                    )
                    if segments and len(segments) >= 2:
                        result["segments"] = segments
                        result["source"] = "vocal_separation"
                        logger.info(f"✓ Vocal separation + Whisper ({len(segments)} lines)")
                        return result
        else:
            logger.info("Strategy 3: Skipped (demucs not installed)")

        # ── Strategy 4: Raw Whisper fallback ──
        logger.info("Strategy 4: Raw Whisper transcription...")
        segments = LyricsPipeline._whisper_transcribe(
            audio_path, whisper_model, language
        )
        if segments:
            result["segments"] = segments
            result["source"] = "whisper"
            logger.info(f"✓ Whisper transcription ({len(segments)} lines)")

        return result

    @staticmethod
    def _whisper_transcribe(
        audio_path: str, model: Any, language: str | None
    ) -> list[dict[str, Any]]:
        """Run Whisper transcription on an audio file."""
        try:
            kwargs: dict[str, Any] = {"verbose": False}
            if language:
                kwargs["language"] = language
            raw = model.transcribe(audio_path, **kwargs)
            return [
                {
                    "start": round(s["start"], 2),
                    "end": round(s["end"], 2),
                    "text": s["text"].strip(),
                }
                for s in raw.get("segments", [])
                if s["text"].strip()
            ]
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return []
