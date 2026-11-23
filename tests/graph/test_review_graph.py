"""chat 그래프 + review Agent, daily_review 예약 그래프."""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver

from study_notes.graphs.chat import build_chat_graph
from study_notes.graphs.daily_review import build_daily_review_graph
from study_notes.tools.fakes.be import DEMO_DATE
from tests.conftest import Env
from tests.graph.test_notes_graph import ask


async def test_review_today(env: Env) -> None:
    out = await ask(build_chat_graph(InMemorySaver()), "chat:u1:r1", "오늘 뭐 복습해?")
    reply = out["replies"][0]
    assert out["intents"] == ["review_today"] and reply["agent"] == "review"
    assert reply["text"].startswith("오늘 복습할 카드 3장(밀린 카드 1장)")
    assert reply["actions"][0]["kind"] == "navigate" and reply["actions"][0]["target"] == "review"
    assert [c["id"] for c in reply["data"]["cards"]] == ["C-1", "C-2", "C-3"]


async def test_review_today_empty(env: Env) -> None:
    env.be.cards = []
    out = await ask(build_chat_graph(InMemorySaver()), "chat:u1:r2", "오늘 뭐 복습해?")
    assert out["replies"][0]["text"].startswith("오늘 복습할 카드가 없습니다")


async def test_review_stats_rule_uses_be_numbers(env: Env) -> None:
    out = await ask(build_chat_graph(InMemorySaver()), "chat:u1:r3", "공부 현황 어때?")
    reply = out["replies"][0]
    assert reply["source"] == "rule"
    assert "정답률 56%" in reply["text"] and "연속 학습 4일" in reply["text"]
    assert "'체크포인터와 메모리'(최근 2주 3번 다시)" in reply["text"]
    assert reply["actions"][0]["text"] == "체크포인터와 메모리 요약해줘"


async def test_review_stats_model_coaching(env: Env) -> None:
    env.llm.reply_for("worker", "현황", "4일째 꾸준히 복습 중이에요. 오늘은 밀린 1장부터 넘겨 보세요.")
    out = await ask(build_chat_graph(InMemorySaver()), "chat:u1:r4", "공부 현황 어때?")
    reply = out["replies"][0]
    assert reply["source"] == "ai" and reply["prompt_version"] == "review.coach.v1"
    assert "정답률 56%" in env.llm.calls[-1].system  # 숫자는 BE 값이 프롬프트로 들어간다


async def test_profile_update_proposal(env: Env) -> None:
    out = await ask(build_chat_graph(InMemorySaver()), "chat:u1:r5", "앞으로 요약은 짧게 해줘")
    reply = out["replies"][0]
    assert out["intents"] == ["profile_update"]
    (draft,) = reply["proposals"]
    assert draft["kind"] == "profile.update" and draft["payload"] == {"summary_length": "short"}
    assert reply["actions"][0]["kind"] == "save_proposal"


async def test_daily_review_graph_stable_keys(env: Env) -> None:
    g = build_daily_review_graph(InMemorySaver())
    outs = [await g.ainvoke({"base_date": DEMO_DATE}, {"configurable": {"thread_id": f"dr-{i}"}}) for i in range(2)]
    first, second = (o["proposals"] for o in outs)
    assert [(p["kind"], p["subject_id"]) for p in first] == [("review.daily_plan", "NB-1")]  # NB-2는 복습할 카드 없음
    assert first[0]["payload"] == {"base_date": DEMO_DATE, "card_ids": ["C-1", "C-2", "C-3"]}
    assert [p["dedupe_key"] for p in first] == [p["dedupe_key"] for p in second]
    assert all(r.data["agent"] == "review" for r in env.recorder.of("tool_call"))
