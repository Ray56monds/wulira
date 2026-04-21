#!/usr/bin/env python3
"""
Wulira — Hear every word, in every language.
---------------------------------------------
Extract lyrics and transcripts from any YouTube video.
Works even when a video has NO captions enabled.

"Wulira" means "to hear / to listen" in Luganda 🇺🇬

SETUP (run once):
    pip install -r requirements.txt

USAGE:
    python wulira.py <YouTube_URL>
    python wulira.py <URL> --language lg --model medium   # Luganda
    python wulira.py <URL> --language sw                  # Kiswahili
    python wulira.py <URL> --language en                  # English
    python wulira.py <URL> --detect-only                  # language detection only
    python wulira.py <URL> --output lyrics.txt            # save to file
    python wulira.py <URL> --model large                  # best accuracy
"""

import sys
import os
import logging
import argparse
import tempfile
import time
from typing import Any, cast

# Import lyrics processor and pipeline
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "api"))
try:
    from lyrics import LyricsProcessor
except ImportError:
    LyricsProcessor = None
try:
    from fingerprint import LyricsPipeline
except ImportError:
    LyricsPipeline = None

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger("wulira")

LANG_NAMES = {
    "sw": "Kiswahili", "lg": "Luganda",  "en": "English",
    "fr": "French",    "ar": "Arabic",   "hi": "Hindi",
    "pt": "Portuguese","es": "Spanish",  "de": "German",
    "zh": "Chinese",   "ja": "Japanese", "ko": "Korean",
    "ru": "Russian",   "it": "Italian",  "nl": "Dutch",
    "tr": "Turkish",   "pl": "Polish",   "vi": "Vietnamese",
    "id": "Indonesian","th": "Thai",     "yo": "Yoruba",
    "ha": "Hausa",     "ig": "Igbo",     "am": "Amharic",
    "so": "Somali",    "rw": "Kinyarwanda", "ln": "Lingala",
}
LOW_RESOURCE = {"lg", "yo", "ha", "ig", "rw", "ln", "so", "am"}
MAX_VIDEO_DURATION = 7200  # 2 hours

def lang_display(code: str | None) -> str:
    if not code: return "Unknown"
    return LANG_NAMES.get(code.split("-")[0].lower(), code.upper())

def check_deps() -> None:
    missing: list[str] = []
    try: import yt_dlp; _ = yt_dlp
    except ImportError: missing.append("yt-dlp")
    try: import whisper; _ = whisper  # type: ignore[import-untyped]
    except ImportError: missing.append("openai-whisper")
    if missing:
        print("Missing dependencies. Run:")
        print(f"    pip install -r requirements.txt")
        sys.exit(1)

def download_audio(url: str, out_dir: str) -> tuple[str, dict[str, Any]]:
    import yt_dlp
    ydl_opts: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(out_dir, "audio.%(ext)s"),
        "quiet": True, "no_warnings": True,
        "socket_timeout": 60,
        "postprocessors": [{"key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3", "preferredquality": "128"}],
        "prefer_ffmpeg": True,
    }
    info: dict[str, Any] = {}
    with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
        try:
            data = ydl.extract_info(url, download=True)
            info = {"title": data.get("title","Unknown"),
                    "uploader": data.get("uploader","Unknown"),
                    "duration": data.get("duration", 0)}
            
            # Validate duration
            if info.get("duration", 0) > MAX_VIDEO_DURATION:
                raise ValueError(f"Video too long. Max duration: {MAX_VIDEO_DURATION}s")
                
        except Exception as e:
            logger.error(f"Download failed: {e}")
            sys.exit(1)

    audio: str = os.path.join(out_dir, "audio.mp3")
    if not os.path.exists(audio):
        for f in os.listdir(out_dir):
            if f.startswith("audio."): audio = os.path.join(out_dir, f); break
    return audio, info

