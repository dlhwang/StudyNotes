"""Agent 이벤트 → 화면에 그릴 데이터. Streamlit 없이 시험할 수 있게 순수 함수로 둔다."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

AGENT_LABELS = {
    "notes": "노트 Agent",
    "quiz": "퀴즈 Agent",
    "review": "복습 코치 Agent",
    "orchestrator": "안내",
}


@dataclass
class ReplyView:
    agent: str
    label: str
    text: str
    badge: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    table: list[dict[str, Any]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnView:
    header: str = ""
    replies: list[ReplyView] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _table(data: dict[str, Any]) -> list[dict[str, Any]]:
    if data.get("cards"):
        return [
            {k: c.get(k, "") for k in ("question", "answer", "note_title", "due_date") if k in c} for c in data["cards"]
        ]
    if data.get("notes"):
        return [{"ID": n.get("id"), "제목": n.get("title"), "내용": n.get("why", "")} for n in data["notes"]]
    if data.get("stats"):
        labels = {
            "due_today": "오늘 복습",
            "overdue": "밀린 카드",
            "new_cards": "새 카드",
            "reviewed_7d": "7일 복습",
            "correct_rate_7d_pct": "7일 정답률(%)",
            "streak_days": "연속 학습일",
        }
        return [{"항목": v, "값": data["stats"].get(k)} for k, v in labels.items()]
    return []


def reply_view(reply: dict[str, Any]) -> ReplyView:
    agent = str(reply.get("agent") or "")
    source = reply.get("source")
    version = reply.get("prompt_version")
    badge = f"AI 답 · {version}" if source == "ai" else "규칙 답(모델 없이)"
    data = dict(reply.get("data") or {})
    return ReplyView(
        agent=agent,
        label=AGENT_LABELS.get(agent, agent),
        text=str(reply.get("text") or ""),
        badge=badge,
        citations=list(reply.get("citations") or []),
        trace=list(data.get("trace") or []),
        table=_table(data),
        actions=list(reply.get("actions") or []),
        raw=reply,
    )


def turn_view(events: list[dict[str, Any]]) -> TurnView:
    turn = TurnView()
    for e in events:
        kind = e.get("type")
        if kind == "orchestrator":
            turn.header = str(e.get("text") or "")
        elif kind == "agent_reply" and isinstance(e.get("reply"), dict):
            turn.replies.append(reply_view(e["reply"]))
        elif kind == "error":
            turn.errors.append(str(e.get("text") or "오류"))
    return turn
