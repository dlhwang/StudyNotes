"""BE ↔ Agent 연결: SSE 중계, 대화 메모리, 제안 수락, 예약 실행 (같은 프로세스 Agent + 가짜 모델)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from notes_api.bridge import AegraBridge
from study_notes.deps import set_deps
from tests.api.conftest import TODAY, make_test_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(make_test_app())
    set_deps(None)  # 같은 프로세스 Agent가 바꿔 둔 의존성을 되돌린다


def chat(client: TestClient, thread: str, text: str, **screen: str) -> list[dict[str, Any]]:
    body = {"thread_id": thread, "text": text, "notebook_id": "NB-1", "screen": {"base_date": TODAY, **screen}}
    with client.stream("POST", "/chat/stream", json=body) as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        return [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]


def test_stream_qa_then_quiz_then_accept(client: TestClient) -> None:
    thread = client.post("/chat/threads").json()["thread_id"]
    assert thread.startswith("chat:local-user:")

    events = chat(client, thread, "체크포인터가 뭐야?")
    assert [e["type"] for e in events] == ["orchestrator", "agent_reply", "done"]
    reply = events[1]["reply"]
    assert reply["agent"] == "notes" and reply["citations"][0]["title"] == "체크포인터와 메모리"

    events = chat(client, thread, "그 노트로 퀴즈 내줘")  # 대화 메모리 → 같은 노트
    quiz = events[1]["reply"]
    (draft,) = quiz["proposals"]
    assert draft["payload"]["note_id"] == "N-2"
    questions = [c["question"] for c in draft["payload"]["cards"]]
    assert "체크포인터란 무엇인가?" not in questions and len(questions) == 3  # 시드에 이미 있는 카드는 뺀다

    before = len(client.get("/notebooks/NB-1/cards", params={"note_id": "N-2"}).json())
    for _ in range(2):  # 두 번 눌러도 한 번만
        rec = client.post("/proposals/accept", json={"proposal": draft, "accepted_on": TODAY}).json()
        assert rec["status"] == "applied"
    after = client.get("/notebooks/NB-1/cards", params={"note_id": "N-2"}).json()
    assert len(after) == before + 3


def test_profile_memory_changes_next_summary(client: TestClient) -> None:
    thread = client.post("/chat/threads").json()["thread_id"]
    pref = chat(client, thread, "앞으로 요약은 짧게 해줘")[1]["reply"]
    client.post("/proposals/accept", json={"proposal": pref["proposals"][0]})
    summary = chat(client, thread, "StateGraph 기초 요약해줘")[1]["reply"]
    assert len(summary["data"]["key_points"]) == 3  # 장기 메모리(short) 반영


def test_screen_note_and_unknown_notebook(client: TestClient) -> None:
    thread = client.post("/chat/threads").json()["thread_id"]
    reply = chat(client, thread, "이 노트 요약해줘", note_id="N-3")[1]["reply"]
    assert reply["citations"][0]["title"] == "도구 호출과 ReAct"
    r = client.post("/chat/stream", json={"thread_id": thread, "text": "안녕", "notebook_id": "NB-9"})
    assert r.status_code == 404


def test_daily_review_job_saves_once(client: TestClient) -> None:
    first = client.post("/jobs/daily-review", json={"base_date": TODAY}).json()["saved"]
    second = client.post("/jobs/daily-review", json={"base_date": TODAY}).json()["saved"]
    assert [(p["kind"], p["subject_id"]) for p in first] == [
        ("review.daily_plan", "NB-1"),
        ("review.daily_plan", "NB-2"),
    ]
    assert [p["id"] for p in first] == [p["id"] for p in second]
    plan = client.get("/notebooks/NB-1/daily-plan", params={"base_date": TODAY}).json()
    assert plan["plan"]["source"] == "agent" and len(plan["cards"]) == len(first[0]["payload"]["card_ids"])


class _FakeSdk:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

        async def create(**kw: Any) -> dict[str, str]:
            self.calls.append(("create", kw))
            return {"thread_id": "th-1"}

        async def stream(thread_id: str, assistant: str, **kw: Any) -> AsyncIterator[Any]:
            self.calls.append(("stream", (thread_id, assistant, kw)))
            yield SimpleNamespace(event="metadata", data={"run_id": "r"})
            yield SimpleNamespace(event="custom", data={"type": "agent_reply", "reply": {"text": "hi"}})

        async def wait(thread_id: str, assistant: str, **kw: Any) -> dict[str, Any]:
            self.calls.append(("wait", (thread_id, assistant, kw)))
            return {"proposals": [{"kind": "review.daily_plan"}]}

        self.threads = SimpleNamespace(create=create)
        self.runs = SimpleNamespace(stream=stream, wait=wait)


async def test_aegra_bridge_maps_sdk_calls() -> None:
    sdk = _FakeSdk()
    bridge = AegraBridge("http://aegra", "u1", "학습자", client=sdk)
    assert await bridge.new_thread("u1") == "th-1"
    events = [e async for e in bridge.stream_chat("th-1", "u1", "안녕", "NB-1", {"base_date": TODAY})]
    assert events == [{"type": "agent_reply", "reply": {"text": "hi"}}]
    _, (tid, assistant, kw) = sdk.calls[1]
    assert (tid, assistant) == ("th-1", "chat") and kw["context"] == {
        "subject_id": "NB-1",
        "screen": {"base_date": TODAY},
    }
    assert kw["stream_mode"] == ["custom"]
    assert await bridge.run_daily_review(TODAY, None) == [{"kind": "review.daily_plan"}]
