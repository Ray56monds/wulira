# 🎵 Wulira Lyrics Features (v1.2.0)

> A complete system for professional-grade lyrics extraction with advanced processing, export formats, and analysis tools.

---

## 🌟 New Features Overview

### 1. **Multiple Export Formats**
Export transcripts in industry-standard formats:
- **SRT** - SubRip format for video subtitles
- **LRC** - Lyrics for music players with timing
- **VTT** - WebVTT for web players
- **JSON** - Structured data with full metadata
- **CSV** - Spreadsheet format for analysis
- **TXT** - Plain text (default)

### 2. **Lyrics Processing**
- **Clean text** - Remove filler words and audio artifacts
- **Chorus detection** - Identify repeated sections
- **Quality metrics** - Confidence scores per segment
- **Duplication check** - Find duplicate lyrics

### 3. **Advanced Search**
- Search within lyrics
- Context extraction (lines before/after)
- Timestamp-based results

### 4. **Lyrics Statistics**
- Word frequency analysis
- Most common phrases
- Coverage metrics
- Segment analysis
- Chorus detection

### 5. **Batch Processing**
- Submit up to 10 URLs at once
- Process multiple videos in parallel
- Get all job IDs for tracking

---

## 📚 CLI Usage

### Basic Transcription
```bash
python wulira.py "https://youtube.com/watch?v=..."
```

### Export Formats
```bash
# Export as SRT (for subtitles)
python wulira.py <URL> --format srt --output lyrics.srt

# Export as LRC (for music players)
python wulira.py <URL> --format lrc --output lyrics.lrc

# Export as JSON (full data)
python wulira.py <URL> --format json --output lyrics.json

# Export as CSV (analysis)
python wulira.py <URL> --format csv --output lyrics.csv

# Export as VTT (web subtitles)
python wulira.py <URL> --format vtt --output lyrics.vtt
```

### Text Processing
```bash
# Clean filler words
python wulira.py <URL> --clean

# Show statistics
python wulira.py <URL> --stats

# Both combined
python wulira.py <URL> --clean --stats --format json --output lyrics.json
```

### Examples
```bash
# Full workflow: transcribe, clean, analyze
python wulira.py "https://youtube.com/watch?v=xxx" \
  --model medium \
  --language en \
  --clean \
  --stats \
  --format json \
  --output transcript.json

# Export Luganda lyrics as SRT subtitles
python wulira.py "https://youtube.com/watch?v=yyy" \
  --language lg \
  --format srt \
  --output luganda_lyrics.srt

# Detect language only
python wulira.py "https://youtube.com/watch?v=zzz" --detect-only
```

---

## 🔗 API Endpoints

### Submit Transcription
```bash
POST /api/transcribe
Content-Type: application/json

{
  "url": "https://youtube.com/watch?v=...",
  "language": "en",        # optional, auto-detected
  "model": "base",         # tiny, base, small, medium, large
  "timestamps": true
}

Response:
{
  "job_id": "uuid",
  "status": "queued"
}
```

### Get Job Status
```bash
GET /api/job/{job_id}

Response:
{
  "job_id": "uuid",
  "status": "done",
  "created_at": "2026-04-21T...",
  "title": "Song Title",
  "uploader": "Artist Name",
  "duration": 180,
  "language_detected": "English",
  "language_code": "en",
  "language_confidence": 95.5,
  "language_top5": [...],
  "transcript": [
    {"start": 0.0, "end": 2.5, "text": "First lyrics line"},
    {"start": 2.5, "end": 5.0, "text": "Second lyrics line"},
    ...
  ]
}
```

### Export Transcript
```bash
GET /api/job/{job_id}/export/{format}

# Available formats: srt, lrc, vtt, json, csv, txt

Response:
# SRT format:
1
00:00:00,000 --> 00:00:02,500
First lyrics line

2
00:00:02,500 --> 00:00:05,000
Second lyrics line

# LRC format:
[ti:Song Title]
[ar:Artist Name]
[length:180000]

[00:00.00]First lyrics line
[00:02.50]Second lyrics line

# JSON format:
{
  "metadata": {...},
  "segments": [...],
  "statistics": {...}
}
```

### Search Lyrics
```bash
GET /api/job/{job_id}/search?q=love

Response:
{
  "query": "love",
  "results_count": 5,
  "results": [
    {
      "index": 0,
      "timestamp": 0.5,
      "text": "I love you",
      "context_before": "",
      "context_after": "More than words can say"
    },
    ...
  ],
  "title": "Song Title",
  "language": "English"
}
```

### Lyrics Statistics
```bash
GET /api/job/{job_id}/lyrics-stats

Response:
{
  "job_id": "uuid",
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
      ...
    },
    "chorus_indices": [5, 6, 7, 25, 26, 27, ...]
  },
  "overall_confidence": 0.92
}
```

