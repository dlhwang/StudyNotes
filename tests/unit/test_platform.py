"""공통 기반: 도구 실행기 안전장치, 쓰기 금지, 도구 등록 규칙, 모델 게이트웨이, 프롬프트, 제안 초안."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from study_notes.agents.base import BaseAgent
from study_notes.agents.notes.tools import NoteListArgs
from study_notes.core.context import SERVICE_USER, RequestInfo, UserInfo
from study_notes.core.errors import LlmUnavailableError, ToolLimitError, ToolPermissionError
from study_notes.llm.fake import FakeLlm
from study_notes.llm.gateway import GuardedGateway, LlmRequest, LlmResult
from study_notes.prompts.loader import load_prompt
from study_notes.tools.be_client.http import HttpBeClient
from study_notes.tools.be_client.protocol import BeClient
from study_notes.tools.fakes.be import DEMO_SUBJECT, FakeBeClient
from study_notes.tools.guards import ToolRunner
from study_notes.tools.registry import TOOLS, ToolContext, agent_tool
from tests.conftest import Env


def _req(user: UserInfo | None = None, thread: str = "chat:u1:t") -> RequestInfo:
    return RequestInfo(
        user=user or UserInfo(user_id="u1"), thread_id=thread, run_id="r1", graph="test", subject_id=DEMO_SUBJECT
    )


def _runner(env: Env, agent: str = "notes", user: UserInfo | None = None, max_calls: int = 5) -> ToolRunner:
    return ToolRunner(agent=agent, request=_req(user), be=env.be, recorder=env.recorder, max_calls=max_calls)


async def test_allowlist_blocks_other_agents_tools(env: Env) -> None:
    with pytest.raises(ToolPermissionError):
        await _runner(env, agent="other").call("notes_list_items", NoteListArgs(notebook_id=DEMO_SUBJECT))


# BE에 쓰는 일로 보이는 이름. ai-agent에 이런 메서드·도구가 생기면 안 된다 (docs/01 §5)
_WRITE_WORDS = ("save", "submit", "create", "update", "delete", "approve", "confirm", "apply", "write", "post")


def test_be_client_has_no_write_methods() -> None:
    methods = [n for n in vars(BeClient) if not n.startswith("_")]
    assert methods, "BeClient 약속을 읽지 못했습니다"
    bad = [n for n in methods if any(w in n for w in _WRITE_WORDS)]
    assert bad == [], f"ai-agent는 BE에 쓰지 않습니다. 쓰기로 보이는 메서드: {bad}"
    for impl in (FakeBeClient, HttpBeClient):
        extra = [n for n in vars(impl) if not n.startswith("_") and any(w in n for w in _WRITE_WORDS)]
        assert extra == [], f"{impl.__name__}에 쓰기로 보이는 메서드: {extra}"


def test_no_tool_writes_to_be() -> None:
    bad = [n for n in TOOLS if any(f"_{w}_" in f"_{n}_" for w in _WRITE_WORDS)]
    assert bad == [], f"쓰기로 보이는 도구: {bad}"


async def test_service_user_reads_only(env: Env) -> None:
    """예약 실행(서비스 계정)도 조회 도구만 부른다."""
    out = await _runner(env, user=SERVICE_USER).call("notes_list_items", {"notebook_id": DEMO_SUBJECT})
    assert out


async def test_call_limit_and_records(env: Env) -> None:
    runner = _runner(env, max_calls=2)
    await runner.call("notes_list_items", NoteListArgs(notebook_id=DEMO_SUBJECT))
    await runner.call("notes_list_items", {"notebook_id": DEMO_SUBJECT})
    with pytest.raises(ToolLimitError):
        await runner.call("notes_list_items", {"notebook_id": DEMO_SUBJECT})
    recs = env.recorder.of("tool_call")
    assert len(recs) == 2 and all("args_hash" in r.data and r.data["outcome"] == "ok" for r in recs)


class A(BaseModel):
    x: int = 0


def test_tool_naming_rules() -> None:
    with pytest.raises(ValueError, match="형식"):

        @agent_tool(agent="notes")
        async def get_something(args: A, ctx: ToolContext) -> int:
            """doc"""
            return 1

    with pytest.raises(ValueError, match="독스트링"):

        @agent_tool(agent="notes")
        async def notes_get_nodoc(args: A, ctx: ToolContext) -> int:
            return 1


def test_proposal_draft_has_stable_dedupe_key(env: Env) -> None:
    class Dummy(BaseAgent):
        name = "dummy"
        title = "시험"
        intents = ()

    def make(thread: str) -> str:
        agent = Dummy(_req(thread=thread), env.deps)
        draft = agent.proposal(kind="x.y", title="t", payload={"n": 1}, reasons=["r"])
        assert draft.subject_id == DEMO_SUBJECT and draft.source == "chat"
        return draft.dedupe_key

    assert make("chat:u1:a") == make("chat:u1:a") != make("chat:u1:b")


async def test_gateway_cache_limit_and_failure() -> None:
    llm = FakeLlm().reply_for("worker", "안녕", "반갑습니다")
    gw = GuardedGateway(
        llm, timeout_seconds=1, calls_per_minute=2, cache_ttl_seconds=60, cache_max_entries=5, default_max_tokens=50
    )
    req = LlmRequest(role="worker", system="s", user="안녕")
    first = await gw.complete(req)
    second = await gw.complete(req)
    assert first.text == "반갑습니다" and second.cached and len(llm.calls) == 1
    with pytest.raises(LlmUnavailableError):
        await gw.complete(LlmRequest(role="worker", system="s", user="등록 안 된 질문"))
    with pytest.raises(LlmUnavailableError, match="상한"):
        await gw.complete(LlmRequest(role="worker", system="s", user="또 다른 질문"))


async def test_gateway_timeout() -> None:
    class Slow:
        async def complete(self, req: LlmRequest) -> LlmResult:
            await asyncio.sleep(1)
            return LlmResult(text="", role=req.role)

    gw = GuardedGateway(
        Slow(),
        timeout_seconds=0.05,
        calls_per_minute=10,
        cache_ttl_seconds=0,
        cache_max_entries=1,
        default_max_tokens=10,
    )
    with pytest.raises(LlmUnavailableError, match="시간 초과"):
        await gw.complete(LlmRequest(role="router", system="s", user="u"))


def test_prompt_loader() -> None:
    p = load_prompt("notes", "summary")
    assert p.id == "notes.summary.v1"
    assert "x" in p.render(title="x")
    with pytest.raises(FileNotFoundError):
        load_prompt("notes", "nothing")
