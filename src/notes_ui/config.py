"""화면 설정. 접두어 ``NOTES_UI_``. 예: ``NOTES_UI_API_URL=http://127.0.0.1:8000``."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class UiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NOTES_UI_", env_file=".env", extra="ignore")

    api_url: str = "http://127.0.0.1:8000"
    timeout_seconds: float = 120.0