### Batch Transcribe
```bash
POST /api/batch-transcribe
Content-Type: application/json

{
  "urls": [
    "https://youtube.com/watch?v=xxx",
    "https://youtube.com/watch?v=yyy",
    "https://youtube.com/watch?v=zzz"
  ],
  "language": "en",
  "model": "base",
  "timestamps": true
}

Response:
{
  "batch_id": "uuid",
  "job_ids": ["uuid1", "uuid2", "uuid3"],
  "count": 3,
  "status": "queued"
}

# Then track each job individually with /api/job/{job_id}
```

---

## 📊 Export Format Details

### SRT (SubRip)
Used for video subtitles. Compatible with:
- YouTube
- VLC Media Player
- Adobe Premiere
- Most video editing software

```srt
1
00:00:00,000 --> 00:00:02,500
First lyrics line

2
00:00:02,500 --> 00:00:05,000
Second lyrics line
```

### LRC (Lyrics)
Used by music players. Compatible with:
- foobar2000
- winamp
- iTunes (with plugin)
- Android music apps

```lrc
[ti:Song Title]
[ar:Artist Name]
[length:180000]

[00:00.00]First lyrics line
[00:02.50]Second lyrics line
```

### VTT (WebVTT)
Modern web subtitle format. Compatible with:
- HTML5 `<video>` tags
- YouTube
- Most streaming platforms

```vtt
WEBVTT

00:00:00.000 --> 00:00:02.500
First lyrics line

00:00:02.500 --> 00:00:05.000
Second lyrics line
```

### JSON
Structured format with full metadata. Useful for:
- Integration with applications
- Data analysis
- Custom processing

```json
{
  "metadata": {
    "title": "Song Title",
    "artist": "Artist Name",
    "duration": 180,
    "language": "en",
    "confidence": 0.92
  },
  "segments": [
    {
      "start": 0.0,
      "end": 2.5,
      "text": "First lyrics line",
      "is_chorus": false,
      "cleaned_text": "First lyrics line"
    }
  ],
  "statistics": {
    "total_segments": 45,
    "chorus_lines": 8,
    "unique_lines": 37
  }
}
```

### CSV
Spreadsheet format. Useful for:
- Analysis in Excel/Google Sheets
- Data processing in Python/R
- Database import

```csv
start_time,end_time,duration,text,word_count
0.00,2.50,2.50,"First lyrics line",3
2.50,5.00,2.50,"Second lyrics line",3
```

---

## 🔍 Lyrics Processing

### Filler Word Removal
Automatically removes common filler words:
- Speech markers: "um", "uh", "ah", "eh"
- Qualifiers: "like", "kind of", "sort of", "basically"
- Discourse markers: "you know", "I mean", "right?"

**Example:**
```
Before: "Um, like, you know, I love you so much"
After:  "I love you so much"
```

### Audio Artifact Removal
Removes non-speech elements:
- `[music]`, `[laughter]`, `[applause]`
- `(spoken)`, `(whispered)`, `(unintelligible)`

**Example:**
```
Before: "[music] He said (whispered) I love you [applause]"
After:  "He said I love you"
```

### Chorus Detection
Identifies repeated sections of lyrics. Uses:
- Text similarity matching
- Frequency analysis
- Duration-based heuristics

**Output:**
- Indices of chorus lines
- Can be used to highlight or isolate chorus

---

## 📈 Statistics & Analysis

### Word Frequency
Shows most common words in the lyrics. Useful for:
- Theme identification
- SEO optimization
- Lyrical pattern analysis

**Example:**
```json
"most_common_words": {
  "love": 12,
  "heart": 8,
  "night": 7,
  "star": 6,
  "dream": 5
}
```

### Coverage Analysis
Percentage of video covered by actual lyrics (vs. silence/music).

```
Total duration: 180 seconds
Lyrics duration: 160 seconds
Coverage: 88.9%
```

### Confidence Score
Overall quality metric (0-1) based on:
- Individual segment confidence
- Coverage percentage
- Segment consistency

### Segment Analysis
Average metrics per segment:
- Words per segment
- Duration per segment
- Repetition patterns

---

## 🚀 Advanced Usage

### Integration with Other Tools

#### YouTube Subtitles
```bash
# Create subtitle file
python wulira.py "https://youtube.com/watch?v=xxx" \
  --format srt \
  --output video.srt

# Import to YouTube via upload interface
```

#### Music Metadata
```bash
# Export JSON for music library
python wulira.py "https://youtube.com/watch?v=xxx" \
  --format json \
  --output song.json

# Use with music tagger (MusicBrainz, etc.)
```

