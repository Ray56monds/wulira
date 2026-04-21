# 📖 Wulira API Reference

## Base URL
```
http://localhost:8000
Development: http://localhost:8000/api/docs
```

---

## ✅ Health Check

### Endpoint
```http
GET /api/health
```

### Response
```json
{
  "status": "ok",
  "service": "Wulira API",
  "tagline": "Hear every word, in every language.",
  "version": "1.1.0"
}
```

---

## 🎵 Transcription

### Submit Job
```http
POST /api/transcribe
Content-Type: application/json
```

#### Request
```json
{
  "url": "https://youtube.com/watch?v=XXXXX",
  "language": "en",
  "model": "base",
  "timestamps": true
}
```

#### Parameters
| Field | Type | Required | Options | Default | Description |
|-------|------|----------|---------|---------|-------------|
| url | string | ✅ | Valid YouTube URL | - | Video to transcribe |
| language | string | ❌ | Language code (lg, sw, en, etc.) | auto | Override auto-detection |
| model | string | ❌ | tiny, base, small, medium, large | base | Model accuracy/speed |
| timestamps | boolean | ❌ | true, false | true | Include time codes |

#### Response (Success)
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued"
}
```

#### Response (Error)
```json
{
  "detail": "Invalid YouTube URL"
}
```

Status Codes:
- `200` - Job queued successfully
- `400` - Invalid request
- `429` - Queue full, try later

---

## 📊 Get Job Status

### Endpoint
```http
GET /api/job/{job_id}
```

#### Response (Queued)
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "created_at": "2026-04-21T10:30:00"
}
```

#### Response (Processing)
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "created_at": "2026-04-21T10:30:00"
}
```

#### Response (Complete)
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "done",
  "created_at": "2026-04-21T10:30:00",
  "title": "Song Title",
  "uploader": "Artist Name",
  "duration": 180,
  "language_detected": "English",
  "language_code": "en",
  "language_confidence": 95.5,
  "language_top5": [
    {"code": "en", "name": "English", "confidence": 95.5},
    {"code": "fr", "name": "French", "confidence": 2.1}
  ],
  "timestamps": true,
  "transcript": [
    {
      "start": 0.0,
      "end": 2.5,
      "text": "First line of lyrics"
    },
    {
      "start": 2.5,
      "end": 5.0,
      "text": "Second line of lyrics"
    }
  ]
}
```

#### Response (Error)
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "error",
  "error_type": "validation|file|processing",
  "error": "Error description",
  "created_at": "2026-04-21T10:30:00"
}
```

Status Codes:
- `200` - Job found
- `404` - Job not found or expired

---

## 💾 Export Transcript

### Endpoint
```http
GET /api/job/{job_id}/export/{format}
```

#### Formats
| Format | MIME Type | Use Case |
|--------|-----------|----------|
| srt | text/plain | Video subtitles |
| lrc | text/plain | Music player lyrics |
| vtt | text/vtt | Web subtitles |
| json | application/json | Data integration |
| csv | text/csv | Spreadsheet analysis |
| txt | text/plain | Plain text |

#### Examples

**SRT Export**
```http
GET /api/job/abc123/export/srt
```

Response:
```
1
00:00:00,000 --> 00:00:02,500
First line of lyrics

2
00:00:02,500 --> 00:00:05,000
Second line of lyrics
```

**LRC Export**
```http
GET /api/job/abc123/export/lrc
```

Response:
```
[ti:Song Title]
[ar:Artist Name]
[length:180000]

[00:00.00]First line of lyrics
[00:02.50]Second line of lyrics
```

**JSON Export**
```http
GET /api/job/abc123/export/json
```

Response:
```json
{
  "metadata": {
    "title": "Song Title",
    "artist": "Artist Name",
    "duration": 180,
    "language": "en",
    "confidence": 0.92
  },
  "segments": [...],
  "statistics": {...}
}
```

Status Codes:
- `200` - Export successful
- `400` - Job not complete
- `404` - Job not found

---

## 🔍 Search Lyrics

### Endpoint
```http
GET /api/job/{job_id}/search?q={query}
```

#### Query Parameters
| Parameter | Type | Required | Example |
|-----------|------|----------|---------|
| q | string | ✅ | "love" |

#### Response
```json
{
  "query": "love",
  "results_count": 3,
  "results": [
    {
      "index": 5,
      "timestamp": 12.5,
      "text": "I love you so much",
      "context_before": "Previous line",
      "context_after": "Next line"
    },
    {
      "index": 27,
      "timestamp": 65.3,
      "text": "Love is all we need",
      "context_before": "Nothing else matters",
      "context_after": "In this world"
    }
  ],
  "title": "Song Title",
  "language": "English"
}
```

Status Codes:
- `200` - Search completed
- `400` - Query too short (min 2 chars)
- `404` - Job not found

---

## 📈 Lyrics Statistics

### Endpoint
```http
GET /api/job/{job_id}/lyrics-stats
```

#### Response
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Song Title",
  "language": "English",
  "statistics": {
    "total_segments": 45,
    "total_words": 523,
    "unique_words": 187,
    "avg_words_per_segment": 11.6,
    "total_duration": 180.0,
    "avg_segment_duration": 4.0,
    "most_common_words": {
      "love": 8,
      "heart": 6,
      "night": 5,
      "dream": 4,
      "star": 3
    },
    "chorus_indices": [5, 6, 7, 25, 26, 27]
  },
  "overall_confidence": 0.92
}
```

