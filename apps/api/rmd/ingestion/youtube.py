"""YouTube helpers: video-id extraction and optional (never blocking) metadata lookup via oEmbed."""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_PATTERNS = [
    re.compile(r"(?:v=|/v/|/embed/|/shorts/|/live/|youtu\.be/)([A-Za-z0-9_-]{11})"),
]


def extract_video_id(url_or_id: str) -> str | None:
    s = url_or_id.strip()
    if _ID_RE.match(s):
        return s
    for p in _PATTERNS:
        m = p.search(s)
        if m:
            return m.group(1)
    return None


def canonical_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def timestamp_url(video_id: str, seconds: int) -> str:
    return f"https://www.youtube.com/watch?v={video_id}&t={int(seconds)}s"


@dataclass
class VideoMetadata:
    title: str | None = None
    channel: str | None = None
    thumbnail_url: str | None = None
    status: str = "not_fetched"  # fetched | unavailable | not_fetched


def fetch_metadata(video_id: str, timeout: float = 5.0) -> VideoMetadata:
    """Best-effort oEmbed lookup (no API key). Failure is recorded, never raised."""
    try:
        r = httpx.get(
            "https://www.youtube.com/oembed",
            params={"url": canonical_url(video_id), "format": "json"},
            timeout=timeout,
        )
        if r.status_code != 200:
            return VideoMetadata(status="unavailable")
        data = r.json()
        return VideoMetadata(
            title=data.get("title"),
            channel=data.get("author_name"),
            thumbnail_url=data.get("thumbnail_url"),
            status="fetched",
        )
    except Exception:  # noqa: BLE001
        return VideoMetadata(status="unavailable")
