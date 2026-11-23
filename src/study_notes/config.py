"""설정. 모든 설정은 여기서만 읽는다 (AGENTS.md §5).

환경 변수 접두어는 ``STUDY_NOTES_`` 이고, 묶음 설정은 ``__`` 로 내려간다.
예: ``STUDY_NOTES_LLM__MODE=litellm``, ``STUDY_NOTES_BE__BASE_URL=http://backend:8080``.
DB만은 Aegra와 같은 이름(``POSTGRES_HOST`` 등)을 쓴다 — ``DbSettings`` 참고.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import quote

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class BeSettings(BaseModel):
    """BE 도구 API. 경로·인증 방식은 프로젝트마다 BE와 정하므로 설정으로만 둔다."""

    mode: Literal["fake", "http"] = "fake"
    base_url: str = "http://localhost:8080"
    # BE가 Agent에게만 여는 경로 묶음. 예: /internal/agent/**
    path_prefix: str = "/internal/agent"
    timeout_seconds: float = 10.0
    read_retries: int = 2
    # 사람 없는 실행(예약 점검)이 쓰는 읽기 전용 서비스 계정 토큰 (AGENTS.md §4.5)
    service_token: SecretStr | None = None


class LlmSettings(BaseModel):
    """모델 게이트웨이. 모델 이름은 코드에 쓰지 않고 역할 키로만 부른다 (AGENTS.md §1-7)."""

    mode: Literal["fake", "litellm"] = "fake"
    # 역할 키 → 실제 모델 ID. 예: {"router": "bedrock/openai.gpt-oss-120b-1:0"}
    models: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = 20.0
    max_tokens: int = 600
    calls_per_minute: int = 20
    cache_ttl_seconds: int = 600
    cache_max_entries: int = 100


class DbSettings(BaseSettings):
    """PostgreSQL 접속. **Aegra와 같은 환경 변수(POSTGRES_*)를 함께 쓴다** — 값을 한 곳(.env)에만 적는다.

    Aegra는 DATABASE_URL이 없으면 POSTGRES_*로 붙는다(aegra_api/settings.py DatabaseSettings).
    그래서 .env에는 DATABASE_URL을 두지 않고 아래 값만 적는다.
    - Aegra 테이블(thread·run·체크포인트)은 이 DB에 Aegra가 만든다.
    - 우리 테이블(실행 기록·평가)은 AGENT_DB_SCHEMA 스키마에 만든다 (python -m study_notes.db migrate).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    host: str = Field(default="localhost", validation_alias="POSTGRES_HOST")
    port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    name: str = Field(default="aegra", validation_alias="POSTGRES_DB")
    user: str = Field(default="postgres", validation_alias="POSTGRES_USER")
    password: SecretStr = Field(default=SecretStr(""), validation_alias="POSTGRES_PASSWORD")
    sslmode: str | None = Field(default=None, validation_alias="PGSSLMODE")
    # 우리 테이블을 둘 스키마
    schema_name: str = Field(default="agent", validation_alias="AGENT_DB_SCHEMA", pattern=r"^[a-z_][a-z0-9_]*$")

    def dsn(self) -> str:
        """asyncpg·psql이 읽는 접속 주소. 비밀번호가 들어 있으니 로그에 남기지 않는다."""
        auth = quote(self.user, safe="")
        pw = self.password.get_secret_value()
        if pw:
            auth += ":" + quote(pw, safe="")
        query = f"?sslmode={self.sslmode}" if self.sslmode else ""
        return f"postgresql://{auth}@{self.host}:{self.port}/{quote(self.name, safe='')}{query}"

    def describe(self) -> str:
        """비밀번호를 뺀 접속 정보 (로그·화면 출력용)."""
        return f"{self.user}@{self.host}:{self.port}/{self.name} (schema={self.schema_name})"


class AuthSettings(BaseModel):
    """Aegra 인증. 토큰 전달 방식은 프로젝트마다 정하므로 두 방식만 둔다 (docs/01 §10)."""

    # dev: 헤더의 사용자 정보만 믿는다(개발 PC 전용)
    # trusted_be: BE만 부를 수 있는 내부망 전제. 공유 키 + BE가 보낸 사용자 헤더
    mode: Literal["dev", "trusted_be"] = "dev"
    shared_key: SecretStr | None = None


class GuardSettings(BaseModel):
    max_tool_calls_per_run: int = 20
    max_intents_per_message: int = 3  # 한 질문에서 고를 의도 최대 개수
    recursion_limit: int = 25


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="STUDY_NOTES_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
    )

    env: Literal["local", "dev", "stag", "prod", "test"] = "local"
    be: BeSettings = Field(default_factory=BeSettings)
    llm: LlmSettings = Field(default_factory=LlmSettings)
    db: DbSettings = Field(default_factory=DbSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    guard: GuardSettings = Field(default_factory=GuardSettings)
    recorder: Literal["log", "postgres"] = "log"
    # 프롬프트 버전 고정. 예: {"notes.summary": 2}. 없으면 최신 버전
    prompt_pins: dict[str, int] = Field(default_factory=dict)
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
