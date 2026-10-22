"""Ingestion services: create sources, parse/OCR, chunk, embed. Idempotent on content hash."""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from rmd.config import get_settings
from rmd.ingestion import pdf as pdfmod
from rmd.ingestion.chunking import ChunkDraft, chunk_book_pages, chunk_transcript_segments
from rmd.ingestion.transcript_parser import parse_transcript
from rmd.ingestion.youtube import canonical_url, extract_video_id, fetch_metadata
from rmd.logging import get_logger
from rmd.models import Book, Chunk, IngestionJob, Lecture, Page, Source, TranscriptSegment
from rmd.providers.base import Usage
from rmd.providers.factory import get_embedding_provider, get_llm_provider

log = get_logger("rmd.ingestion")

EMBED_BATCH = 64


class IngestionError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- lectures
def create_lecture_source(
    db: Session,
    *,
    url: str,
    transcript: str,
    title: str | None = None,
    language: str = "hi",
    fetch_meta: bool = True,
) -> tuple[Source, IngestionJob]:
    video_id = extract_video_id(url)
    if not video_id:
        raise IngestionError("could not extract a YouTube video id from the URL")
    parsed = parse_transcript(transcript)
    if not parsed.segments:
        reasons = "; ".join(f"line {i.line_number}: {i.reason}" for i in parsed.issues[:5])
        raise IngestionError(f"transcript could not be parsed ({reasons})")

    content_hash = hashlib.sha256((video_id + "\n" + transcript).encode()).hexdigest()
    existing = db.scalar(select(Lecture).where(Lecture.youtube_id == video_id))
    if existing is not None:
        source = db.get(Source, existing.source_id)
        assert source is not None
        if source.content_hash == content_hash and source.status == "ready":
            job = IngestionJob(
                source_id=source.id,
                job_type="lecture",
                status="skipped",
                progress={"reason": "identical transcript already ingested"},
            )
            db.add(job)
            db.commit()
            return source, job
        # reprocess with new transcript
        existing.raw_transcript = transcript
        source.content_hash = content_hash
        source.status = "pending"
    else:
        meta = fetch_metadata(video_id) if fetch_meta else None
        source = Source(
            kind="lecture",
            title=title or (meta.title if meta and meta.title else f"YouTube lecture {video_id}"),
            language=language,
            status="pending",
            content_hash=content_hash,
            metadata_={
                "youtube_id": video_id,
                "parse_format": parsed.format,
                "parse_issues": [i.__dict__ for i in parsed.issues[:50]],
                "thumbnail_url": meta.thumbnail_url if meta else None,
            },
        )
        db.add(source)
        db.flush()
        db.add(
            Lecture(
                source_id=source.id,
                youtube_id=video_id,
                url=canonical_url(video_id),
                channel=meta.channel if meta else None,
                transcript_source="pasted",
                raw_transcript=transcript,
                metadata_status=meta.status if meta else "not_fetched",
            )
        )
    job = IngestionJob(source_id=source.id, job_type="lecture", status="queued")
    db.add(job)
    db.commit()
    return source, job


