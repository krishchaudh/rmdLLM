from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from rmd.api.schemas import PageOut, SourceOut
from rmd.db import get_db
from rmd.models import Page, Source

router = APIRouter(prefix="/sources", tags=["sources"])


def source_to_out(s: Source) -> SourceOut:
    book = None
    lecture = None
    if s.book:
        book = {
            "page_count": s.book.page_count,
            "author": s.book.author,
            "file_size": s.book.file_size,
            "file_sha256": s.book.file_sha256,
        }
    if s.lecture:
        lecture = {
            "youtube_id": s.lecture.youtube_id,
            "url": s.lecture.url,
            "channel": s.lecture.channel,
            "duration_seconds": s.lecture.duration_seconds,
            "transcript_source": s.lecture.transcript_source,
            "verification_status": s.lecture.verification_status,
            "metadata_status": s.lecture.metadata_status,
        }
    return SourceOut(
        id=s.id,
        kind=s.kind,
        title=s.title,
        language=s.language,
        status=s.status,
        status_detail=s.status_detail,
        chunk_count=s.chunk_count,
        created_at=s.created_at,
        updated_at=s.updated_at,
        metadata=s.metadata_ or {},
        book=book,
        lecture=lecture,
    )


def _get_source(db: Session, source_id: uuid.UUID) -> Source:
    s = db.get(Source, source_id)
    if s is None:
        raise HTTPException(404, "Source not found")
    return s


@router.get("", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db), kind: str | None = None):
    q = select(Source).order_by(Source.created_at.desc())
    if kind:
        q = q.where(Source.kind == kind)
    return [source_to_out(s) for s in db.scalars(q).all()]


@router.get("/{source_id}", response_model=SourceOut)
def get_source(source_id: uuid.UUID, db: Session = Depends(get_db)):
    return source_to_out(_get_source(db, source_id))


@router.get("/{source_id}/pdf")
def get_pdf(source_id: uuid.UUID, db: Session = Depends(get_db)):
    s = _get_source(db, source_id)
    if not s.book:
        raise HTTPException(404, "Not a book")
    return FileResponse(
        s.book.file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{s.title[:80]}.pdf"'},
    )


@router.get("/{source_id}/pages/{page_index}", response_model=PageOut)
def get_page(source_id: uuid.UUID, page_index: int, db: Session = Depends(get_db)):
    p = db.scalar(select(Page).where(Page.source_id == source_id, Page.page_index == page_index))
    if p is None:
        raise HTTPException(404, "Page not found")
    return PageOut.model_validate(p, from_attributes=True)


@router.get("/{source_id}/pages/{page_index}/image")
def get_page_image(
    source_id: uuid.UUID,
    page_index: int,
    db: Session = Depends(get_db),
    dpi: int = Query(default=110, ge=40, le=200),
):
    s = _get_source(db, source_id)
    if not s.book:
        raise HTTPException(404, "Not a book")
    from rmd.ingestion.pdf import open_pdf

    doc = open_pdf(s.book.file_path)
    if page_index < 0 or page_index >= doc.page_count:
        raise HTTPException(404, "Page out of range")
    pix = doc[page_index].get_pixmap(dpi=dpi, alpha=False)
    data = pix.tobytes("png")
    doc.close()
    return Response(
        data, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"}
    )
