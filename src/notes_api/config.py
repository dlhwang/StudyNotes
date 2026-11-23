"""BE 설정. 접두어 ``NOTES_API_``. 예: ``NOTES_API_AGENT_MODE=aegra``."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NOTES_API_", env_file=".env", extra="ignore")

    # 저장 위치 (저장소 루트 기준 상대 경로)
    db_path: str = "data/notes.db"
    chroma_dir: str = "data/chroma"
    # 임베딩: hash(모델 없이, 기본) | litellm(embedding_model 필요)
    embedding_mode: Literal["hash", "litellm"] = "hash"
    embedding_model: str | None = None
    # 비어 있으면 데모 노트를 넣는다
    seed_demo: bool = True
    # Agent 실행: inprocess(BE 프로세스 안, PostgreSQL 불필요) | aegra(떠 있는 Aegra 서버)
    agent_mode: Literal["inprocess", "aegra"] = "inprocess"
    aegra_url: str = "http://127.0.0.1:2026"
    # 로컬 1인용. Agent에 넘기는 사용자
    user_id: str = "local-user"
    user_name: str = "학습자"


@lru_cache(maxsize=1)
def get_api_settings() -> ApiSettings:
    return ApiSettings()
