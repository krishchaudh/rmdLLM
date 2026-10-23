"""Admin duplicate-lecture guard: same video or same transcript → 409 unless replace=true."""

import uuid

import pytest
from fastapi.testclient import TestClient

from rmd.api import admin
from rmd.main import app

client = TestClient(app)
TRANSCRIPT = "0:00\nदो प्रकार के कर्म होते हैं।\n0:05\nएक सकाम और एक निष्काम।\n0:10\nयह परीक्षा का पाठ है।"


@pytest.fixture
def token(monkeypatch):
    monkeypatch.setattr(
        admin, "enqueue_ingestion", lambda *a, **k: str(a[2]) if len(a) > 2 else "x"
    )
    r = client.post("/auth/login", json={"username": "admin", "password": "change-me"})
    if r.status_code != 200:
        pytest.skip("admin auth not available")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _post(h, url, transcript, replace=False):
    return client.post(
        "/admin/lectures",
        json={"url": url, "transcript": transcript, "title": "dup test", "replace": replace},
        headers=h,
    )


def test_duplicate_video_and_transcript_are_rejected(token):
    vid = "T" + uuid.uuid4().hex[:10]
    salted = TRANSCRIPT + f"\n0:15\n{vid}"
    url = f"https://www.youtube.com/watch?v={vid}"
    first = _post(token, url, salted)
    if first.status_code == 500:
        pytest.skip("database not available")
    assert first.status_code == 202, first.text
    sid = first.json()["source"]["id"]
    try:
        look = client.get("/admin/lectures/lookup", params={"url": url}, headers=token)
        assert look.status_code == 200 and look.json()["existing"]["id"] == sid
        assert "already in the bank" in look.json()["reason"]

        again = _post(token, f"https://youtu.be/{vid}", salted + "\n0:20\nextra")
        assert again.status_code == 409
        assert again.json()["detail"]["source"]["id"] == sid

        other = _post(token, "https://www.youtube.com/watch?v=Zz" + vid[2:], salted)
        assert other.status_code == 409
        assert "exact transcript" in other.json()["detail"]["message"]

        fresh = client.get(
            "/admin/lectures/lookup", params={"url": "https://youtu.be/Qq" + vid[2:]}, headers=token
        )
        assert fresh.status_code == 200 and fresh.json()["existing"] is None

        forced = _post(token, url, salted + "\n0:20\nextra", replace=True)
        assert forced.status_code == 202 and forced.json()["source"]["id"] == sid
    finally:
        client.delete(f"/admin/sources/{sid}", headers=token)


def test_lookup_rejects_bad_url(token):
    assert (
        client.get("/admin/lectures/lookup", params={"url": "nope"}, headers=token).status_code
        == 400
    )
