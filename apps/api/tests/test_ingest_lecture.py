"""Integration test against the local Postgres (DATABASE_URL) using mock providers."""

import pathlib
import uuid

import pytest
from sqlalchemy import select, text

from rmd.db import get_engine, session_factory
from rmd.ingestion.service import create_lecture_source, process_lecture
from rmd.models import Chunk, Source, TranscriptSegment

TRANSCRIPT = pathlib.Path("/home/ubuntu/transcript_P4u061hYAXs.txt")


@pytest.fixture(scope="module")
def db():
    try:
        with get_engine().connect() as c:
            c.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("database not available")
    s = session_factory()()
    yield s
    s.close()


def test_lecture_end_to_end(db):
    if not TRANSCRIPT.exists():
        pytest.skip("real transcript not available")
    raw = TRANSCRIPT.read_text(encoding="utf-8")
    # Use a unique fake id so the test does not collide with the real ingested lecture.
    fake_id = "T" + uuid.uuid4().hex[:10]
    source, job = create_lecture_source(
        db,
        url=f"https://www.youtube.com/watch?v={fake_id}",
        transcript=raw,
        fetch_meta=False,
        replace=True,
    )
    assert job.status == "queued"
    process_lecture(db, source.id, job.id)
    db.refresh(source)
    assert source.status == "ready"
    segs = db.scalars(
        select(TranscriptSegment).where(TranscriptSegment.source_id == source.id)
    ).all()
    assert len(segs) == 148
    chunks = db.scalars(select(Chunk).where(Chunk.source_id == source.id).order_by(Chunk.idx)).all()
    assert chunks and source.chunk_count == len(chunks)
    # the 5:16-6:34 wealth passage must sit in a chunk whose locator covers it
    hit = [c for c in chunks if c.locator["start_seconds"] <= 316 <= c.locator["end_seconds"]]
    assert hit and "कितना संसार मिला" in hit[0].text
    assert all(c.embedding is not None for c in chunks)
    # idempotent: same transcript again → skipped
    _, job2 = create_lecture_source(
        db, url=f"https://youtu.be/{fake_id}", transcript=raw, fetch_meta=False, replace=True
    )
    assert job2.status == "skipped"
    db.delete(db.get(Source, source.id))
    db.commit()
