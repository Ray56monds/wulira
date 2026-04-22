"""Models — Pydantic request/response schemas"""

from typing import Any, Optional
from pydantic import BaseModel, field_validator


def _validate_youtube_url(url: str) -> str:
    import re
    if not re.match(r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/', url):
        raise ValueError("Invalid YouTube URL")
    return url


class TranscribeRequest(BaseModel):
    url: str
    language: Optional[str] = None
    model: str = "base"
    timestamps: bool = True

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _validate_youtube_url(v)

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        allowed = ["tiny", "base", "small", "medium", "large"]
        if v not in allowed:
            raise ValueError(f"Model must be one of: {', '.join(allowed)}")
        return v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 5:
            raise ValueError("Invalid language code")
        return v


class BatchTranscribeRequest(BaseModel):
    urls: list[str]
    language: Optional[str] = None
    model: str = "base"
    timestamps: bool = True

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v: list[str]) -> list[str]:
        if len(v) > 10:
            raise ValueError("Maximum 10 URLs per batch")
        if not v:
            raise ValueError("At least 1 URL required")
        return v


class TranslateRequest(BaseModel):
    from_code: str
    to_code: str