def process_lecture(db: Session, source_id: uuid.UUID, job_id: uuid.UUID | None = None) -> None:
    source = db.get(Source, source_id)
    job = db.get(IngestionJob, job_id) if job_id else None
    if source is None or source.lecture is None:
        raise IngestionError("lecture source not found")
    _job_start(db, job)
    try:
        source.status = "processing"
        db.commit()
        parsed = parse_transcript(source.lecture.raw_transcript)
        db.execute(delete(TranscriptSegment).where(TranscriptSegment.source_id == source.id))
        db.execute(delete(Chunk).where(Chunk.source_id == source.id))
        seg_rows = []
        for idx, s in enumerate(parsed.segments):
            db.add(
                TranscriptSegment(
                    source_id=source.id,
                    idx=idx,
                    start_seconds=s.start_seconds,
                    end_seconds=s.end_seconds,
                    text=s.text,
                    raw_line=s.raw_line,
                )
            )
            seg_rows.append(
                {
                    "idx": idx,
                    "start_seconds": s.start_seconds,
                    "end_seconds": s.end_seconds,
                    "text": s.text,
                }
            )
        if parsed.segments:
            source.lecture.duration_seconds = (
                parsed.segments[-1].end_seconds or parsed.segments[-1].start_seconds
            )
        drafts = chunk_transcript_segments(seg_rows, youtube_id=source.lecture.youtube_id)
        usage = _store_chunks(db, source, drafts, kind="lecture")
        source.status = "ready"
        source.status_detail = None
        source.chunk_count = len(drafts)
        source.metadata_ = {
            **source.metadata_,
            "segment_count": len(seg_rows),
            "embedding_tokens": usage.prompt_tokens,
        }
        _job_finish(db, job, {"segments": len(seg_rows), "chunks": len(drafts)})
    except Exception as exc:
        db.rollback()
        source = db.get(Source, source_id)
        if source:
            source.status = "failed"
            source.status_detail = f"{type(exc).__name__}: {exc}"[:2000]
        _job_fail(db, db.get(IngestionJob, job_id) if job_id else None, exc)
        raise


# --------------------------------------------------------------------------- books
def create_book_source(
    db: Session,
    *,
    file_bytes: bytes,
    filename: str,
    title: str,
    author: str | None = None,
    language: str = "en",
) -> tuple[Source, IngestionJob]:
    settings = get_settings()
    if not file_bytes.startswith(b"%PDF"):
        raise IngestionError("file is not a PDF")
    if len(file_bytes) > settings.max_upload_mb * 1024 * 1024:
        raise IngestionError(f"file exceeds {settings.max_upload_mb} MB")
    sha = hashlib.sha256(file_bytes).hexdigest()
    existing = db.scalar(select(Book).where(Book.file_sha256 == sha))
    if existing is not None:
        source = db.get(Source, existing.source_id)
        assert source is not None
        job = IngestionJob(
            source_id=source.id,
            job_type="book",
            status="skipped",
            progress={"reason": "identical PDF already uploaded"},
        )
        db.add(job)
        db.commit()
        return source, job

    os.makedirs(settings.upload_dir, exist_ok=True)
    path = os.path.join(settings.upload_dir, f"{sha}.pdf")
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(file_bytes)
    try:
        doc = pdfmod.open_pdf(path)
        page_count = doc.page_count
        doc.close()
    except Exception as exc:
        os.remove(path)
        raise IngestionError(f"invalid PDF: {exc}") from exc

    source = Source(
        kind="book",
        title=title,
        language=language,
        status="pending",
        content_hash=sha,
        metadata_={"original_filename": filename},
    )
    db.add(source)
    db.flush()
    db.add(
        Book(
            source_id=source.id,
            file_path=path,
            file_sha256=sha,
            file_size=len(file_bytes),
            page_count=page_count,
            author=author,
        )
    )
    job = IngestionJob(source_id=source.id, job_type="book", status="queued")
    db.add(job)
    db.commit()
    return source, job


