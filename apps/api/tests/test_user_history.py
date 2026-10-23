"""Signed-in chat history: ownership, listing, rename/delete/claim, token validation."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from jose import jwt

from rmd.main import app

client = TestClient(app)
SECRET = "test-user-jwt-secret"


def _token(sub: uuid.UUID, email: str = "u@example.com", exp_minutes: int = 60) -> dict:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(sub),
        "email": email,
        "aud": "authenticated",
        "role": "authenticated",
        "iat": now,
        "exp": now + timedelta(minutes=exp_minutes),
    }
    return {"Authorization": "Bearer " + jwt.encode(claims, SECRET, algorithm="HS256")}


def _ask(q: str, conv: str | None = None, headers: dict | None = None):
    return client.post("/ask", json={"question": q, "conversation_id": conv}, headers=headers)


def test_me_requires_token():
    assert client.get("/me/conversations").status_code == 401
    bad = {"Authorization": "Bearer not.a.token"}
    assert client.get("/me/conversations", headers=bad).status_code == 401
    expired = _token(uuid.uuid4(), exp_minutes=-5)
    assert client.get("/me/conversations", headers=expired).status_code == 401
    # a bad token on /ask is rejected too (not silently treated as a guest)
    assert _ask("What is prema?", headers=expired).status_code == 401


def test_history_lifecycle():
    alice, bob = uuid.uuid4(), uuid.uuid4()
    ha, hb = _token(alice, "alice@example.com"), _token(bob, "bob@example.com")

    r = _ask("What is prema according to the book?", headers=ha)
    assert r.status_code == 200, r.text
    conv_id = r.json()["conversation_id"]

    lst = client.get("/me/conversations", headers=ha).json()
    mine = [c for c in lst if c["id"] == conv_id]
    assert len(mine) == 1
    assert mine[0]["title"].startswith("What is prema")
    assert mine[0]["message_count"] == 2

    # only the owner can read or continue it
    assert client.get(f"/conversations/{conv_id}").status_code == 403
    assert client.get(f"/conversations/{conv_id}", headers=hb).status_code == 403
    assert _ask("tell me more", conv_id, headers=hb).status_code == 403
    assert _ask("tell me more", conv_id).status_code == 403
    got = client.get(f"/conversations/{conv_id}", headers=ha).json()
    assert got["owned"] is True and len(got["messages"]) == 2
    assert all(c["id"] != conv_id for c in client.get("/me/conversations", headers=hb).json())

    r = client.patch(f"/me/conversations/{conv_id}", json={"title": "Prema notes"}, headers=ha)
    assert r.status_code == 200 and r.json()["title"] == "Prema notes"
    assert (
        client.patch(f"/me/conversations/{conv_id}", json={"title": "x"}, headers=hb).status_code
        == 404
    )

    assert client.delete(f"/me/conversations/{conv_id}", headers=hb).status_code == 404
    assert client.delete(f"/me/conversations/{conv_id}", headers=ha).status_code == 204
    assert client.get(f"/conversations/{conv_id}", headers=ha).status_code == 404


def test_guest_chat_claimed_on_sign_in():
    r = _ask("Why does wealth not give lasting happiness?")
    assert r.status_code == 200, r.text
    conv_id = r.json()["conversation_id"]
    assert client.get(f"/conversations/{conv_id}").json()["owned"] is False

    carol = uuid.uuid4()
    hc = _token(carol, "carol@example.com")
    assert client.post(f"/me/conversations/{conv_id}/claim", headers=hc).status_code == 204
    assert any(c["id"] == conv_id for c in client.get("/me/conversations", headers=hc).json())
    # now private
    assert client.get(f"/conversations/{conv_id}").status_code == 403
    other = _token(uuid.uuid4())
    assert client.post(f"/me/conversations/{conv_id}/claim", headers=other).status_code == 403

    # continuing a guest chat while signed in also adopts it
    r2 = _ask("What is maya?")
    g2 = r2.json()["conversation_id"]
    assert _ask("and what is prema?", g2, headers=hc).status_code == 200
    assert client.get(f"/conversations/{g2}", headers=hc).json()["owned"] is True

    assert client.delete("/me/conversations", headers=hc).status_code == 204
    assert client.get("/me/conversations", headers=hc).json() == []
    assert client.get(f"/conversations/{conv_id}", headers=hc).status_code == 404