Status Codes:
- `200` - Stats generated
- `400` - Job not complete
- `404` - Job not found

---

## 📦 Batch Transcribe

### Endpoint
```http
POST /api/batch-transcribe
Content-Type: application/json
```

#### Request
```json
{
  "urls": [
    "https://youtube.com/watch?v=XXX",
    "https://youtube.com/watch?v=YYY",
    "https://youtube.com/watch?v=ZZZ"
  ],
  "language": "en",
  "model": "base",
  "timestamps": true
}
```

#### Parameters
| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| urls | array | ✅ | 1-10 URLs, valid YouTube |
| language | string | ❌ | Language code |
| model | string | ❌ | tiny, base, small, medium, large |
| timestamps | boolean | ❌ | Default true |

#### Response
```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440001",
  "job_ids": [
    "550e8400-e29b-41d4-a716-446655440002",
    "550e8400-e29b-41d4-a716-446655440003",
    "550e8400-e29b-41d4-a716-446655440004"
  ],
  "count": 3,
  "status": "queued"
}
```

Status Codes:
- `200` - Batch queued
- `400` - Invalid URLs or params
- `429` - Queue full

---

## 📊 API Statistics

### Endpoint
```http
GET /api/stats
```

#### Response
```json
{
  "total_jobs": 15,
  "processing": 2,
  "done": 11,
  "errors": 2,
  "models_cached": ["base", "medium"],
  "environment": "development"
}
```

---

## 🔄 Status Values

| Status | Meaning | Action |
|--------|---------|--------|
| `queued` | Waiting to process | Wait and retry |
| `processing` | Currently transcribing | Wait and retry |
| `done` | Complete, ready to use | Access results |
| `error` | Failed, see error message | Check error_type |

---

## 🔐 Error Responses

### Format
```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common Errors

**Invalid URL**
```json
{
  "detail": "Invalid YouTube URL"
}
```

**Queue Full**
```json
{
  "detail": "Job queue full. Please try again later."
}
```

**Job Not Found**
```json
{
  "detail": "Job not found or has expired"
}
```

**Cannot Export**
```json
{
  "detail": "Cannot export - job status is 'processing'"
}
```

**Invalid Format**
```json
{
  "detail": "Unknown format: xyz"
}
```

---

## 🚀 Usage Examples

### Curl

**Submit transcription**
```bash
curl -X POST http://localhost:8000/api/transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://youtube.com/watch?v=...",
    "model": "base",
    "language": "en"
  }'
```

**Get job status**
```bash
curl http://localhost:8000/api/job/550e8400-e29b-41d4-a716-446655440000
```

**Export as SRT**
```bash
curl http://localhost:8000/api/job/550e8400-e29b-41d4-a716-446655440000/export/srt \
  -o lyrics.srt
```

**Search lyrics**
```bash
curl "http://localhost:8000/api/job/550e8400-e29b-41d4-a716-446655440000/search?q=love"
```

### Python

```python
import requests

# Submit job
response = requests.post('http://localhost:8000/api/transcribe', json={
    'url': 'https://youtube.com/watch?v=...',
    'model': 'base'
})
job_id = response.json()['job_id']

# Poll for completion
import time
while True:
    status = requests.get(f'http://localhost:8000/api/job/{job_id}')
    if status.json()['status'] == 'done':
        break
    time.sleep(2)

# Export as JSON
result = requests.get(f'http://localhost:8000/api/job/{job_id}/export/json')
lyrics_data = result.json()

# Search
search = requests.get(
    f'http://localhost:8000/api/job/{job_id}/search',
    params={'q': 'love'}
)
results = search.json()['results']
```

### JavaScript

```javascript
// Submit job
const response = await fetch('http://localhost:8000/api/transcribe', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    url: 'https://youtube.com/watch?v=...',
    model: 'base'
  })
});

const { job_id } = await response.json();

// Poll for completion
let job = {};
while (job.status !== 'done') {
  const res = await fetch(`http://localhost:8000/api/job/${job_id}`);
  job = await res.json();
  await new Promise(r => setTimeout(r, 2000));
}

// Export as JSON
const exportRes = await fetch(`http://localhost:8000/api/job/${job_id}/export/json`);
const lyricsData = await exportRes.json();

// Search
const searchRes = await fetch(
  `http://localhost:8000/api/job/${job_id}/search?q=love`
);
const results = await searchRes.json();
```

---

## ⏱️ Rate Limiting & Quotas

| Item | Limit | Notes |
|------|-------|-------|
| Concurrent jobs | 100 | Configurable |
| Job timeout | 1 hour | Auto-cleanup |
| Batch size | 10 URLs | Per request |
| Video duration | 2 hours | Maximum |
| Query length | 2+ chars | Search |

---

## 🔌 Integration Points

### Webhooks (Future)
Coming in v1.3 - Job completion callbacks

### Rate Limiting (Future)
Coming in v1.3 - Per-IP/API-key limits

### Authentication (Future)
Coming in v1.3 - API key support

---

## 📝 Changelog

### v1.2.0
- Added export endpoints (SRT, LRC, VTT, JSON, CSV)
- Added search endpoint
- Added statistics endpoint
- Added batch transcribe endpoint

### v1.1.0
- Added CORS configuration
- Added URL validation
- Added comprehensive error handling

### v1.0.0
- Initial API release
- Basic transcription
- Job management
