# Wulira 🎵

> **Wulira** — *to hear, to listen* (Luganda)

Extract lyrics and transcripts from **any YouTube video** in **any language** — even videos with no captions. Built for East Africa, works everywhere.

**wulira.app** · Made in Uganda 🇺🇬

---

## Features

### Transcription
- ✅ Works on videos **with or without captions**
- 🎵 **Multi-strategy lyrics pipeline** — finds lyrics no matter what:
  1. YouTube captions (instant, free)
  2. Song fingerprint → lyrics database (Genius)
  3. Vocal separation (demucs) → Whisper on clean vocals
  4. Raw Whisper fallback
- 🌍 Supports **99+ languages** — auto-detected
- ⭐ Optimised for **Kiswahili**, **Luganda**, and **English**
- 🔍 Language confidence ranking before transcription
- ⏱ Timestamped output
- 🧠 5 Whisper model sizes — from fast to most accurate

### Export Formats
- 💾 **SRT** — Video subtitles (YouTube, VLC, Premiere)
- 🎵 **LRC** — Music player lyrics (foobar2000, winamp, apps)
- 🌐 **VTT** — Web subtitles (HTML5, streaming)
- 📊 **JSON** — Full structured data with metadata
- 📈 **CSV** — Spreadsheet analysis
- 📝 **TXT** — Plain text

### Lyrics Processing
- ✨ **Filler removal** — Automatic cleanup of "um", "uh", etc.
- 🎯 **Chorus detection** — Identify repeated sections
- 🔍 **Search** — Find phrases in lyrics with context
- 📊 **Statistics** — Word frequency, coverage, confidence scores
- 🧹 **Auto-cleaning** — Remove audio artifacts and noise

### Advanced Features
- 🚀 **Batch processing** — Submit up to 10 videos at once
- ⚡ **Model caching** — Fast reuse of loaded models
- 🔐 **URL validation** — Secure input verification
- 📈 **Quality metrics** — Per-segment and overall confidence
- 🌐 **REST API** — Full integration capabilities
- 🔄 **WebSocket progress** — Real-time job status via `ws://host/ws/job/{id}`
- 🛡️ **Rate limiting** — Per-IP request throttling (20 req/min)
- 🗑️ **Job management** — Cancel/delete jobs via API
- 🔇 **Quiet mode** — `--quiet` for scripting & pipelines
- 🔁 **Retry downloads** — `--retry N` for flaky connections
- 🧩 **Segment merging** — `--merge-short N` to combine tiny segments

---

## How It Works — The Lyrics Pipeline

Wulira uses a **4-strategy pipeline** to guarantee lyrics are found:

```
┌─────────────────────────────────────────────────┐
│  1. YouTube Captions                            │
│     Check if video has subtitles/auto-captions  │
│     → Instant, free, most accurate when present │
├─────────────────────────────────────────────────┤
│  2. Song Identification → Lyrics Database       │
│     Parse "Artist - Title" from video metadata  │
│     → Fetch lyrics from Genius API              │
├─────────────────────────────────────────────────┤
│  3. Vocal Separation → Whisper                  │
│     Use demucs to isolate vocals from music     │
│     → Run Whisper on clean vocal track only     │
├─────────────────────────────────────────────────┤
│  4. Raw Whisper (fallback)                      │
│     Transcribe the full audio directly          │
└─────────────────────────────────────────────────┘
```

Each strategy is tried in order. The first one that returns results wins.

To skip the pipeline and use Whisper only: `--no-pipeline`

### Optional Setup for Best Results

```bash
# Genius API (free) — enables lyrics database lookups
# Get a token at https://genius.com/api-clients
export GENIUS_API_TOKEN=your_token_here

# Demucs (optional) — enables vocal separation
pip install demucs
```

---

## Quick Start (CLI)

```bash
pip install -r requirements.txt

# Basic transcription
python wulira.py https://www.youtube.com/watch?v=XXXXX

# Export as SRT (subtitles)
python wulira.py <URL> --format srt --output lyrics.srt

# Export as LRC (music player)
python wulira.py <URL> --format lrc --output lyrics.lrc

# Export as JSON with stats
python wulira.py <URL> --format json --stats --clean --output lyrics.json

# Luganda with medium accuracy
python wulira.py <URL> --language lg --model medium

# Kiswahili
python wulira.py <URL> --language sw

# Quiet mode for scripting
python wulira.py <URL> --quiet --format json --output out.json

# Retry flaky downloads
python wulira.py <URL> --retry 3

# Merge short segments (< 2s)
python wulira.py <URL> --merge-short 2.0

# Detect language only
python wulira.py <URL> --detect-only
```

