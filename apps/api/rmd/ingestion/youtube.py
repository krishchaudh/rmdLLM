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


class TranscriptFetchError(Exception):
    pass


def _fmt_time(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def fetch_transcript(video_id: str, languages: tuple[str, ...] = ("hi", "en")) -> tuple[str, str]:
    """Fetch YouTube captions and return (``M:SS text`` lines, language code).

    Best effort: YouTube blocks most cloud IPs, so callers must offer manual paste as a fallback.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            NoTranscriptFound,
            TranscriptsDisabled,
            VideoUnavailable,
        )
    except ImportError as exc:  # pragma: no cover
        raise TranscriptFetchError("transcript fetching is not installed") from exc
    try:
        api = YouTubeTranscriptApi()
        listing = api.list(video_id)
        try:
            transcript = listing.find_transcript(list(languages))
        except NoTranscriptFound:
            transcript = next(iter(listing))
        fetched = transcript.fetch()
    except (TranscriptsDisabled, VideoUnavailable) as exc:
        raise TranscriptFetchError("this video has no captions available") from exc
    except Exception as exc:  # noqa: BLE001
        name = type(exc).__name__
        if name in ("IpBlocked", "RequestBlocked"):
            raise TranscriptFetchError(
                "YouTube blocked the server's request (cloud IPs are often blocked). "
                "Open the video, click “Show transcript”, copy it and paste it below."
            ) from exc
        raise TranscriptFetchError(f"could not fetch captions ({name})") from exc
    lines = [
        f"{_fmt_time(snip.start)} {' '.join(snip.text.split())}"
        for snip in fetched
        if snip.text.strip()
    ]
    if not lines:
        raise TranscriptFetchError("captions were empty")
    return "\n".join(lines), fetched.language_code
