import hmac
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.config import get_settings

COOKIE_NAME = "session"
TOKEN_TTL = timedelta(days=30)
ALGORITHM = "HS256"

# Простая защита от перебора: не больше 10 неудачных попыток за 15 минут с одного IP.
MAX_FAILURES = 10
FAILURE_WINDOW = 15 * 60
_failures: dict[str, deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _recent_failures(ip: str) -> deque[float]:
    attempts = _failures[ip]
    while attempts and attempts[0] < time.monotonic() - FAILURE_WINDOW:
        attempts.popleft()
    return attempts


def create_token() -> str:
    payload = {"sub": "app", "exp": datetime.now(timezone.utc) + TOKEN_TTL}
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=ALGORITHM)


def require_auth(request: Request) -> None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Требуется вход")
    try:
        jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(401, "Сессия истекла, войдите снова")


class LoginIn(BaseModel):
    password: str


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response) -> dict:
    ip = _client_ip(request)
    attempts = _recent_failures(ip)
    if len(attempts) >= MAX_FAILURES:
        raise HTTPException(429, "Слишком много попыток, попробуйте позже")
    if not hmac.compare_digest(body.password.encode(), get_settings().app_password.encode()):
        attempts.append(time.monotonic())
        raise HTTPException(401, "Неверный пароль")
    attempts.clear()
    response.set_cookie(
        COOKIE_NAME,
        create_token(),
        max_age=int(TOKEN_TTL.total_seconds()),
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
        path="/",
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me", dependencies=[Depends(require_auth)])
def me() -> dict:
    return {"ok": True}
