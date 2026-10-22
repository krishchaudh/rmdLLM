"""RQ worker entrypoint and job functions. Run: python -m rmd.worker"""

from __future__ import annotations

import uuid

from redis import Redis
from rq import Queue, Worker

from rmd.config import get_settings
from rmd.db import session_factory
from rmd.logging import configure_logging, get_logger

log = get_logger("rmd.worker")
QUEUE_NAME = "ingest"


def get_queue() -> Queue:
    return Queue(
        QUEUE_NAME, connection=Redis.from_url(get_settings().redis_url), default_timeout=6 * 3600
    )


def run_lecture_job(source_id: str, job_id: str) -> None:
    from rmd.ingestion.service import process_lecture

    with session_factory()() as db:
        process_lecture(db, uuid.UUID(source_id), uuid.UUID(job_id))


def run_book_job(source_id: str, job_id: str, page_range: list[int] | None = None) -> None:
    from rmd.ingestion.service import process_book

    with session_factory()() as db:
        process_book(
            db,
            uuid.UUID(source_id),
            uuid.UUID(job_id),
            page_range=tuple(page_range) if page_range else None,
        )


def enqueue_ingestion(source_kind: str, source_id: uuid.UUID, job_id: uuid.UUID, **kwargs) -> str:
    fn = run_lecture_job if source_kind == "lecture" else run_book_job
    rq_job = get_queue().enqueue(
        fn, str(source_id), str(job_id), **kwargs, job_id=str(job_id), retry=None
    )
    return rq_job.id


def main() -> None:
    s = get_settings()
    configure_logging(s.log_level, json_output=s.is_production)
    log.info("worker_start", queue=QUEUE_NAME)
    conn = Redis.from_url(s.redis_url)
    Worker([Queue(QUEUE_NAME, connection=conn)], connection=conn).work(with_scheduler=False)


if __name__ == "__main__":
    main()
