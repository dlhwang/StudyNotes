"""chat 그래프 + quiz Agent: 제안 초안·버튼·중복 방지 키, Structured Output 검증, 다중 의도, 대화 메모리."""

from __future__ import annotations

import json

from langgraph.checkpoint.memory import InMemorySaver

from study_notes.graphs.chat import build_chat_graph
from tests.conftest import Env
from tests.graph.test_notes_graph import ask


async def test_quiz_rule_answer_has_proposal_and_button(env: Env) -> None:
    out = await ask(build_chat_graph(InMemorySaver()), "chat:u1:q1", "StateGraph 기초 퀴즈 2개 내줘")
    assert out["intents"] == ["quiz_make"]
    reply = out["replies"][0]
    assert reply["agent"] == "quiz" and reply["source"] == "rule"
    (draft,) = reply["proposals"]
    assert draft["kind"] == "quiz.cards_add" and draft["subject_id"] == "NB-1" and draft["source"] == "chat"
    assert draft["payload"]["note_id"] == "N-1"
    assert [c["question"] for c in draft["payload"]["cards"]] == ["노드란 무엇인가?", "엣지란 무엇인가?"]
    save = reply["actions"][0]
    assert save == {
        "kind": "save_proposal",
        "label": "카드 2장 저장",
        "target": None,
        "text": None,
        "params": {"index": 0},
    }
    assert out["focus_note_ids"] == ["N-1"]


async def test_same_request_same_dedupe_key(env: Env) -> None:
    g = build_chat_graph(InMemorySaver())
    keys = []
    for thread in ("chat:u1:k", "chat:u1:k", "chat:u1:other"):
        out = await ask(g, thread, "StateGraph 기초 퀴즈 내줘")
        keys.append(out["replies"][0]["proposals"][0]["dedupe_key"])
    assert keys[0] == keys[1] != keys[2]


async def test_quiz_model_cards_are_grounded(env: Env) -> None:
    body = {
        "reasoning": "노드와 리듀서를 묻자",
        "cards": [
            {
                "question": "노드는 무엇을 돌려주나?",
                "answer": "부분 업데이트",
                "evidence": "- 노드: 상태를 받아 부분 업데이트를 돌려주는 함수",
            },
            {
                "question": "StateGraph는 누가 만들었나?",
                "answer": "모름",
                "evidence": "StateGraph는 2020년에 발표되었다",
            },
        ],
    }
    env.llm.reply_for("worker", "퀴즈", json.dumps(body, ensure_ascii=False))
    out = await ask(build_chat_graph(InMemorySaver()), "chat:u1:q2", "StateGraph 기초 퀴즈 내줘")
    reply = out["replies"][0]
    assert reply["source"] == "ai" and reply["prompt_version"] == "quiz.make.v1"
    assert [c["question"] for c in reply["proposals"][0]["payload"]["cards"]] == ["노드는 무엇을 돌려주나?"]
    system = env.llm.calls[-1].system
    assert "난이도: normal" in system and "- 리듀서란?" in system  # 프로필·기존 카드가 프롬프트에


async def test_summary_and_quiz_in_one_question(env: Env) -> None:
    out = await ask(build_chat_graph(InMemorySaver()), "chat:u1:q3", "체크포인터와 메모리 요약하고 퀴즈도 내줘")
    assert out["intents"] == ["note_summary", "quiz_make"]
    assert [r["agent"] for r in out["replies"]] == ["notes", "quiz"]
    assert out["replies"][1]["proposals"][0]["payload"]["note_id"] == "N-2"


async def test_that_note_from_memory(env: Env) -> None:
    g = build_chat_graph(InMemorySaver())
    await ask(g, "chat:u1:q4", "ReAct 패턴 설명해줘")
    out = await ask(g, "chat:u1:q4", "그 노트로 퀴즈 내줘")
    assert out["replies"][0]["proposals"][0]["payload"]["note_id"] == "N-3"


async def test_quiz_without_target_asks_which_note(env: Env) -> None:
    out = await ask(build_chat_graph(InMemorySaver()), "chat:u1:q5", "퀴즈 내줘")
    reply = out["replies"][0]
    assert reply["text"].startswith("어느 노트로") and not reply["proposals"]
    assert next(a["text"] for a in reply["actions"]) == "StateGraph 기초 퀴즈 내줘"
