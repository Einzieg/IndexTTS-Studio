from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass

from fastapi import Request, Response

from app.core.config import AuthSettings


@dataclass(slots=True)
class AuthSession:
    username: str
    expires_at: int


def validate_credentials(settings: AuthSettings, username: str, password: str) -> bool:
    if not settings.enabled:
        return True
    return secrets.compare_digest(username, settings.username) and secrets.compare_digest(
        password,
        settings.password,
    )


def create_session_token(settings: AuthSettings, username: str) -> str:
    expires_at = int(time.time()) + settings.session_ttl_seconds
    payload = f"{username}\n{expires_at}"
    signature = _sign_payload(settings.session_secret, payload)
    raw = f"{payload}\n{signature}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def resolve_session(settings: AuthSettings, token: str | None) -> AuthSession | None:
    if not settings.enabled or not token:
        return None

    try:
        raw = base64.urlsafe_b64decode(_with_padding(token)).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None

    username, expires_at_text, signature = _split_token(raw)
    if not username or not expires_at_text or not signature:
        return None

    expected = _sign_payload(settings.session_secret, f"{username}\n{expires_at_text}")
    if not secrets.compare_digest(signature, expected):
        return None

    try:
        expires_at = int(expires_at_text)
    except ValueError:
        return None

    if expires_at <= int(time.time()):
        return None
    return AuthSession(username=username, expires_at=expires_at)


def session_from_request(request: Request, settings: AuthSettings) -> AuthSession | None:
    token = request.cookies.get(settings.session_cookie_name)
    return resolve_session(settings, token)


def set_session_cookie(response: Response, settings: AuthSettings, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        max_age=settings.session_ttl_seconds,
        secure=settings.secure_cookie,
        samesite=settings.same_site,
        path="/",
    )


def clear_session_cookie(response: Response, settings: AuthSettings) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.secure_cookie,
        samesite=settings.same_site,
    )


def _with_padding(token: str) -> str:
    padding = (-len(token)) % 4
    return token + ("=" * padding)


def _split_token(raw: str) -> tuple[str, str, str]:
    parts = raw.split("\n")
    if len(parts) != 3:
        return "", "", ""
    return parts[0], parts[1], parts[2]


def _sign_payload(secret: str, payload: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
