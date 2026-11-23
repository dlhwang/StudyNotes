from __future__ import annotations

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from notes_api.routes.internal import PREFIX, READ_ONLY_POSTS
from tests.api.conftest import TODAY


def test_health_after_seed(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["notes"] == 5 and body["chunks"] > 5


def test_note_lifecycle_updates_index(client: TestClient) -> None:
    created = client.post(
        "/notebooks/NB-1/notes",
        json={"title": "Send API", "body": "Send는 병렬 분기로 여러 노드를 동시에 부른다", "tags": ["x"]},
    ).json()
    assert created["id"] == "N-6" and created["chunks"] == 1
    hits = client.post(f"{PREFIX}/notebooks/NB-1/search", json={"query": "병렬 분기 Send", "k": 3}).json()
    assert hits[0]["note_id"] == "N-6" and hits[0]["title"] == "Send API"
    client.put("/notes/N-6", json={"title": "Send API", "body": "완전히 다른 내용 무지개", "tags": []})
    hits = client.post(f"{PREFIX}/notebooks/NB-1/search", json={"query": "무지개", "k": 1}).json()
    assert hits[0]["note_id"] == "N-6" and "무지개" in hits[0]["text"]
    assert client.delete("/notes/N-6").status_code == 204
    assert client.get("/notes/N-6").status_code == 404
    hits = client.post(f"{PREFIX}/notebooks/NB-1/search", json={"query": "무지개", "k": 5}).json()
    assert all(h["note_id"] != "N-6" for h in hits)


def test_internal_api_is_read_only(api_app: FastAPI) -> None:
    for route in api_app.routes:
        if isinstance(route, APIRoute) and route.path.startswith(PREFIX):
            writes = route.methods - {"GET", "HEAD"}
            assert not writes or (writes == {"POST"} and route.path in READ_ONLY_POSTS), route.path


def test_internal_reads(client: TestClient) -> None:
    assert client.get(f"{PREFIX}/notebooks").json() == ["NB-1", "NB-2"]
    notes = client.get(f"{PREFIX}/notebooks/NB-1/notes", params={"query": "체크포인터"}).json()
    assert notes[0]["title"] == "체크포인터와 메모리"
    assert client.get(f"{PREFIX}/notes/N-1").json()["title"] == "StateGraph 기초"
    assert len(client.get(f"{PREFIX}/notebooks/NB-1/cards", params={"note_id": "N-1"}).json()) == 4
    stats = client.get(f"{PREFIX}/notebooks/NB-1/stats", params={"base_date": TODAY}).json()
    assert stats["total_cards"] == 7 and stats["correct_rate_7d_pct"] == 56
    profile = client.get(f"{PREFIX}/profile", params={"base_date": TODAY}).json()
    assert profile["weak_notes"][0]["note_id"] == "N-2"


def test_problem_details(client: TestClient) -> None:
    r = client.get(f"{PREFIX}/notes/N-99")
    assert r.status_code == 404 and "노트 목록" in r.json()["detail"]
    r = client.get(f"{PREFIX}/notebooks/NB-1/due", params={"base_date": "어제"})
    assert r.status_code == 400 and "날짜 형식" in r.json()["detail"]
    assert client.post(f"{PREFIX}/notebooks/NB-9/search", json={"query": "x"}).status_code == 404


def test_accept_proposal_twice_adds_cards_once(client: TestClient) -> None:
    draft = {
        "kind": "quiz.cards_add",
        "subject_id": "NB-1",
        "title": "카드 1장",
        "payload": {"note_id": "N-3", "cards": [{"question": "ReAct란?", "answer": "추론과 행동 반복"}]},
        "reasons": [],
        "source": "chat",
        "dedupe_key": "dk-1",
    }
    before = len(client.get("/notebooks/NB-1/cards").json())
    r1 = client.post("/proposals/accept", json={"proposal": draft, "accepted_on": TODAY}).json()
    r2 = client.post("/proposals/accept", json={"proposal": draft, "accepted_on": TODAY}).json()
    assert r1["id"] == r2["id"] and r1["status"] == "applied"
    assert len(client.get("/notebooks/NB-1/cards").json()) == before + 1


def test_review_changes_stats_and_plan(client: TestClient) -> None:
    due = client.get("/notebooks/NB-1/due", params={"base_date": TODAY}).json()
    before = client.get("/notebooks/NB-1/stats", params={"base_date": TODAY}).json()
    card = client.post(f"/cards/{due[0]['id']}/review", json={"grade": "good", "reviewed_on": TODAY}).json()
    assert card["due_date"] > TODAY
    after = client.get("/notebooks/NB-1/stats", params={"base_date": TODAY}).json()
    assert after["due_today"] == before["due_today"] - 1 and after["streak_days"] == 5
    assert client.post(f"/cards/{due[0]['id']}/review", json={"grade": "meh", "reviewed_on": TODAY}).status_code == 422

    plan = {
        "kind": "review.daily_plan",
        "subject_id": "NB-1",
        "title": "계획",
        "payload": {"base_date": TODAY, "card_ids": [due[1]["id"]]},
        "source": "agent",
        "dedupe_key": "plan-1",
    }
    client.post("/proposals/accept", json={"proposal": plan})
    got = client.get("/notebooks/NB-1/daily-plan", params={"base_date": TODAY}).json()
    assert got["plan"]["kind"] == "review.daily_plan" and [c["id"] for c in got["cards"]] == [due[1]["id"]]


def test_profile_update(client: TestClient) -> None:
    got = client.put("/profile", json={"quiz_difficulty": "hard"}).json()
    assert got["quiz_difficulty"] == "hard" and got["summary_length"] == "normal"
