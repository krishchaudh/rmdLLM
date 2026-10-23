"""Parser for transcripts copied from the YouTube transcript panel.

Each line is: ``<compact time><accessibility label><text>`` with no separators, e.g.

    0:000 secondsदो प्रकार के कर्म होते हैं।
    0:055 secondsएक भौतिक, एक आध्यात्मिक
    1:231 minute, 23 secondsअर्थात दिव्य कर्म गुणातीत कर्म
    20:0820 minutes, 8 secondsलगाओ लगाओ।

The compact time (``M:SS`` or ``H:MM:SS``) is immediately followed by its spoken-form duplicate
(``N minutes, N seconds`` / ``N hour, ...``) and then the caption text. Both forms are parsed and must
agree; disagreement or an unparseable line is reported explicitly — a timestamp is never guessed.

The current YouTube panel copies as alternating lines instead (timestamp on its own line, caption
on the next): ``0:00\nदो प्रकार के कर्म होते हैं।\n0:05\n...``. Standard formats (``M:SS text``, SRT,
VTT) are accepted as well.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_WORD_TIME = re.compile(
    r"^(?:(?P<h>\d+)\s*hours?,?\s*)?(?:(?P<m>\d+)\s*minutes?,?\s*)?(?:(?P<s>\d+)\s*seconds?)?",
    re.UNICODE,
)
_COMPACT = re.compile(r"^(?P<time>\d{1,2}:\d{2}(?::\d{2})?)")
_SIMPLE = re.compile(r"^(?P<time>\d{1,2}:\d{2}(?::\d{2})?)[\s\-–>]+(?P<text>\S.*)$")
_TIME_ONLY = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")
_SRT_TS = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)


@dataclass
class Segment:
    start_seconds: int
    text: str
    raw_line: str
    end_seconds: int | None = None
    line_number: int = 0

    def to_dict(self) -> dict:
        return {
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "text": self.text,
        }


@dataclass
class ParseIssue:
    line_number: int
    raw_line: str
    reason: str


@dataclass
class ParseResult:
    segments: list[Segment] = field(default_factory=list)
    issues: list[ParseIssue] = field(default_factory=list)
    format: str = "unknown"

    @property
    def ok(self) -> bool:
        return bool(self.segments) and not self.issues


class TranscriptParseError(ValueError):
    pass


def _compact_to_seconds(t: str) -> int:
    parts = [int(p) for p in t.split(":")]
    if len(parts) == 2:
        m, s = parts
        h = 0
    else:
        h, m, s = parts
    if s >= 60 or m >= 60:
        raise TranscriptParseError(f"invalid compact time {t!r}")
    return h * 3600 + m * 60 + s


def _spoken_duplicate(rest: str) -> tuple[int | None, str]:
    """Parse the leading 'N minutes, N seconds' label. Returns (seconds, remaining_text).

    Returns (None, rest) if no spoken label is present."""
    m = _WORD_TIME.match(rest)
    if not m or not m.group(0).strip():
        return None, rest
    if m.group("h") is None and m.group("m") is None and m.group("s") is None:
        return None, rest
    h = int(m.group("h") or 0)
    mi = int(m.group("m") or 0)
    s = int(m.group("s") or 0)
    return h * 3600 + mi * 60 + s, rest[m.end() :]


def parse_youtube_panel_line(line: str) -> tuple[int, str]:
    """Parse one line of the YouTube panel format. Raises TranscriptParseError on ambiguity.

    >>> parse_youtube_panel_line("1:231 minute, 23 secondsअर्थात दिव्य कर्म गुणातीत कर्म")
    (83, 'अर्थात दिव्य कर्म गुणातीत कर्म')
    """
    s = line.strip()
    m = _COMPACT.match(s)
    if not m:
        raise TranscriptParseError("line does not start with a timestamp")
    compact = m.group("time")
    rest = s[m.end() :]

    # Compact time is M:SS (or H:MM:SS); the spoken duplicate immediately follows with no separator.
    # Because "0:055 seconds" is ambiguous ("0:05" + "5 seconds" vs "0:055"), the compact regex
    # already took exactly two digits after the colon; what follows belongs to the spoken label.
    spoken, text = _spoken_duplicate(rest)
    start = _compact_to_seconds(compact)
    if spoken is None:
        # Plain "M:SS text" with whitespace separator.
        if rest.strip() == "":
            raise TranscriptParseError("empty caption text")
        if rest[:1].isspace():
            return start, rest.strip()
        raise TranscriptParseError("timestamp not followed by spoken label or whitespace")
    if spoken != start:
        raise TranscriptParseError(
            f"compact time {compact!r} ({start}s) disagrees with spoken label ({spoken}s)"
        )
    text = text.strip()
    if not text:
        raise TranscriptParseError("empty caption text")
    return start, text


def _detect_format(lines: list[str]) -> str:
    stripped = [ln.strip() for ln in lines if ln.strip()]
    if not stripped:
        return "empty"
    if stripped[0].upper().startswith("WEBVTT"):
        return "vtt"
    if any(_SRT_TS.match(ln) for ln in stripped[:5]):
        return "srt"
    panel_like = sum(
        1 for ln in stripped if _COMPACT.match(ln) and re.search(r"(second|minute|hour)", ln[:40])
    )
    if panel_like >= max(1, len(stripped) // 2):
        return "youtube_panel"
    if sum(1 for ln in stripped if _SIMPLE.match(ln)) >= max(1, len(stripped) // 2):
        return "simple"
    time_only = sum(1 for ln in stripped if _TIME_ONLY.match(ln))
    if time_only >= 2 and time_only >= len(stripped) // 3:
        return "youtube_panel_lines"
    return "unknown"


def _parse_panel_lines(lines: list[str]) -> ParseResult:
    """Alternating-line panel format: a bare timestamp line followed by its caption line(s)."""
    result = ParseResult(format="youtube_panel_lines")
    pending: tuple[int, str, int] | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal pending, buf
        if pending is None:
            return
        start, raw, line_no = pending
        text = " ".join(buf).strip()
        if text:
            result.segments.append(Segment(start, text, raw, None, line_no))
        else:
            result.issues.append(ParseIssue(line_no, raw, "timestamp without caption text"))
        pending, buf = None, []

    for idx, ln in enumerate(lines, start=1):
        s = ln.strip()
        if not s:
            continue
        if _TIME_ONLY.match(s):
            flush()
            try:
                pending = (_compact_to_seconds(s), s, idx)
            except TranscriptParseError as exc:
                result.issues.append(ParseIssue(idx, s, str(exc)))
        elif pending is None:
            result.issues.append(ParseIssue(idx, s, "caption text before any timestamp"))
        else:
            buf.append(s)
    flush()
    return result


def _parse_srt_vtt(lines: list[str], fmt: str) -> ParseResult:
    result = ParseResult(format=fmt)
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i].strip()
        m = _SRT_TS.match(ln)
        if m:
            g = [int(x) for x in m.groups()]
            start = g[0] * 3600 + g[1] * 60 + g[2]
            end = g[4] * 3600 + g[5] * 60 + g[6]
            i += 1
            buf: list[str] = []
            while i < n and lines[i].strip():
                buf.append(lines[i].strip())
                i += 1
            text = " ".join(buf).strip()
            if text:
                result.segments.append(Segment(start, text, ln, end, i))
        else:
            i += 1
    return result


def parse_transcript(raw: str) -> ParseResult:
    """Parse a pasted transcript. Never raises; malformed lines are reported in ``issues``."""
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    fmt = _detect_format(lines)
    if fmt == "empty":
        return ParseResult(format=fmt, issues=[ParseIssue(0, "", "transcript is empty")])
    if fmt in ("srt", "vtt"):
        result = _parse_srt_vtt(lines, fmt)
    elif fmt == "youtube_panel_lines":
        result = _parse_panel_lines(lines)
    else:
        result = ParseResult(format=fmt)
        for idx, ln in enumerate(lines, start=1):
            s = ln.strip()
            if not s:
                continue
            try:
                if fmt == "youtube_panel":
                    start, text = parse_youtube_panel_line(s)
                else:
                    m = _SIMPLE.match(s)
                    if not m:
                        raise TranscriptParseError("line does not match 'M:SS text'")
                    start, text = _compact_to_seconds(m.group("time")), m.group("text").strip()
            except TranscriptParseError as exc:
                result.issues.append(ParseIssue(idx, s, str(exc)))
                continue
            result.segments.append(Segment(start, text, s, None, idx))

    # Order check + end times from the following segment.
    for a, b in zip(result.segments, result.segments[1:], strict=False):
        if b.start_seconds < a.start_seconds:
            result.issues.append(ParseIssue(b.line_number, b.raw_line, "timestamp goes backwards"))
        if a.end_seconds is None:
            a.end_seconds = b.start_seconds
    return result