def detect_language(audio_path: str, model: Any) -> tuple[str, str, float]:
    import whisper  # type: ignore[import-untyped]
    w: Any = whisper
    print("Detecting language...")
    audio = w.pad_or_trim(w.load_audio(audio_path))
    mel = w.log_mel_spectrogram(audio).to(model.device)
    _, probs_list = model.detect_language(mel)
    probs: dict[str, float] = cast(dict[str, float], probs_list[0] if isinstance(probs_list, list) else probs_list)
    ranked: list[tuple[str, float]] = sorted(probs.items(), key=lambda x: x[1], reverse=True)

    print()
    print("-" * 50)
    print("  Wulira — language detection (top 5)")
    print("-" * 50)
    for i,(code,prob) in enumerate(ranked[:5]):
        bar = "#" * int(prob * 28)
        mark = "  <-- detected" if i == 0 else ""
        print(f"  {lang_display(code):<18} {prob*100:5.1f}%  {bar}{mark}")
    print("-" * 50)
    print()

    top_code: str = ranked[0][0]
    return top_code, lang_display(top_code), round(ranked[0][1]*100, 1)

def transcribe(audio_path: str, model: Any, language: str | None = None) -> tuple[list[dict[str, Any]], str]:
    kwargs: dict[str, Any] = {"verbose": False}
    if language: kwargs["language"] = language
    result: dict[str, Any] = model.transcribe(audio_path, **kwargs)
    raw_segments: list[dict[str, Any]] = result.get("segments", [])
    segments: list[dict[str, Any]] = [{"start": s["start"], "end": s["end"], "text": s["text"].strip()}
                for s in raw_segments]
    return segments, result.get("language", "unknown")

def fmt_time(sec: float) -> str:
    s = int(sec); m, s = divmod(s, 60)
    return f"{m}:{s:02d}"

def format_output(segments: list[dict[str, Any]], info: dict[str, Any], lang_code: str, timestamps: bool = True) -> str:
    lines: list[str] = [
        f"Title    : {info.get('title','')}",
        f"Uploader : {info.get('uploader','')}",
        f"Duration : {fmt_time(info.get('duration',0))}",
        f"Language : {lang_display(lang_code)} ({lang_code})",
        f"Lines    : {len(segments)}",
        "-" * 60,
    ]
    for s in segments:
        lines.append(f"[{fmt_time(s['start'])}]  {s['text']}" if timestamps else s["text"])
    return "\n".join(lines)

def recommend_model(lang_code: str, model_name: str) -> None:
    base: str = (lang_code or "").split("-")[0].lower()
    if base in LOW_RESOURCE and model_name in ("tiny","base"):
        print(f"\n⚠️  NOTE: '{lang_display(base)}' is a low-resource language.")
        print("For better accuracy re-run with:  --model medium  or  --model large\n")

