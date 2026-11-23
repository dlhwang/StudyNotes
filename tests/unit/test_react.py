"""Function Calling 게이트웨이와 ReAct 루프 (가짜 모델 시나리오)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from study_notes.agents.base import BaseAgent
from study_notes.core.context import RequestInfo, UserInfo
from study_notes.core.errors import LlmUnavailableError, ToolInputError, ToolPermissionError
from study_notes.llm.gateway import ChatMessage, LlmRequest, LlmResult, ToolCall, ToolDef
from study_notes.llm.litellm_gateway import parse_tool_calls, to_openai_messages, to_openai_tools
from study_notes.prompts.loader import Prompt
from study_notes.tools.registry import ToolContext, agent_tool
from tests.conftest import Env


class EchoArgs(BaseModel):
    word: str = Field(description="돌려받을 단어", min_length=2)


@agent_tool(agent="reactdummy", llm_selectable=True)
async def reactdummy_get_echo(args: EchoArgs, ctx: ToolContext) -> dict[str, str]:
    """단어를 그대로 돌려준다. 시험용."""
    if args.word == "없음":
        raise ToolInputError("그런 단어는 없습니다", hint="다른 단어로 다시 부르세요")
    return {"echo": args.word}


@agent_tool(agent="reactdummy")
async def reactdummy_get_hidden(args: EchoArgs, ctx: ToolContext) -> str:
    """모델에게 보이지 않는 도구. 시험용."""
    return args.word


class Dummy(BaseAgent):
    name = "reactdummy"
    title = "시험"
    intents = ()


PROMPT = Prompt(agent="reactdummy", purpose="qa", version=1, text="너는 시험용 비서다. {topic}")


def _agent(env: Env) -> Dummy:
    req = RequestInfo(user=UserInfo(user_id="u1"), thread_id="t", run_id="r", graph="test", subject_id="NB-1")
    return Dummy(req, env.deps)


def _call(name: str, **args: str) -> LlmResult:
    return LlmResult(text="도구가 필요하다", role="worker", tool_calls=[ToolCall(id="c1", name=name, arguments=args)])


async def test_react_tool_then_answer(env: Env) -> None:
    env.llm.script("worker", [_call("reactdummy_get_echo", word="안녕"), "최종 답: 안녕"])
    out = await _agent(env).react("worker", PROMPT, "따라 해", topic="메아리")
    assert out.answer == "최종 답: 안녕" and out.prompt_id == "reactdummy.qa.v1"
    assert [(s.tool, s.args) for s in out.steps] == [("reactdummy_get_echo", {"word": "안녕"})]
    assert out.observations == [{"echo": "안녕"}]
    # 첫 호출: 도구 정의만, 둘째 호출: assistant(tool_calls) + tool 관찰이 이어 붙음
    first, second = env.llm.calls
    assert first.tools and [t.name for t in first.tools] == ["reactdummy_get_echo"] and first.messages is None
    assert first.system == "너는 시험용 비서다. 메아리"
    assert second.messages is not None and [m.role for m in second.messages] == ["assistant", "tool"]
    assert '"echo": "안녕"' in second.messages[1].content
    assert len(env.recorder.of("tool_call")) == 1 and len(env.recorder.of("llm_call")) == 2


async def test_react_blocks_hidden_tool(env: Env) -> None:
    env.llm.script("worker", [_call("reactdummy_get_hidden", word="몰래")])
    with pytest.raises(ToolPermissionError):
        await _agent(env).react("worker", PROMPT, "몰래 불러")


async def test_react_recovers_from_bad_input(env: Env) -> None:
    env.llm.script(
        "worker", [_call("reactdummy_get_echo", word="x"), _call("reactdummy_get_echo", word="없음"), "포기합니다"]
    )
    out = await _agent(env).react("worker", PROMPT, "해 봐")
    assert out.answer == "포기합니다" and len(out.steps) == 2
    assert "인자가 올바르지 않습니다" in out.steps[0].observation  # 검증 실패도 관찰로
    assert "다른 단어로" in out.steps[1].observation  # hint가 모델에게 간다


async def test_react_step_limit_and_no_model(env: Env) -> None:
    env.llm.script("worker", [_call("reactdummy_get_echo", word="하나"), _call("reactdummy_get_echo", word="둘")])
    with pytest.raises(LlmUnavailableError, match="단계 상한"):
        await _agent(env).react("worker", PROMPT, "계속", max_steps=2)
    with pytest.raises(LlmUnavailableError):  # 등록된 응답이 없음 = 모델 없음
        await _agent(env).react("worker", PROMPT, "또")


def test_litellm_conversion_roundtrip() -> None:
    req = LlmRequest(
        role="worker",
        system="s",
        user="u",
        tools=[ToolDef(name="t_get_x", description="d", parameters={"type": "object"})],
        messages=[
            ChatMessage(
                role="assistant", content="", tool_calls=[ToolCall(id="c1", name="t_get_x", arguments={"a": 1})]
            ),
            ChatMessage(role="tool", content='{"ok": true}', tool_call_id="c1", name="t_get_x"),
        ],
    )
    msgs = to_openai_messages(req)
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "tool"]
    assert msgs[2]["tool_calls"][0]["function"] == {"name": "t_get_x", "arguments": '{"a": 1}'}
    assert to_openai_tools(req) == [
        {"type": "function", "function": {"name": "t_get_x", "description": "d", "parameters": {"type": "object"}}}
    ]
    back = parse_tool_calls({"tool_calls": msgs[2]["tool_calls"]})
    assert back == [ToolCall(id="c1", name="t_get_x", arguments={"a": 1})]
    with pytest.raises(LlmUnavailableError):
        parse_tool_calls({"tool_calls": [{"id": "x", "function": {"name": "n", "arguments": "{깨짐"}}]})
