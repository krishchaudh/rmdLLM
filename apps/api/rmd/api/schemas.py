from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SourceOut(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    language: str
    status: str
    status_detail: str | None = None
    chunk_count: int
    created_at: datetime
    updated_at: datetime
    metadata: dict = Field(default_factory=dict)
    book: dict | None = None
    lecture: dict | None = None


class PageOut(BaseModel):
    page_index: int
    printed_page_number: str | None
    text: str
    extraction_method: str
    ocr_confidence: float | None
    needs_review: bool
    review_reason: str | None
    chapter: str | None = None
    section: str | None = None


class JobOut(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    job_type: str
    status: str
    attempts: int
    progress: dict
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class LectureCreate(BaseModel):
    url: str = Field(min_length=5, max_length=512)
    transcript: str = Field(min_length=5, max_length=2_000_000)
    title: str | None = Field(default=None, max_length=512)
    language: str = Field(default="hi", max_length=16)


class TranscriptFetchIn(BaseModel):
    url: str = Field(min_length=5, max_length=512)


class TranscriptFetchOut(BaseModel):
    video_id: str
    language: str
    transcript: str
    segments: int


class IngestAccepted(BaseModel):
    source: SourceOut
    job: JobOut
