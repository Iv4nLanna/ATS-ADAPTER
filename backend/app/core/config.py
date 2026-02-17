from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ai_provider: Literal["groq", "gemini", "openai", "openrouter"] = "groq"
    ai_timeout_seconds: int = 90

    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.1-8b-instruct:free"

    resume_chunk_max_chars: int = 1100
    resume_chunk_min_chars: int = 260
    resume_chunk_max_selected: int = 6

    app_api_key: str = ""
    max_pdf_size_mb: int = 5
    max_job_description_chars: int = 15000

    rate_limit_optimize_per_minute: int = 12
    rate_limit_export_per_minute: int = 20

    captcha_enabled: bool = False
    turnstile_secret_key: str = ""

    frontend_origin: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
