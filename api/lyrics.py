"""
Lyrics Processing Module
Enhanced lyrics extraction, formatting, and analysis
"""

from typing import Any, Optional
from dataclasses import dataclass
import re
import math
from collections import Counter
from difflib import SequenceMatcher

# Filler words and common speech patterns to remove/minimize
FILLER_WORDS = {
    "um", "uh", "ah", "eh", "hmm", "huh",
    "like", "you know", "kind of", "sort of",
    "literally", "basically", "honestly", "right",
    "okay", "alright", "so", "well", "now",
}

COMMON_INTERRUPTIONS = {
    "[", "]", "(", ")", "music", "laughter", "applause",
    "crowd", "noise", "unintelligible", "inaudible"
}

@dataclass
class LyricsSegment:
    """Enhanced lyrics segment with metrics"""
    start: float
    end: float
    text: str
    confidence: float = 1.0
    is_chorus: bool = False
    is_filler: bool = False
    
    def duration(self) -> float:
        return self.end - self.start

class LyricsProcessor:
    """Process and enhance lyrics"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Remove noise and normalize lyrics text"""
        # Remove audio artifacts
        text = re.sub(r'\[.*?\]', '', text)  # [music], [laughter], etc.
        text = re.sub(r'\(.*?\)', '', text)  # (spoken), (whispered), etc.
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove filler words (case insensitive)
        words = text.split()
        cleaned = [w for w in words if w.lower() not in FILLER_WORDS]
        
        return ' '.join(cleaned) if cleaned else text
    
    @staticmethod
    def merge_short_segments(segments: list[dict[str, Any]], min_duration: float = 1.0) -> list[dict[str, Any]]:
        """Merge segments shorter than min_duration into neighbours"""
        if not segments:
            return segments
        merged: list[dict[str, Any]] = []
        for seg in segments:
            dur = seg.get('end', 0) - seg.get('start', 0)
            if merged and dur < min_duration:
                merged[-1]['end'] = seg['end']
                merged[-1]['text'] = f"{merged[-1]['text']} {seg['text']}".strip()
            else:
                merged.append({**seg})
        return merged

    @staticmethod
    def words_per_minute(segments: list[dict[str, Any]]) -> float:
        """Calculate average words spoken per minute"""
        if not segments:
            return 0.0
        total_words = sum(len(s['text'].split()) for s in segments)
        total_mins = (segments[-1]['end'] - segments[0]['start']) / 60
        return round(total_words / total_mins, 1) if total_mins > 0 else 0.0

    @staticmethod
    def detect_chorus(segments: list[dict[str, Any]], threshold: float = 0.8) -> list[int]:
        """
        Detect likely chorus lines using fuzzy matching.
        Returns list of segment indices that are chorus.
        """
        if not segments:
            return []
        texts = [LyricsProcessor.normalize_for_comparison(s['text']) for s in segments]
        text_counts = Counter(texts)
        chorus_indices: list[int] = []

        for i, text in enumerate(texts):
            if not text:
                continue
            # Exact duplicate
            if text_counts[text] >= 2:
                chorus_indices.append(i)
                continue
            # Fuzzy match against already-identified chorus lines
            for ci in chorus_indices:
                if SequenceMatcher(None, text, texts[ci]).ratio() >= threshold:
                    chorus_indices.append(i)
                    break
        return sorted(set(chorus_indices))
    
    @staticmethod
    def normalize_for_comparison(text: str) -> str:
        """Normalize text for comparison (detect duplicates)"""
        return re.sub(r'\W+', ' ', text.lower()).strip()
    
    @staticmethod
    def calculate_confidence(segments: list[dict[str, Any]]) -> float:
        """Calculate overall transcript confidence"""
        if not segments:
            return 0.0
        
        # Base confidence on segment count and quality
        confidence_scores = [s.get('confidence', 1.0) for s in segments]
        avg = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        
        # Adjust for coverage (fewer gaps = higher confidence)
        total_duration = segments[-1]['end'] - segments[0]['start'] if segments else 0
        segment_duration = sum(s['end'] - s['start'] for s in segments)
        coverage = segment_duration / total_duration if total_duration > 0 else 1.0
        
        return (avg * 0.7 + coverage * 0.3)
    
    @staticmethod
    def export_srt(segments: list[dict[str, Any]], metadata: dict[str, Any]) -> str:
        """Export transcript as SRT (SubRip) format"""
        lines = []
        for i, seg in enumerate(segments, 1):
            start_time = LyricsProcessor._format_srt_time(seg['start'])
            end_time = LyricsProcessor._format_srt_time(seg['end'])
            text = seg['text'].strip()
            
            if text:
                lines.append(f"{i}")
                lines.append(f"{start_time} --> {end_time}")
                lines.append(text)
                lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def export_lrc(segments: list[dict[str, Any]], metadata: dict[str, Any]) -> str:
        """Export as LRC format (Lyrics + timestamps)"""
        lines = []
        
        # Add metadata
        if title := metadata.get('title'):
            lines.append(f"[ti:{title}]")
        if artist := metadata.get('uploader'):
            lines.append(f"[ar:{artist}]")
        if duration := metadata.get('duration'):
            lines.append(f"[length:{int(duration * 1000)}]")
        
        lines.append("")
        
        # Add lyrics with timestamps
        for seg in segments:
            time_code = LyricsProcessor._format_lrc_time(seg['start'])
            text = seg['text'].strip()
            if text:
                lines.append(f"{time_code}{text}")
        
        return "\n".join(lines)
    
    @staticmethod
    def export_json(segments: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
        """Export as JSON with full metadata"""
        chorus_indices = LyricsProcessor.detect_chorus(segments)
        
        return {
            "metadata": {
                "title": metadata.get('title'),
                "artist": metadata.get('uploader'),
                "duration": metadata.get('duration'),
                "language": metadata.get('language_code'),
                "language_name": metadata.get('language_detected'),
                "confidence": LyricsProcessor.calculate_confidence(segments),
            },
            "segments": [
                {
                    **seg,
                    "is_chorus": i in chorus_indices,
                    "cleaned_text": LyricsProcessor.clean_text(seg['text'])
                }
                for i, seg in enumerate(segments)
            ],
            "statistics": {
                "total_segments": len(segments),
                "chorus_lines": len(chorus_indices),
                "unique_lines": len(set(LyricsProcessor.normalize_for_comparison(s['text']) for s in segments)),
                "total_duration": segments[-1]['end'] - segments[0]['start'] if segments else 0,
            }
        }
    
    @staticmethod
    def export_csv(segments: list[dict[str, Any]], metadata: dict[str, Any]) -> str:
        """Export as CSV"""
        lines = [
            "start_time,end_time,duration,text,word_count",
        ]
        
        for seg in segments:
            start = seg['start']
            end = seg['end']
            duration = end - start
            text = seg['text'].strip().replace('"', '""')  # Escape quotes
            word_count = len(text.split())
            
            lines.append(f"{start:.2f},{end:.2f},{duration:.2f},\"{text}\",{word_count}")
        
        return "\n".join(lines)
    
    @staticmethod
    def export_vtt(segments: list[dict[str, Any]], metadata: dict[str, Any]) -> str:
        """Export as VTT (WebVTT) format"""
        lines = ["WEBVTT", ""]
        
        for seg in segments:
            start = LyricsProcessor._format_vtt_time(seg['start'])
            end = LyricsProcessor._format_vtt_time(seg['end'])
            text = seg['text'].strip()
            
            if text:
                lines.append(f"{start} --> {end}")
                lines.append(text)
                lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        """Format time as HH:MM:SS,mmm for SRT"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    @staticmethod
    def _format_lrc_time(seconds: float) -> str:
        """Format time as [MM:SS.mm] for LRC"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        centis = int((seconds % 1) * 100)
        return f"[{minutes:02d}:{secs:02d}.{centis:02d}]"
    
    @staticmethod
    def _format_vtt_time(seconds: float) -> str:
        """Format time as HH:MM:SS.mmm for VTT"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
    
    @staticmethod
    def search_lyrics(segments: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
        """Search for phrase in lyrics"""
        query_lower = query.lower()
        results = []
        
        for i, seg in enumerate(segments):
            if query_lower in seg['text'].lower():
                results.append({
                    "index": i,
                    "timestamp": seg['start'],
                    "text": seg['text'],
                    "context_before": segments[i-1]['text'] if i > 0 else "",
                    "context_after": segments[i+1]['text'] if i < len(segments) - 1 else "",
                })
        
        return results
    
    @staticmethod
    def get_statistics(segments: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate lyrics statistics"""
        all_text = " ".join(s['text'] for s in segments)
        words = all_text.split()
        word_freq = Counter(w.lower() for w in words)
        total_dur = segments[-1]['end'] - segments[0]['start'] if segments else 0
        chorus = LyricsProcessor.detect_chorus(segments)

        return {
            "total_segments": len(segments),
            "total_words": len(words),
            "unique_words": len(set(w.lower() for w in words)),
            "vocabulary_richness": round(len(set(w.lower() for w in words)) / len(words), 3) if words else 0,
            "words_per_minute": LyricsProcessor.words_per_minute(segments),
            "avg_words_per_segment": round(len(words) / len(segments), 1) if segments else 0,
            "total_duration": round(total_dur, 2),
            "avg_segment_duration": round(total_dur / len(segments), 2) if segments else 0,
            "most_common_words": dict(word_freq.most_common(10)),
            "chorus_indices": chorus,
            "chorus_percentage": round(len(chorus) / len(segments) * 100, 1) if segments else 0,
        }
