"""Supabase token verification: asymmetric (JWKS) and legacy HS256 paths."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from jose import jwk, jwt

from rmd import users
from rmd.config import get_settings


def _claims(sub: uuid.UUID, **extra) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "sub": str(sub),
        "email": "es@example.com",
        "aud": "authenticated",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        **extra,
    }


def test_es256_token_via_jwks(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "supabase_url", "https://proj.supabase.co")
    priv = ec.generate_private_key(ec.SECP256R1())
    pem = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub = jwk.construct(
        priv.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode(),
        algorithm="ES256",
    ).to_dict()
    pub["kid"] = "kid-1"
    monkeypatch.setattr(users._jwks, "_keys", {"kid-1": pub})
    monkeypatch.setattr(users._jwks, "_fetched_at", 10**12)

    uid = uuid.uuid4()
    good = jwt.encode(
        _claims(uid, iss="https://proj.supabase.co/auth/v1"),
        pem,
        algorithm="ES256",
        headers={"kid": "kid-1"},
    )
    ident = users.verify_user_token(good)
    assert ident.id == uid and ident.email == "es@example.com"

    wrong_iss = jwt.encode(
        _claims(uid, iss="https://evil.example/auth/v1"),
        pem,
        algorithm="ES256",
        headers={"kid": "kid-1"},
    )
    with pytest.raises(HTTPException) as e:
        users.verify_user_token(wrong_iss)
    assert e.value.status_code == 401

    unknown_kid = jwt.encode(
        _claims(uid, iss="https://proj.supabase.co/auth/v1"),
        pem,
        algorithm="ES256",
        headers={"kid": "kid-2"},
    )
    with pytest.raises(HTTPException):
        users.verify_user_token(unknown_kid)

    # HS256 tokens are still accepted (legacy projects) but only with the right secret
    hs = jwt.encode(
        _claims(uid, iss="https://proj.supabase.co/auth/v1"),
        "test-user-jwt-secret",
        algorithm="HS256",
    )
    assert users.verify_user_token(hs).id == uid
    forged = jwt.encode(
        _claims(uid, iss="https://proj.supabase.co/auth/v1"), "guess", algorithm="HS256"
    )
    with pytest.raises(HTTPException):
        users.verify_user_token(forged)
