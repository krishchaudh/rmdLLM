from fastapi.testclient import TestClient

from rmd.main import app

client = TestClient(app)


def test_admin_requires_token():
    assert client.get("/admin/jobs").status_code == 401


def test_login_and_me():
    r = client.post("/auth/login", json={"username": "admin", "password": "change-me"})
    assert r.status_code == 200
    tok = r.json()["access_token"]
    assert (
        client.get("/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()["role"] == "admin"
    )
    assert (
        client.post("/auth/login", json={"username": "admin", "password": "nope"}).status_code
        == 401
    )
