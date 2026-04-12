# Wulira 🎵

> **Wulira** — *to hear, to listen* (Luganda)

Extract lyrics and transcripts from **any YouTube video** in **any language** — even videos with no captions. Built for East Africa, works everywhere.

**wulira.app** · Made in Uganda 🇺🇬

---

## Features

- ✅ Works on videos **with or without captions**
- 🌍 Supports **99+ languages** — auto-detected
- ⭐ Optimised for **Kiswahili**, **Luganda**, and **English**
- 🔍 Language confidence ranking before transcription
- ⏱ Timestamped output
- 💾 Export to `.txt` or `.srt`
- 🧠 5 Whisper model sizes — from fast to most accurate
- 🌐 REST API for developers

---

## Quick Start (CLI)

```bash
pip install -r requirements.txt

# Auto-detect language — just run it
python wulira.py https://www.youtube.com/watch?v=XXXXX

# Luganda (use medium for best accuracy)
python wulira.py <URL> --language lg --model medium

# Kiswahili
python wulira.py <URL> --language sw

# Detect language only — fast
python wulira.py <URL> --detect-only

# Save to file
python wulira.py <URL> --output lyrics.txt
```

---

## Web API

```bash
# Start the server
uvicorn api.main:app --reload

# Transcribe a video
curl -X POST http://localhost:8000/api/transcribe \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=XXXXX", "model": "base"}'

# Poll for result
curl http://localhost:8000/api/job/{job_id}
```

---

## Model Guide

| Model    | Speed   | Accuracy | Best for                    |
| -------- | ------- | -------- | --------------------------- |
| `tiny`   | Fastest | Low      | Quick tests                 |
| `base`   | Fast    | Good     | English / common languages  |
| `small`  | Medium  | Better   | Most languages              |
| `medium` | Slow    | High     | **Kiswahili, Luganda** ⭐   |
| `large`  | Slowest | Best     | Low-resource languages      |

> For Luganda always use `--model medium` or `--model large`.

---

## Deploy

### Railway (recommended)

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Select your `wulira` repo — auto-deploys via the Dockerfile

### Docker

```bash
docker build -t wulira .
docker run -p 8000:8000 wulira
```

---

## Roadmap

- [x] CLI with auto language detection
- [x] FastAPI backend
- [ ] Web UI
- [ ] SRT subtitle export
- [ ] Luganda → English translation
- [ ] Batch processing
- [ ] Wulira API with key authentication
- [ ] Mobile app (Android)

---

## Language Support

Natively optimised for:

- 🇺🇬 **Luganda** (`lg`)
- 🇹🇿🇰🇪 **Kiswahili** (`sw`)
- 🇬🇧 **English** (`en`)

Plus all 99 languages supported by OpenAI Whisper.

---

## License

MIT — free to use, modify, and build on.

---

## About

Built in Kampala 🇺🇬 · Powered by [OpenAI Whisper](https://github.com/openai/whisper) + [yt-dlp](https://github.com/yt-dlp/yt-dlp)
