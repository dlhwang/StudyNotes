"""MCP 서버 설정. 접두어 ``NOTES_MCP_``."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class McpSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NOTES_MCP_", env_file=".env", extra="ignore")

    be_url: str = "http://127.0.0.1:8000"
    timeout_seconds: float = 15.0
