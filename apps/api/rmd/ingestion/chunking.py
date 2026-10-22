"""Chunking for books (page text) and lectures (timestamped segments).

Chunks are the retrieval unit. Each chunk carries a `locator` dict that maps back to exact citation
coordinates so the UI can open the PDF page or the YouTube timestamp.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import tiktoken

_enc = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_enc.encode(text))


@dataclass
class ChunkDraft:
    text: str
    locator: dict
    token_count: int


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?।॥])\s+")


def normalize_text(text: str) -> str:
    """Whitespace-only normalisation: never changes words, diacritics or Devanagari."""
    text = text.replace("\u00ad", "")  # soft hyphen
    text = re.sub(r"-\n(?=[a-z])", "", text)  # de-hyphenate line-wrapped words
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _paragraphs(text: str) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out: list[str] = []
    for p in paras:
        # join single newlines inside a paragraph (OCR line breaks)
        out.append(re.sub(r"\s*\n\s*", " ", p))
    return out


def _split_long(text: str, max_tokens: int) -> list[str]:
    sentences = _SENTENCE_SPLIT.split(text)
    pieces: list[str] = []
    cur: list[str] = []
    cur_tokens = 0
    for s in sentences:
        t = count_tokens(s)
        if cur and cur_tokens + t > max_tokens:
            pieces.append(" ".join(cur))
            cur, cur_tokens = [], 0
        cur.append(s)
        cur_tokens += t
    if cur:
        pieces.append(" ".join(cur))
    return pieces


def chunk_book_pages(
    pages: list[dict],
    *,
    target_tokens: int = 350,
    max_tokens: int = 500,
    overlap_paragraphs: int = 1,
) -> list[ChunkDraft]:
    """`pages`: [{page_index, printed_page_number, text, chapter, section}] in order.

    Paragraphs are accumulated across page boundaries up to ~target_tokens; a chunk records the
    page range it spans so a citation can point at the first page (and the UI can show the range).
    """
    units: list[tuple[str, dict]] = []  # (paragraph, page meta)
    for p in pages:
        text = normalize_text(p.get("text") or "")
        if not text:
            continue
        meta = {
            "page_index": p["page_index"],
            "printed_page_number": p.get("printed_page_number"),
            "chapter": p.get("chapter"),
            "section": p.get("section"),
        }
        for para in _paragraphs(text):
            if count_tokens(para) > max_tokens:
                for piece in _split_long(para, max_tokens):
                    units.append((piece, meta))
            else:
                units.append((para, meta))

    chunks: list[ChunkDraft] = []
    i = 0
    while i < len(units):
        buf: list[tuple[str, dict]] = []
        tokens = 0
        j = i
        while j < len(units):
            t = count_tokens(units[j][0])
            if buf and tokens + t > target_tokens:
                break
            buf.append(units[j])
            tokens += t
            j += 1
        text = "\n\n".join(u[0] for u in buf)
        first, last = buf[0][1], buf[-1][1]
        locator = {
            "page_index": first["page_index"],
            "page_index_end": last["page_index"],
            "printed_page_number": first["printed_page_number"],
            "printed_page_number_end": last["printed_page_number"],
            "chapter": first["chapter"],
            "section": first["section"],
        }
        chunks.append(ChunkDraft(text, locator, count_tokens(text)))
        if j >= len(units):
            break
        i = max(j - overlap_paragraphs, i + 1)
    return chunks


def chunk_transcript_segments(
    segments: list[dict],
    *,
    youtube_id: str,
    target_tokens: int = 220,
    max_window_seconds: int = 90,
    overlap_segments: int = 1,
) -> list[ChunkDraft]:
    """`segments`: [{idx, start_seconds, end_seconds, text}] ordered by start.

    Groups consecutive subtitle lines into passages of ~target_tokens or <= max_window_seconds,
    preserving start/end seconds and the segment index range.
    """
    chunks: list[ChunkDraft] = []
    i = 0
    n = len(segments)
    while i < n:
        buf: list[dict] = []
        tokens = 0
        j = i
        while j < n:
            seg = segments[j]
            t = count_tokens(seg["text"])
            span = (seg.get("end_seconds") or seg["start_seconds"]) - segments[i]["start_seconds"]
            if buf and (tokens + t > target_tokens or span > max_window_seconds):
                break
            buf.append(seg)
            tokens += t
            j += 1
        text = " ".join(s["text"].strip() for s in buf)
        start = buf[0]["start_seconds"]
        end = buf[-1].get("end_seconds") or buf[-1]["start_seconds"]
        locator = {
            "youtube_id": youtube_id,
            "start_seconds": start,
            "end_seconds": end,
            "segment_idx_start": buf[0]["idx"],
            "segment_idx_end": buf[-1]["idx"],
        }
        chunks.append(ChunkDraft(text, locator, count_tokens(text)))
        if j >= n:
            break
        i = max(j - overlap_segments, i + 1)
    return chunks
