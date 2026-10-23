"""RQ worker entrypoint, job functions and the dispatch policy.

Run a dedicated worker with ``python -m rmd.worker``. When no worker is listening (the free staging
tier runs only the API), ``INGEST_MODE=auto`` falls back to running the job in a background thread
of the API process so admin ingestion still completes.
"""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from redis import Redis
from rq import Queue, Worker

from rmd.config import get_settings
from rmd.db import session_factory
from rmd.logging import configure_logging, get_logger

log = get_logger("rmd.worker")
QUEUE_NAME = "ingest"

_inline_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ingest-inline")
_inline_lock = threading.Lock()
_inline_running: set[str] = set()


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


def _job_fn(source_kind: str):
    return run_lecture_job if source_kind == "lecture" else run_book_job


def worker_available(timeout: float = 1.0) -> bool:
    """True when Redis is reachable and at least one RQ worker listens on the ingest queue."""
    try:
        conn = Redis.from_url(get_settings().redis_url, socket_connect_timeout=timeout)
        return Worker.count(queue=Queue(QUEUE_NAME, connection=conn)) > 0
    except Exception as exc:  # noqa: BLE001 — redis down → treat as no worker
        log.info("worker_probe_failed", error=type(exc).__name__)
        return False


def run_inline(source_kind: str, source_id: uuid.UUID, job_id: uuid.UUID, **kwargs) -> str:
    """Run the job on the API process's background thread (one at a time)."""
    key = str(job_id)
    fn = _job_fn(source_kind)

    def _run() -> None:
        try:
            fn(str(source_id), key, **kwargs)
        except Exception:  # noqa: BLE001 — job status/error already persisted by the service
            log.exception("inline_job_failed", job_id=key)
        finally:
            with _inline_lock:
                _inline_running.discard(key)

    with _inline_lock:
        _inline_running.add(key)
    _inline_pool.submit(_run)
    log.info("inline_job_submitted", job_id=key, kind=source_kind)
    return key


def inline_jobs_pending() -> int:
    with _inline_lock:
        return len(_inline_running)


def enqueue_ingestion(source_kind: str, source_id: uuid.UUID, job_id: uuid.UUID, **kwargs) -> str:
    """Dispatch according to INGEST_MODE. Returns the job id; raises only if RQ was required."""
    mode = get_settings().ingest_mode
    if mode == "rq" or (mode == "auto" and worker_available()):
        rq_job = get_queue().enqueue(
            _job_fn(source_kind),
            str(source_id),
            str(job_id),
            **kwargs,
            job_id=str(job_id),
            retry=None,
        )
        return rq_job.id
    return run_inline(source_kind, source_id, job_id, **kwargs)


def main() -> None:
    s = get_settings()
    configure_logging(s.log_level, json_output=s.is_production)
    log.info("worker_start", queue=QUEUE_NAME)
    conn = Redis.from_url(s.redis_url)
    Worker([Queue(QUEUE_NAME, connection=conn)], connection=conn).work(with_scheduler=False)


if __name__ == "__main__":
    main()
