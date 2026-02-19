from fastapi import HTTPException, Request

from app.core.config import settings
from app.services.security_service import enforce_rate_limit, verify_turnstile_token


def get_client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce_optional_app_key(x_api_key: str | None) -> None:
    if settings.app_api_key and x_api_key != settings.app_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized request.")


def validate_upload_limits(pdf_bytes: bytes, job_description: str) -> None:
    max_pdf_bytes = max(1, settings.max_pdf_size_mb) * 1024 * 1024
    if len(pdf_bytes) > max_pdf_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"PDF excede o limite de {settings.max_pdf_size_mb} MB.",
        )

    if len(job_description) > max(1000, settings.max_job_description_chars):
        raise HTTPException(
            status_code=413,
            detail=(
                "Descricao da vaga excede o limite de "
                f"{settings.max_job_description_chars} caracteres."
            ),
        )


def enforce_optimize_rate_limit(ip: str) -> None:
    try:
        enforce_rate_limit(
            key=f"optimize:{ip}",
            limit=settings.rate_limit_optimize_per_minute,
            window_seconds=60,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=429, detail="Rate limit exceeded for optimize endpoint.") from exc


def enforce_export_rate_limit(ip: str) -> None:
    try:
        enforce_rate_limit(
            key=f"export:{ip}",
            limit=settings.rate_limit_export_per_minute,
            window_seconds=60,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=429, detail="Rate limit exceeded for export endpoint.") from exc


def enforce_captcha(captcha_token: str | None, ip: str) -> None:
    try:
        captcha_ok = verify_turnstile_token(captcha_token, ip)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=f"Captcha error: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Captcha verification failed: {exc}") from exc

    if not captcha_ok:
        raise HTTPException(status_code=400, detail="Invalid captcha token.")