**See [LYRICS_FEATURES.md](LYRICS_FEATURES.md) for full CLI documentation.**

---

## Web API

```bash
# Start the server
uvicorn api.main:app --reload

# 1. Submit transcription
curl -X POST http://localhost:8000/api/transcribe \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=XXXXX", "model": "base"}'

# Response: {"job_id": "abc123", "status": "queued"}

# 2. Check status
curl http://localhost:8000/api/job/abc123

# 3. Export as SRT
curl http://localhost:8000/api/job/abc123/export/srt > lyrics.srt

# 4. Get statistics
curl http://localhost:8000/api/job/abc123/lyrics-stats

# 5. Delete a job
curl -X DELETE http://localhost:8000/api/job/abc123

# 6. WebSocket live progress (use wscat or browser)
wscat -c ws://localhost:8000/ws/job/abc123
```

**See [API_REFERENCE.md](API_REFERENCE.md) for full API documentation.**

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

### Railway (recommended — easiest)

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Select your `wulira` repo — auto-deploys via the Dockerfile
4. Set env vars in Railway dashboard: `GENIUS_API_TOKEN`, `CORS_ORIGINS`

### Render

1. Push to GitHub
2. Go to [render.com](https://render.com) → New → Web Service → Connect repo
3. Render auto-detects `render.yaml` and deploys

### AWS App Runner

```bash
# 1. Build & push to ECR
aws ecr create-repository --repository-name wulira
docker build -t wulira .
docker tag wulira:latest <account_id>.dkr.ecr.<region>.amazonaws.com/wulira:latest
aws ecr get-login-password | docker login --username AWS --password-stdin <account_id>.dkr.ecr.<region>.amazonaws.com
docker push <account_id>.dkr.ecr.<region>.amazonaws.com/wulira:latest

# 2. Deploy with CloudFormation
aws cloudformation deploy \
  --template-file aws-apprunner.json \
  --stack-name wulira \
  --parameter-overrides ImageUri=<account_id>.dkr.ecr.<region>.amazonaws.com/wulira:latest \
  --capabilities CAPABILITY_IAM
```

### Docker (anywhere)

```bash
docker build -t wulira .
docker run -p 8000:8000 \
  -e GENIUS_API_TOKEN=your_token \
  -e CORS_ORIGINS=https://yourdomain.com \
  wulira
```

### VPS / EC2 (manual)

```bash
git clone https://github.com/Ray56monds/wulira.git
cd wulira
pip install -r requirements.txt
cp .env.example .env   # edit with your values
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

---

## Roadmap

- [x] CLI with auto language detection
- [x] FastAPI backend
- [x] Multiple export formats (SRT, LRC, VTT, JSON, CSV, TXT)
- [x] Lyrics processing & cleaning
- [x] Search & statistics API
- [x] Batch processing (up to 10 URLs)
- [x] Security improvements & configuration
- [x] Comprehensive error handling
- [x] Rate limiting & WebSocket progress
- [x] Job deletion endpoint
- [x] Web UI dashboard
- [x] Persistent job storage (Redis)
- [x] API key authentication
- [x] Real-time WebSocket updates
- [x] Translation support (Luganda → English + 100 languages)
- [x] Lyrics database export (all 6 formats)
- [x] Mobile app (Android — Expo/React Native)
- [ ] iOS app

---

## 📚 Documentation

- **[LYRICS_FEATURES.md](LYRICS_FEATURES.md)** — Complete guide to all lyrics features
- **[API_REFERENCE.md](API_REFERENCE.md)** — Full API endpoint documentation
- **[IMPROVEMENTS.md](IMPROVEMENTS.md)** — Technical improvements & security
- [x] Luganda → English translation
- [x] Batch processing
- [x] Wulira API with key authentication
- [x] Mobile app (Android)
- [ ] iOS app

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
