"""End-user identity from Supabase Auth access tokens.

Guests are allowed everywhere; a valid token just attaches the conversation to an
account. Admin tokens (rmd.api.auth) are a separate, HS256 scheme.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from slowapi.util import get_remote_address

from rmd.config import get_settings
from rmd.logging import get_logger

log = get_logger("rmd.users")
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class UserIdentity:
    id: uuid.UUID
    email: str | None


class _JWKSCache:
    def __init__(self) -> None:
        self._keys: dict[str, dict] = {}
        self._fetched_at = 0.0
        self._lock = threading.Lock()

    def key_for(self, kid: str | None) -> dict | None:
        with self._lock:
            if kid in self._keys and time.time() - self._fetched_at < 3600:
                return self._keys[kid]
            if time.time() - self._fetched_at > 60:  # unknown kid: refetch (key rotation)
                self._refresh()
            return self._keys.get(kid)

    def _refresh(self) -> None:
        url = get_settings().supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
        try:
            r = httpx.get(url, timeout=5)
            r.raise_for_status()
            self._keys = {k.get("kid"): k for k in r.json().get("keys", [])}
            self._fetched_at = time.time()
        except Exception as exc:
            log.warning("jwks_fetch_failed", error=type(exc).__name__)


_jwks = _JWKSCache()


def verify_user_token(token: str) -> UserIdentity:
    """Decode a Supabase access token; raises HTTPException(401) on any problem."""
    s = get_settings()
    if not s.supabase_url and not s.supabase_jwt_secret:
        raise HTTPException(401, "Accounts are not enabled on this server")
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "")
        issuer = s.supabase_url.rstrip("/") + "/auth/v1" if s.supabase_url else None
        opts = {"verify_iss": issuer is not None}
        if alg == "HS256":
            if not s.supabase_jwt_secret:
                raise HTTPException(401, "Unsupported token")
            claims = jwt.decode(
                token,
                s.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                issuer=issuer,
                options=opts,
            )
        else:
            key = _jwks.key_for(header.get("kid"))
            if key is None:
                raise HTTPException(401, "Unknown signing key")
            claims = jwt.decode(
                token,
                key,
                algorithms=[alg],
                audience="authenticated",
                issuer=issuer,
                options=opts,
            )
    except JWTError as exc:
        raise HTTPException(401, "Invalid or expired session, please sign in again") from exc
    try:
        uid = uuid.UUID(str(claims["sub"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(401, "Invalid token subject") from exc
    return UserIdentity(id=uid, email=claims.get("email"))


def identify(request: Request) -> UserIdentity | None:
    """Cached per-request identity (also used by the rate limiter key function)."""
    if hasattr(request.state, "user"):
        return request.state.user
    user: UserIdentity | None = None
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            user = verify_user_token(auth[7:].strip())
        except HTTPException as exc:
            request.state.user_error = exc
    request.state.user = user
    return user


def current_user_optional(
    request: Request, _creds: HTTPAuthorizationCredentials | None = Depends(_bearer)
) -> UserIdentity | None:
    """Signed-in user, or None for guests. A *present but bad* token is rejected so the
    client notices an expired session instead of silently losing its history."""
    user = identify(request)
    err = getattr(request.state, "user_error", None)
    if user is None and err is not None:
        raise err
    return user


def require_user(user: UserIdentity | None = Depends(current_user_optional)) -> UserIdentity:
    if user is None:
        raise HTTPException(401, "Sign in required")
    return user


# --- rate-limit helpers -------------------------------------------------------------


def ask_rate_key(request: Request) -> str:
    user = identify(request)
    return f"user:{user.id}" if user else f"ip:{get_remote_address(request)}"


def is_signed_in(request: Request) -> bool:
    return identify(request) is not None


def is_guest(request: Request) -> bool:
    return identify(request) is None


def global_key() -> str:
    return "global"
