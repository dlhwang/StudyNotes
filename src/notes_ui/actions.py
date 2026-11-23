"""답 아래 버튼(UiAction) 처리. 화면이 버튼을 그리고, 누르면 여기서 BE를 부른다.

| kind | 처리 |
|---|---|
| ask | 버튼의 text를 다음 질문으로 보낸다 |
| save_proposal | 그 답의 proposals[params.index]를 BE ``/proposals/accept``로 저장·반영 (누름 = 사용자 승인) |
| navigate | target 화면으로 이동 (review, notes) |
| backend | 이 서비스에는 아직 없다 |
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from notes_ui.api import BeApiError


class AcceptsProposals(Protocol):
    def accept(self, proposal: dict[str, Any], accepted_on: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ActionOutcome:
    kind: str
    ask_text: str | None = None
    page: str | None = None
    message: str | None = None
    ok: bool = True


def _applied_message(rec: dict[str, Any]) -> str:
    applied = rec.get("applied") or {}
    if rec.get("kind") == "quiz.cards_add":
        n = len(applied.get("card_ids") or [])
        return f"카드 {n}장을 저장했습니다." if n else "이미 저장된 카드입니다."
    if rec.get("kind") == "profile.update":
        return "선호를 기억했습니다. 다음 답부터 반영됩니다."
    return f"저장했습니다: {rec.get('title', '')}"


def handle_action(api: AcceptsProposals, reply: dict[str, Any], action: dict[str, Any], today: str) -> ActionOutcome:
    kind = str(action.get("kind") or "")
    if kind == "ask":
        return ActionOutcome(kind="ask", ask_text=str(action.get("text") or action.get("label") or ""))
    if kind == "navigate":
        return ActionOutcome(kind="navigate", page=str(action.get("target") or ""))
    if kind == "save_proposal":
        index = int((action.get("params") or {}).get("index", 0))
        proposals = list(reply.get("proposals") or [])
        if not 0 <= index < len(proposals):
            return ActionOutcome(kind=kind, message="저장할 제안을 찾지 못했습니다.", ok=False)
        try:
            rec = api.accept(proposals[index], today)
        except BeApiError as e:
            return ActionOutcome(kind=kind, message=f"저장하지 못했습니다: {e.detail}", ok=False)
        return ActionOutcome(kind=kind, message=_applied_message(rec))
    return ActionOutcome(kind=kind, message="아직 지원하지 않는 버튼입니다.", ok=False)
