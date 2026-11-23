"""의존성 모음. 그래프와 하위 Agent는 여기서 BE 클라이언트·모델·기록기를 받는다.

시험에서는 ``set_deps(Deps(...))``로 바꿔 끼운다. 운영에서는 설정으로 정한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from study_notes.config import Settings, get_settings
from study_notes.llm.fake import FakeLlm
from study_notes.llm.gateway import GuardedGateway, LlmGateway
from study_notes.observability.recorder import LogRecorder, RunRecorder
from study_notes.tools.be_client.protocol import BeClient


@dataclass
class Deps:
    settings: Settings
    be: BeClient
    llm: LlmGateway
    recorder: RunRecorder


_current: Deps | None = None


def build_deps(settings: Settings | None = None) -> Deps:
    s = settings or get_settings()

    be: BeClient
    if s.be.mode == "http":
        from study_notes.tools.be_client.http import HttpBeClient

        be = HttpBeClient(s.be)
    else:
        from study_notes.tools.fakes.be import FakeBeClient

        be = FakeBeClient()

    inner: LlmGateway
    if s.llm.mode == "litellm":
        from study_notes.llm.litellm_gateway import LiteLlmGateway

        inner = LiteLlmGateway(s.llm.models)
    else:
        inner = FakeLlm()
    llm = GuardedGateway(
        inner,
        timeout_seconds=s.llm.timeout_seconds,
        calls_per_minute=s.llm.calls_per_minute,
        cache_ttl_seconds=s.llm.cache_ttl_seconds,
        cache_max_entries=s.llm.cache_max_entries,
        default_max_tokens=s.llm.max_tokens,
    )

    recorder: RunRecorder
    if s.recorder == "postgres":
        from study_notes.db.recorder import PostgresRecorder

        recorder = PostgresRecorder()
    else:
        recorder = LogRecorder()
    return Deps(settings=s, be=be, llm=llm, recorder=recorder)


def get_deps() -> Deps:
    global _current
    if _current is None:
        _current = build_deps()
    return _current


def set_deps(deps: Deps | None) -> None:
    """시험용. None이면 다음 get_deps()에서 설정으로 다시 만든다."""
    global _current
    _current = deps
