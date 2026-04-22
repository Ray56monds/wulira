---
title: Wulira
emoji: 🎵
colorFrom: purple
colorTo: blue
sdk: docker
app_port: 7860
pinned: true
license: mit
short_description: "Extract lyrics from any YouTube video"
---

# Wulira 🎵

> **Wulira** — *to hear, to listen* (Luganda)

Extract lyrics and transcripts from **any YouTube video** in **any language** — even videos with no captions.

**Made in Uganda 🇺🇬**

## API

- `POST /api/transcribe` — Submit a YouTube URL
- `GET /api/job/{id}` — Check job status
- `GET /api/job/{id}/export/{format}` — Export as SRT/LRC/VTT/JSON/CSV/TXT
- `POST /api/job/{id}/translate` — Translate lyrics
- `GET /api/docs` — Interactive API docs