def main():
    p = argparse.ArgumentParser(description="Wulira — hear every word, in every language.")
    p.add_argument("url")
    p.add_argument("--language","-l", default=None,
                   help="Language code: lg, sw, en, fr, ar... (auto-detected if omitted)")
    p.add_argument("--model","-m", default="base",
                   choices=["tiny","base","small","medium","large"])
    p.add_argument("--output","-o", default=None,
                   help="Output file path")
    p.add_argument("--format", "-f", default="txt",
                   choices=["txt", "srt", "lrc", "json", "csv", "vtt"],
                   help="Output format (default: txt)")
    p.add_argument("--no-timestamps", action="store_true")
    p.add_argument("--detect-only",   action="store_true")
    p.add_argument("--no-pipeline", action="store_true",
                   help="Skip multi-strategy pipeline, use Whisper only")
    p.add_argument("--quiet", "-q", action="store_true",
                   help="Suppress banner and progress output")
    p.add_argument("--retry", type=int, default=1,
                   help="Number of download attempts (default: 1)")
    p.add_argument("--merge-short", type=float, default=0,
                   help="Merge segments shorter than N seconds")
    p.add_argument("--stats", action="store_true",
                   help="Show lyrics statistics")
    p.add_argument("--clean", action="store_true",
                   help="Clean filler words from lyrics")
    args = p.parse_args()

    check_deps()
    import whisper  # type: ignore[import-untyped]
    w: Any = whisper

    if not args.quiet:
        print()
        print("=" * 50)
        print("  Wulira — hear every word, in every language")
        print("  wulira.app  |  Made in Uganda 🇺🇬")
        print("=" * 50)
        print(f"  URL   : {args.url}")
        print(f"  Model : {args.model}")
        print(f"  Lang  : {lang_display(args.language) if args.language else 'auto-detect'}")
        print(f"  Format: {args.format}")
        print()

    _log = (lambda msg: None) if args.quiet else (lambda msg: print(msg))

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            _log("Downloading audio...")
            audio, info = None, None
            for attempt in range(1, args.retry + 1):
                try:
                    audio, info = download_audio(args.url, tmpdir)
                    break
                except SystemExit:
                    if attempt < args.retry:
                        _log(f"  Retry {attempt}/{args.retry}...")
                        time.sleep(2 * attempt)
                    else:
                        raise
            _log(f"Downloaded : {info.get('title','?')}\n")

            _log(f"Loading Whisper '{args.model}' model...")
            model: Any = w.load_model(args.model)

            detected_code, _, confidence = detect_language(audio, model)
            if not args.quiet:
                recommend_model(detected_code, args.model)

            if args.detect_only:
                print(f"Detected: {lang_display(detected_code)} ({detected_code}) — {confidence}% confidence")
                return

            lang_to_use: str = args.language or detected_code

            # ── Multi-strategy pipeline ──
            if LyricsPipeline and not args.no_pipeline:
                _log("Running lyrics pipeline (captions → lyrics DB → vocal separation → whisper)...")
                pipeline_result = LyricsPipeline.extract(
                    url=args.url,
                    audio_path=audio,
                    whisper_model=model,
                    language=lang_to_use,
                    duration=info.get("duration", 0),
                )
                segments = pipeline_result["segments"]
                final_lang = pipeline_result.get("language", lang_to_use)
                source = pipeline_result["source"]
                _log(f"  Source: {source}")
                if pipeline_result.get("metadata", {}).get("track"):
                    _log(f"  Song: {pipeline_result['metadata'].get('artist', '?')} — {pipeline_result['metadata']['track']}")
            else:
                _log(f"Transcribing in {lang_display(lang_to_use)}...")
                segments, final_lang = transcribe(audio, model, lang_to_use)
                source = "whisper"

        except Exception as e:
            logger.error(f"Error during processing: {e}")
            sys.exit(1)

    if not segments:
        print("⚠️  Transcript is empty — audio may be music-only or too noisy.")
        sys.exit(1)

    # Apply cleaning if requested
    if args.clean and LyricsProcessor:
        _log("Cleaning lyrics...")
        segments = [
            {**seg, "text": LyricsProcessor.clean_text(seg["text"])}
            for seg in segments
        ]

    # Merge short segments if requested
    if args.merge_short > 0 and LyricsProcessor:
        segments = LyricsProcessor.merge_short_segments(segments, args.merge_short)

    # Show statistics if requested
    if args.stats and LyricsProcessor:
        stats = LyricsProcessor.get_statistics(segments)
        print("\n📊 Lyrics Statistics:")
        print(f"  Total segments: {stats['total_segments']}")
        print(f"  Total words: {stats['total_words']}")
        print(f"  Unique words: {stats['unique_words']}")
        print(f"  Avg words/segment: {stats['avg_words_per_segment']:.1f}")
        print(f"  Avg segment duration: {stats['avg_segment_duration']:.1f}s")
        if stats.get('chorus_indices'):
            print(f"  Possible chorus lines: {len(stats['chorus_indices'])}")
        print()

    # Generate output based on format
    try:
        if args.format == "srt" and LyricsProcessor:
            result = LyricsProcessor.export_srt(segments, info)
        elif args.format == "lrc" and LyricsProcessor:
            result = LyricsProcessor.export_lrc(segments, info)
        elif args.format == "vtt" and LyricsProcessor:
            result = LyricsProcessor.export_vtt(segments, info)
        elif args.format == "csv" and LyricsProcessor:
            result = LyricsProcessor.export_csv(segments, info)
        elif args.format == "json" and LyricsProcessor:
            import json
            export_data = LyricsProcessor.export_json(segments, info)
            result = json.dumps(export_data, indent=2)
        else:
            # Default txt format
            result = format_output(segments, info, final_lang, not args.no_timestamps)

        print(result)

        if args.output:
            try:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(result)
                print(f"\n✓ Saved to: {args.output}")
            except Exception as e:
                logger.error(f"Failed to save file: {e}")
                sys.exit(1)

    except Exception as e:
        logger.error(f"Error generating output: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
