from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rmd.api.auth import require_admin
from rmd.api.schemas import IngestAccepted, JobOut, LectureCreate, PageOut
from rmd.api.sources import source_to_out
from rmd.config import get_settings
from rmd.db import get_db
from rmd.ingestion.service import IngestionError, create_book_source, create_lecture_source
from rmd.models import Feedback, IngestionJob, Message, Page, Source
from rmd.worker import enqueue_ingestion

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _job_out(j: IngestionJob) -> JobOut:
    return JobOut.model_validate(j, from_attributes=True)


def _dispatch(source: Source, job: IngestionJob, **kwargs) -> None:
    if job.status != "queued":
        return
    try:
        enqueue_ingestion(source.kind, source.id, job.id, **kwargs)
    except Exception as exc:  # redis down → surface clearly instead of silently losing the job
        raise HTTPException(503, f"Job queue unavailable: {type(exc).__name__}") from exc


@router.post("/lectures", response_model=IngestAccepted, status_code=202)
def add_lecture(body: LectureCreate, db: Session = Depends(get_db)):
    try:
        source, job = create_lecture_source(
            db, url=body.url, transcript=body.transcript, title=body.title, language=body.language
        )
    except IngestionError as exc:
        raise HTTPException(400, str(exc)) from exc
    _dispatch(source, job)
    return IngestAccepted(source=source_to_out(source), job=_job_out(job))


@router.post("/books", response_model=IngestAccepted, status_code=202)
async def upload_book(
    file: UploadFile = File(...),
    title: str = Form(..., max_length=512),
    author: str | None = Form(default=None, max_length=256),
    language: str = Form(default="en", max_length=16),
    db: Session = Depends(get_db),
):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(400, "Only PDF uploads are accepted")
    data = await file.read()
    try:
        source, job = create_book_source(
            db,
            file_bytes=data,
            filename=file.filename or "upload.pdf",
            title=title,
            author=author,
            language=language,
        )
    except IngestionError as exc:
        raise HTTPException(400, str(exc)) from exc
    _dispatch(source, job)
    return IngestAccepted(source=source_to_out(source), job=_job_out(job))


@router.post("/sources/{source_id}/reprocess", response_model=JobOut, status_code=202)
def reprocess(
    source_id: uuid.UUID,
    db: Session = Depends(get_db),
    page_start: int | None = None,
    page_end: int | None = None,
):
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(404, "Source not found")
    job = IngestionJob(source_id=source.id, job_type=source.kind, status="queued")
    source.status = "pending"
    db.add(job)
    db.commit()
    kwargs = {}
    if source.kind == "book" and page_start is not None and page_end is not None:
        kwargs["page_range"] = [page_start, page_end]
    _dispatch(source, job, **kwargs)
    return _job_out(job)


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: uuid.UUID, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(404, "Source not found")
    db.delete(source)
    db.commit()


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(db: Session = Depends(get_db), limit: int = 50):
    jobs = db.scalars(
        select(IngestionJob).order_by(IngestionJob.created_at.desc()).limit(limit)
    ).all()
    return [_job_out(j) for j in jobs]


@router.get("/sources/{source_id}/pages", response_model=list[PageOut])
def list_pages(
    source_id: uuid.UUID,
    db: Session = Depends(get_db),
    needs_review: bool | None = None,
    offset: int = 0,
    limit: int = 50,
):
    q = select(Page).where(Page.source_id == source_id).order_by(Page.page_index)
    if needs_review is not None:
        q = q.where(Page.needs_review == needs_review)
    return [
        PageOut.model_validate(p, from_attributes=True)
        for p in db.scalars(q.offset(offset).limit(limit))
    ]


@router.patch("/sources/{source_id}/pages/{page_index}", response_model=PageOut)
def update_page(
    source_id: uuid.UUID,
    page_index: int,
    body: dict,
    db: Session = Depends(get_db),
):
    p = db.scalar(select(Page).where(Page.source_id == source_id, Page.page_index == page_index))
    if p is None:
        raise HTTPException(404, "Page not found")
    for key in (
        "text",
        "printed_page_number",
        "chapter",
        "section",
        "needs_review",
        "review_reason",
    ):
        if key in body:
            setattr(p, key, body[key])
    if "text" in body:
        p.extraction_method = "manual"
        p.ocr_confidence = 1.0
    db.commit()
    return PageOut.model_validate(p, from_attributes=True)


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    s = get_settings()
    msg_count = (
        db.scalar(select(func.count()).select_from(Message).where(Message.role == "assistant")) or 0
    )
    abstained = (
        db.scalar(select(func.count()).select_from(Message).where(Message.abstained.is_(True))) or 0
    )
    cost = db.scalar(select(func.coalesce(func.sum(Message.estimated_cost_usd), 0.0))) or 0.0
    fb_up = db.scalar(select(func.count()).select_from(Feedback).where(Feedback.rating > 0)) or 0
    fb_down = db.scalar(select(func.count()).select_from(Feedback).where(Feedback.rating < 0)) or 0
    return {
        "sources": db.scalar(select(func.count()).select_from(Source)) or 0,
        "answers": msg_count,
        "abstained": abstained,
        "estimated_cost_usd": round(float(cost), 4),
        "feedback": {"up": fb_up, "down": fb_down},
        "models": {"generation": s.generation_model, "embedding": s.embedding_model},
    }
