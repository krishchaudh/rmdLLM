"""Dispatch policy: fall back to in-process execution when no RQ worker is listening."""

import threading
import uuid

from fastapi.testclient import TestClient

from rmd import worker
from rmd.ingestion.youtube import TranscriptFetchError
from rmd.main import app

client = TestClient(app)


def _token() -> str:
    r = client.post("/auth/login", json={"username": "admin", "password": "change-me"})
    return r.json()["access_token"]


def test_auto_mode_runs_inline_without_worker(monkeypatch):
    done = threading.Event()
    calls: list[tuple] = []

    def fake_job(source_id: str, job_id: str, **kwargs) -> None:
        calls.append((source_id, job_id, kwargs))
        done.set()

    monkeypatch.setattr(worker, "worker_available", lambda: False)
    monkeypatch.setattr(worker, "_job_fn", lambda kind: fake_job)
    sid, jid = uuid.uuid4(), uuid.uuid4()
    assert worker.enqueue_ingestion("book", sid, jid, page_range=[1, 2]) == str(jid)
    assert done.wait(5)
    assert calls == [(str(sid), str(jid), {"page_range": [1, 2]})]


def test_inline_job_failure_is_contained(monkeypatch):
    done = threading.Event()

    def boom(source_id: str, job_id: str) -> None:
        done.set()
        raise RuntimeError("x")

    monkeypatch.setattr(worker, "_job_fn", lambda kind: boom)
    jid = uuid.uuid4()
    worker.run_inline("lecture", uuid.uuid4(), jid)
    assert done.wait(5)
    for _ in range(50):
        if worker.inline_jobs_pending() == 0:
            break
        threading.Event().wait(0.02)
    assert worker.inline_jobs_pending() == 0


def test_fetch_transcript_endpoint(monkeypatch):
    tok = _token()
    h = {"Authorization": f"Bearer {tok}"}
    monkeypatch.setattr(
        "rmd.api.admin.fetch_transcript", lambda vid: ("0:00 पहली बात\n0:05 दूसरी बात", "hi")
    )
    r = client.post(
        "/admin/lectures/transcript", json={"url": "https://youtu.be/P4u061hYAXs"}, headers=h
    )
    assert r.status_code == 200
    assert r.json() == {
        "video_id": "P4u061hYAXs",
        "language": "hi",
        "transcript": "0:00 पहली बात\n0:05 दूसरी बात",
        "segments": 2,
    }

    def blocked(vid):
        raise TranscriptFetchError("YouTube blocked the server's request")

    monkeypatch.setattr("rmd.api.admin.fetch_transcript", blocked)
    r = client.post(
        "/admin/lectures/transcript", json={"url": "https://youtu.be/P4u061hYAXs"}, headers=h
    )
    assert r.status_code == 502 and "blocked" in r.json()["detail"]
    assert (
        client.post("/admin/lectures/transcript", json={"url": "not a url"}, headers=h).status_code
        == 400
    )
