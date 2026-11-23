"""chat 그래프 + notes Agent: 경로, 스트림 이벤트, 규칙 답·모델 답, ReAct, 대화 메모리 (AGENTS.md §8)."""

from __future__ import annotations

import json
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from study_notes.core.context import AgentContext
from study_notes.graphs.chat import build_chat_graph
from study_notes.llm.gateway import LlmResult, ToolCall
from study_notes.tools.fakes.be import DEMO_DATE, DEMO_SUBJECT
from tests.conftest import Env

CTX = AgentContext(subject_id=DEMO_SUBJECT, screen={"base_date": DEMO_DATE})


def _cfg(thread: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread, "user_id": "u1"}}


async def ask(graph: Any, thread: str, text: str, ctx: AgentContext = CTX) -> dict[str, Any]:
    out: dict[str, Any] = await graph.ainvoke(
        {"messages": [{"role": "user", "content": text}]}, _cfg(thread), context=ctx
    )
    return out


async def test_summary_rule_answer(env: Env) -> None:
    out = await ask(build_chat_graph(InMemorySaver()), "chat:u1:a", "StateGraph 기초 요약해줘")
    assert out["intents"] == ["note_summary"]
    reply = out["replies"][0]
    assert reply["agent"] == "notes" and reply["source"] == "rule"
    assert "'StateGraph 기초' 핵심 4가지" in reply["text"] and "리듀서" not in reply["text"].split("\n")[1]
    assert reply["citations"] == [{"title": "StateGraph 기초", "location": "N-1"}]
    assert reply["actions"][0]["text"] == "StateGraph 기초 퀴즈 내줘"
    assert out["focus_note_ids"] == ["N-1"] and "__interrupt__" not in out


async def test_summary_uses_profile_length(env: Env) -> None:
    env.be.profile.summary_length = "short"
    out = await ask(build_chat_graph(InMemorySaver()), "chat:u1:p", "StateGraph 기초 요약해줘")
    assert len(out["replies"][0]["data"]["key_points"]) == 3


async def test_summary_model_answer_hides_reasoning(env: Env) -> None:
    body = {
        "reasoning": "비밀 생각",
        "key_points": ["노드는 부분 업데이트를 돌려준다", "엣지는 연결이다"],
        "one_line": "그래프 기초",
    }
    env.llm.reply_for("worker", "요약", json.dumps(body, ensure_ascii=False))
    out = await ask(build_chat_graph(InMemorySaver()), "chat:u1:b", "StateGraph 기초 요약해줘")
    reply = out["replies"][0]
    assert reply["source"] == "ai" and reply["prompt_version"] == "notes.summary.v1"
    assert "그래프 기초" in reply["text"] and "비밀 생각" not in reply["text"]
    assert "StateGraph는 상태 스키마" in env.llm.calls[0].system  # 노트 본문이 프롬프트에 들어간다


async def test_search_merges_keyword_and_vector(env: Env) -> None:
    out = await ask(build_chat_graph(InMemorySaver()), "chat:u1:c", "체크포인터 노트 찾아줘")
    reply = out["replies"][0]
    assert out["intents"] == ["note_search"]
    assert reply["data"]["notes"][0]["id"] == "N-2" and "체크포인터와 메모리(N-2)" in reply["text"]


async def test_qa_rule_answer_from_rag(env: Env) -> None:
    out = await ask(build_chat_graph(InMemorySaver()), "chat:u1:d", "체크포인터가 뭐야?")
    reply = out["replies"][0]
    assert out["intents"] == ["note_qa"] and reply["source"] == "rule"
    assert reply["text"].startswith("노트에서 찾은 내용입니다") and "체크포인터" in reply["text"]
    assert reply["citations"][0]["location"].startswith("N-2 · 체크포인터와 메모리")
    assert out["focus_note_ids"][0] == "N-2"


async def test_qa_react_with_tool_calls(env: Env) -> None:
    call = ToolCall(id="c1", name="notes_search_chunks", arguments={"query": "체크포인터"})
    env.llm.script(
        "worker",
        [
            LlmResult(text="노트에서 체크포인터를 찾아야 한다", role="worker", tool_calls=[call]),
            "체크포인터는 단계마다 상태를 저장하는 장치입니다. (체크포인터와 메모리)",
        ],
    )
    out = await ask(build_chat_graph(InMemorySaver()), "chat:u1:e", "체크포인터가 뭐야?")
    reply = out["replies"][0]
    assert reply["source"] == "ai" and reply["prompt_version"] == "notes.qa.v1"
    assert reply["data"]["trace"][0]["tool"] == "notes_search_chunks"
    assert reply["citations"][0]["title"] == "체크포인터와 메모리"
    assert len(env.recorder.of("llm_call")) == 2 and env.recorder.of("tool_call")


async def test_qa_nothing_found(env: Env) -> None:
    out = await ask(build_chat_graph(InMemorySaver()), "chat:u1:f", "양자역학 파동함수가 뭐야?")
    assert out["replies"][0]["text"].startswith("노트에 관련 내용이 없습니다")


async def test_memory_follows_that_note(env: Env) -> None:
    g = build_chat_graph(InMemorySaver())
    await ask(g, "chat:u1:m", "체크포인터와 메모리 요약해줘")
    out = await ask(g, "chat:u1:m", "그 노트 핵심만 다시")
    assert out["replies"][0]["citations"][0]["location"] == "N-2"
    other = await ask(g, "chat:u1:other", "그 노트 핵심만 다시")  # 다른 thread는 기억이 없다
    assert other["replies"][0]["text"].startswith("어떤 노트를 요약할지")


async def test_screen_note_is_used(env: Env) -> None:
    ctx = AgentContext(subject_id=DEMO_SUBJECT, screen={"note_id": "N-3", "base_date": DEMO_DATE})
    out = await ask(build_chat_graph(InMemorySaver()), "chat:u1:s", "이 노트 요약해줘", ctx)
    assert out["replies"][0]["citations"][0]["title"] == "도구 호출과 ReAct"


async def test_custom_stream_events(env: Env) -> None:
    g = build_chat_graph(InMemorySaver())
    events = [
        chunk
        async for mode, chunk in g.astream(
            {"messages": [{"role": "user", "content": "노트 목록 보여줘"}]},
            _cfg("chat:u1:st"),
            context=CTX,
            stream_mode=["custom", "values"],
        )
        if mode == "custom"
    ]
    assert [e["type"] for e in events] == ["orchestrator", "agent_reply"]
    assert all(e["schema_version"] == 1 for e in events)


async def test_unknown_question_gets_help(env: Env) -> None:
    out = await ask(build_chat_graph(InMemorySaver()), "chat:u1:h", "안녕하세요")
    assert out["intents"] == []
    reply = out["replies"][0]
    assert reply["agent"] == "orchestrator" and "노트 요약하기" in reply["text"]


async def test_missing_subject_is_explained(env: Env) -> None:
    out = await ask(build_chat_graph(InMemorySaver()), "chat:u1:x", "노트 목록 보여줘", AgentContext())
    assert "무엇에 대한 질문인지" in out["replies"][0]["text"]
