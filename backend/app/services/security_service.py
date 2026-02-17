import time
from collections import deque
from threading import Lock
from typing import Deque, Dict

import httpx

from app.core.config import settings


_RATE_LIMIT_STORE: Dict[str, Deque[float]] = {}
_STORE_LOCK = Lock()


def _now() -> float:
    return time.time()


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
