from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from rmd.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)
ALGO = "HS256"


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def create_token(subject: str) -> tuple[str, int]:
    s = get_settings()
    exp_seconds = s.jwt_expire_minutes * 60
    payload = {
        "sub": subject,
        "role": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(seconds=exp_seconds),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=ALGO), exp_seconds


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    s = get_settings()
    ok_user = hmac.compare_digest(body.username.encode(), s.admin_username.encode())
    ok_pass = hmac.compare_digest(body.password.encode(), s.admin_password.encode())
    if not (ok_user and ok_pass):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    token, exp = create_token(body.username)
    return TokenResponse(access_token=token, expires_in=exp)


def require_admin(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, get_settings().jwt_secret, algorithms=[ALGO])
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from exc
    if payload.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return str(payload.get("sub"))


@router.get("/me")
def me(user: str = Depends(require_admin)):
    return {"username": user, "role": "admin"}
