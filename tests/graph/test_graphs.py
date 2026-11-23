"""그래프 시험: 경로, 스트림 이벤트, 모델 실패 시 규칙 답, 안내 답, 예약 그래프의 중복 방지 키 (AGENTS.md §8)."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from study_notes.core.context import AgentContext
from study_notes.graphs.chat import build_chat_graph
from study_notes.graphs.daily_check import build_daily_check_graph
from study_notes.tools.fakes.be import DEMO_SUBJECT
from tests.conftest import Env

CTX = AgentContext(subject_id=DEMO_SUBJECT)


def _cfg(thread: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread, "user_id": "u1"}}


async def _ask(graph: Any, thread: str, text: str, ctx: AgentContext = CTX) -> dict[str, Any]:
    out: dict[str, Any] = await graph.ainvoke(
        {"messages": [{"role": "user", "content": text}]}, _cfg(thread), context=ctx
    )
    return out


async def test_rule_answer(env: Env) -> None:
    out = await _ask(build_chat_graph(InMemorySaver()), "chat:u1:a", "오늘 할 일 보여줘")
    assert out["intents"] == ["task_list"]
    reply = out["replies"][0]
    assert reply["agent"] == "tasks" and reply["source"] == "rule"
    assert "열린 할 일 2건" in reply["text"] and "__interrupt__" not in out


async def test_custom_stream_events(env: Env) -> None:
    g = build_chat_graph(InMemorySaver())
    events = [
        chunk
        async for mode, chunk in g.astream(
            {"messages": [{"role": "user", "content": "할 일 보여줘"}]},
            _cfg("chat:u1:s"),
            context=CTX,
            stream_mode=["custom", "values"],
        )
        if mode == "custom"
    ]
    assert [e["type"] for e in events] == ["orchestrator", "agent_reply"]
    assert all(e["schema_version"] == 1 for e in events)


async def test_llm_answer_when_model_available(env: Env) -> None:
    env.llm.reply_for("worker", "왜", "협력사 견적이 새로 들어와 검토가 필요합니다.")
    out = await _ask(build_chat_graph(InMemorySaver()), "chat:u1:f", "견적서 검토 할 일 왜 생겼어?")
    reply = out["replies"][0]
    assert reply["source"] == "ai" and reply["prompt_version"] == "tasks.explain.v1"
    assert reply["citations"][0]["title"] == "할 일 T-1"
    assert env.recorder.of("llm_call")


async def test_falls_back_to_rule_when_model_down(env: Env) -> None:
    out = await _ask(build_chat_graph(InMemorySaver()), "chat:u1:g", "견적서 검토 할 일 왜 생겼어?")
    reply = out["replies"][0]
    assert reply["source"] == "rule" and "협력사 견적이 새로 들어왔다" in reply["text"]


async def test_unknown_question_gets_help(env: Env) -> None:
    out = await _ask(build_chat_graph(InMemorySaver()), "chat:u1:h", "안녕하세요")
    assert out["intents"] == []
    reply = out["replies"][0]
    assert reply["agent"] == "orchestrator" and "할 일 목록 보기" in reply["text"]


async def test_missing_subject_is_explained(env: Env) -> None:
    out = await _ask(build_chat_graph(InMemorySaver()), "chat:u1:m", "할 일 보여줘", AgentContext())
    assert "무엇에 대한 질문인지" in out["replies"][0]["text"]


async def test_daily_check_returns_drafts_with_stable_keys(env: Env) -> None:
    g = build_daily_check_graph(InMemorySaver())
    outs = [await g.ainvoke({"base_date": "2026-11-23"}, {"configurable": {"thread_id": f"dc-{i}"}}) for i in range(2)]
    first, second = (o["proposals"] for o in outs)
    assert [(p["kind"], p["source_ref"]) for p in first] == [("task.overdue_notice", "T-1")]
    assert first[0]["subject_id"] == DEMO_SUBJECT and first[0]["source"] == "agent"
    # 두 번 돌아도 키가 같다 → BE가 한 번만 저장
    assert [p["dedupe_key"] for p in first] == [p["dedupe_key"] for p in second]