#### Lyrics Database
```bash
# CSV export for database
python wulira.py "https://youtube.com/watch?v=xxx" \
  --format csv \
  --output lyrics.csv

# Import to database for lyrics site
```

---

## ⚙️ Configuration

### Environment Variables
```env
# Lyrics settings
MAX_VIDEO_DURATION_SECONDS=7200
DEFAULT_WHISPER_MODEL=base

# Job settings
MAX_JOBS_IN_MEMORY=100
JOB_TIMEOUT_SECONDS=3600
```

### Model Selection
- **tiny** - Fastest, lowest accuracy
- **base** - Default, good balance
- **small** - Better accuracy
- **medium** - High accuracy
- **large** - Best accuracy, slowest

### Language Support
99+ languages supported, optimized for:
- 🇺🇬 Luganda (lg)
- 🇰🇪 Kiswahili (sw)
- 🇬🇧 English (en)
- And 96 more...

---

## 🎯 Use Cases

### 1. **Karaoke Creation**
```bash
python wulira.py <song_url> --format lrc --output karaoke.lrc
# Import to karaoke software
```

### 2. **Subtitle Generation**
```bash
python wulira.py <video_url> --format srt --output subtitles.srt
# Upload to video platform
```

### 3. **Lyrics Website**
```bash
python wulira.py <url> --format json --output lyrics.json
# Integrate with lyrics database
```

### 4. **Accessibility**
```bash
python wulira.py <audio_url> --format vtt --output captions.vtt
# Add to website for accessibility
```

### 5. **Research/Analysis**
```bash
python wulira.py <url> --format json --stats
# Analyze lyrics structure, themes, etc.
```

### 6. **Translation Project**
```bash
python wulira.py <url> --format json --output source.json
# Use JSON for translation platform
```

---

## 🔧 Troubleshooting

### Issue: Export format not recognized
```bash
# Use valid formats only
✓ srt, lrc, vtt, json, csv, txt
✗ subtitle, lyrics, data
```

### Issue: Search returns no results
```bash
# Ensure job is complete (status="done")
# Search is case-insensitive, so "love" finds "Love" and "LOVE"
# Try shorter query terms
```

### Issue: Statistics show 0 confidence
```bash
# Confidence depends on:
# - Segment count (more = higher)
# - Coverage percentage (higher = better)
# - Use higher model for better accuracy
```

---

## 📝 Examples

### Complete Workflow
```bash
# 1. Extract lyrics as JSON with statistics
python wulira.py "https://youtube.com/watch?v=xxx" \
  --model medium \
  --clean \
  --stats \
  --format json \
  --output lyrics.json

# 2. Export as SRT for subtitles
python wulira.py "https://youtube.com/watch?v=xxx" \
  --format srt \
  --output lyrics.srt

# 3. Export as LRC for music player
python wulira.py "https://youtube.com/watch?v=xxx" \
  --format lrc \
  --output lyrics.lrc
```

### API Workflow
```bash
# 1. Submit job
curl -X POST http://localhost:8000/api/transcribe \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=xxx"}'

# Response: {"job_id": "abc123", "status": "queued"}

# 2. Wait and check status
curl http://localhost:8000/api/job/abc123

# 3. Export as SRT
curl http://localhost:8000/api/job/abc123/export/srt > lyrics.srt

# 4. Get statistics
curl http://localhost:8000/api/job/abc123/lyrics-stats

# 5. Search lyrics
curl "http://localhost:8000/api/job/abc123/search?q=love"
```

---

## 🎊 Summary

Wulira now provides a **production-ready lyrics extraction system** with:

✅ Multiple export formats (SRT, LRC, VTT, JSON, CSV, TXT)  
✅ Intelligent text processing (filler removal, artifact detection)  
✅ Advanced search capabilities  
✅ Comprehensive statistics and analysis  
✅ Batch processing support  
✅ Full API for integration  
✅ CLI tools for command-line users  
✅ 99+ language support  

Perfect for:
- **Karaoke creators** - Create LRC files instantly
- **Video editors** - Generate SRT subtitles
- **Music apps** - Export JSON for integration
- **Researchers** - Analyze lyrics with statistics
- **Accessibility** - Create VTT captions
- **Translators** - Export for translation

---

## 🔄 Version History

### v1.2.0 (Latest)
- ✨ Multiple export formats
- ✨ Lyrics processing & cleaning
- ✨ Advanced search API
- ✨ Statistics & analysis
- ✨ Batch processing
- ✨ CLI format support

### v1.1.0
- ✅ Security improvements
- ✅ Configuration management
- ✅ Logging & monitoring
- ✅ Job expiration

### v1.0.0
- 🎵 Basic transcription
- 🌍 Multi-language support
- 🎯 Whisper integration
