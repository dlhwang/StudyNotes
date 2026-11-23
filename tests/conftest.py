"""시험 공통. 가짜 BE·가짜 모델·메모리 기록기를 끼운다 (AGENTS.md §8)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from study_notes.config import Settings
from study_notes.deps import Deps, set_deps
from study_notes.llm.fake import FakeLlm
from study_notes.llm.gateway import GuardedGateway
from study_notes.observability.recorder import MemoryRecorder
from study_notes.tools.fakes.be import FakeBeClient


@dataclass
class Env:
    deps: Deps
    be: FakeBeClient
    llm: FakeLlm
    recorder: MemoryRecorder


@pytest.fixture
def env() -> Iterator[Env]:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    be, llm, recorder = FakeBeClient(), FakeLlm(), MemoryRecorder()
    guarded = GuardedGateway(
        llm, timeout_seconds=5, calls_per_minute=1000, cache_ttl_seconds=0, cache_max_entries=10, default_max_tokens=100
    )
    deps = Deps(settings=settings, be=be, llm=guarded, recorder=recorder)
    set_deps(deps)
    yield Env(deps=deps, be=be, llm=llm, recorder=recorder)
    set_deps(None)