def process_book(
    db: Session,
    source_id: uuid.UUID,
    job_id: uuid.UUID | None = None,
    *,
    use_vision: bool = True,
    use_tesseract: bool = True,
    page_range: tuple[int, int] | None = None,
    reembed: bool = True,
) -> None:
    source = db.get(Source, source_id)
    job = db.get(IngestionJob, job_id) if job_id else None
    if source is None or source.book is None:
        raise IngestionError("book source not found")
    _job_start(db, job)
    try:
        source.status = "processing"
        db.commit()
        llm = get_llm_provider() if use_vision else None
        doc = pdfmod.open_pdf(source.book.file_path)
        total = doc.page_count
        start, end = page_range or (0, total)
        ocr_usage = Usage(model=get_settings().generation_model)
        done_indices = {p.page_index for p in source.pages}
        for i in range(start, min(end, total)):
            if i in done_indices and not page_range:
                continue
            res = pdfmod.extract_page(
                doc[i], i, llm=llm, use_vision=use_vision, use_tesseract=use_tesseract
            )
            db.execute(delete(Page).where(Page.source_id == source.id, Page.page_index == i))
            db.add(
                Page(
                    source_id=source.id,
                    page_index=i,
                    printed_page_number=res.printed_page_number,
                    text=res.text,
                    extraction_method=res.extraction_method,
                    ocr_confidence=res.confidence,
                    width=res.width,
                    height=res.height,
                    needs_review=res.needs_review,
                    review_reason=res.review_reason,
                    word_boxes=res.word_boxes,
                )
            )
            ocr_usage.prompt_tokens += res.usage.prompt_tokens
            ocr_usage.completion_tokens += res.usage.completion_tokens
            if job and (i % 5 == 0 or i == total - 1):
                job.progress = {
                    "pages_done": i + 1,
                    "pages_total": total,
                    "ocr_tokens": ocr_usage.total_tokens,
                }
            db.commit()
        doc.close()
        if reembed:
            rebuild_book_chunks(db, source)
        source.status = "ready"
        source.status_detail = None
        meta = dict(source.metadata_)
        meta["ocr_prompt_tokens"] = meta.get("ocr_prompt_tokens", 0) + ocr_usage.prompt_tokens
        meta["ocr_completion_tokens"] = (
            meta.get("ocr_completion_tokens", 0) + ocr_usage.completion_tokens
        )
        source.metadata_ = meta
        _job_finish(db, job, {"pages_total": total, "chunks": source.chunk_count})
    except Exception as exc:
        db.rollback()
        source = db.get(Source, source_id)
        if source:
            source.status = "failed"
            source.status_detail = f"{type(exc).__name__}: {exc}"[:2000]
        _job_fail(db, db.get(IngestionJob, job_id) if job_id else None, exc)
        raise


def rebuild_book_chunks(db: Session, source: Source) -> Usage:
    pages = db.scalars(
        select(Page).where(Page.source_id == source.id).order_by(Page.page_index)
    ).all()
    page_dicts = [
        {
            "page_index": p.page_index,
            "printed_page_number": p.printed_page_number,
            "text": p.text,
            "chapter": p.chapter,
            "section": p.section,
        }
        for p in pages
        if p.extraction_method != "empty"
    ]
    drafts = chunk_book_pages(page_dicts)
    db.execute(delete(Chunk).where(Chunk.source_id == source.id))
    usage = _store_chunks(db, source, drafts, kind="book")
    source.chunk_count = len(drafts)
    db.commit()
    return usage


# --------------------------------------------------------------------------- shared
def _store_chunks(db: Session, source: Source, drafts: list[ChunkDraft], *, kind: str) -> Usage:
    embedder = get_embedding_provider()
    total = Usage(model=embedder.model)
    for b in range(0, len(drafts), EMBED_BATCH):
        batch = drafts[b : b + EMBED_BATCH]
        vectors, usage = embedder.embed([d.text for d in batch])
        total.prompt_tokens += usage.prompt_tokens
        for offset, (d, v) in enumerate(zip(batch, vectors, strict=True)):
            db.add(
                Chunk(
                    source_id=source.id,
                    idx=b + offset,
                    kind=kind,
                    language=source.language,
                    text=d.text,
                    locator=d.locator,
                    token_count=d.token_count,
                    embedding=v,
                    embedding_model=embedder.model,
                )
            )
        db.flush()
    db.commit()
    return total


def _job_start(db: Session, job: IngestionJob | None) -> None:
    if job:
        job.status = "running"
        job.attempts += 1
        job.started_at = _now()
        db.commit()


def _job_finish(db: Session, job: IngestionJob | None, progress: dict) -> None:
    if job:
        job.status = "succeeded"
        job.finished_at = _now()
        job.progress = {**job.progress, **progress}
    db.commit()


def _job_fail(db: Session, job: IngestionJob | None, exc: Exception) -> None:
    if job:
        job.status = "failed"
        job.finished_at = _now()
        job.error = f"{type(exc).__name__}: {exc}"[:4000]
    db.commit()
