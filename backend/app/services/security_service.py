import secrets
import time
from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Deque, Dict, Optional

import httpx

from app.core.config import settings


@dataclass
class SessionData:
    user_id: str
    expires_at: float


_SESSION_STORE: Dict[str, SessionData] = {}
_RATE_LIMIT_STORE: Dict[str, Deque[float]] = {}
_STORE_LOCK = Lock()


def _now() -> float:
    return time.time()


def _cleanup_sessions(now_ts: float) -> None:
    expired_tokens = [token for token, data in _SESSION_STORE.items() if data.expires_at <= now_ts]
    for token in expired_tokens:
        _SESSION_STORE.pop(token, None)


def issue_session_token(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    ttl_seconds = max(1, settings.auth_token_ttl_minutes) * 60
    expires_at = _now() + ttl_seconds

    with _STORE_LOCK:
        _SESSION_STORE[token] = SessionData(user_id=user_id, expires_at=expires_at)
        _cleanup_sessions(_now())

    return token


def verify_session_token(token: str) -> Optional[str]:
    with _STORE_LOCK:
        data = _SESSION_STORE.get(token)
        if not data:
            return None

        if data.expires_at <= _now():
            _SESSION_STORE.pop(token, None)
            return None

        return data.user_id


def validate_login_credentials(username: str, password: str) -> bool:
    # Constant-time comparisons to reduce timing leak on credential checks.
    valid_user = secrets.compare_digest(username or "", settings.auth_username or "")
    valid_pass = secrets.compare_digest(password or "", settings.auth_password or "")
    return valid_user and valid_pass


def enforce_rate_limit(key: str, limit: int, window_seconds: int = 60) -> None:
    if limit <= 0:
        return

    now_ts = _now()
    cutoff = now_ts - max(1, window_seconds)

    with _STORE_LOCK:
        bucket = _RATE_LIMIT_STORE.setdefault(key, deque())
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            raise RuntimeError("rate_limit_exceeded")

        bucket.append(now_ts)


def verify_turnstile_token(captcha_token: str | None, remote_ip: str | None) -> bool:
    if not settings.captcha_enabled:
        return True

    if not settings.turnstile_secret_key:
        raise RuntimeError("captcha_not_configured")

    if not captcha_token:
        return False

    payload = {
        "secret": settings.turnstile_secret_key,
        "response": captcha_token,
    }
    if remote_ip:
        payload["remoteip"] = remote_ip

    with httpx.Client(timeout=10) as client:
        response = client.post("https://challenges.cloudflare.com/turnstile/v0/siteverify", data=payload)
        response.raise_for_status()
        parsed = response.json()

    return bool(parsed.get("success"))
