"""화면이 쓰는 BE 공개 API 클라이언트(동기). 화면은 Agent에 직접 붙지 않고 이것만 쓴다."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx

from notes_ui.config import UiSettings
from notes_ui.sse import parse_sse_lines


class BeApiError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"{status}: {detail}")
        self.status = status
        self.detail = detail


class BeApi:
    def __init__(self, settings: UiSettings | None = None, client: httpx.Client | None = None) -> None:
        s = settings or UiSettings()
        self._http = client or httpx.Client(base_url=s.api_url, timeout=s.timeout_seconds)

    def _call(self, method: str, path: str, **kw: Any) -> Any:
        try:
            resp = self._http.request(method, path, **kw)
        except httpx.HTTPError as e:
            raise BeApiError(0, f"BE에 연결할 수 없습니다 ({type(e).__name__}). BE가 떠 있는지 확인하세요") from e
        if resp.status_code >= 400:
            try:
                body = resp.json()
                detail = str(body.get("detail") or body) if isinstance(body, dict) else str(body)
            except ValueError:
                detail = resp.text
            raise BeApiError(resp.status_code, detail)
        return None if resp.status_code == 204 else resp.json()

    # ── 상태·노트 ────────────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        return dict(self._call("GET", "/health"))

    def notebooks(self) -> list[dict[str, Any]]:
        return list(self._call("GET", "/notebooks"))

    def notes(self, notebook_id: str, query: str | None = None) -> list[dict[str, Any]]:
        params = {"query": query} if query else {}
        return list(self._call("GET", f"/notebooks/{notebook_id}/notes", params=params))

    def note(self, note_id: str) -> dict[str, Any]:
        return dict(self._call("GET", f"/notes/{note_id}"))

    def create_note(self, notebook_id: str, title: str, body: str, tags: list[str]) -> dict[str, Any]:
        payload = {"title": title, "body": body, "tags": tags}
        return dict(self._call("POST", f"/notebooks/{notebook_id}/notes", json=payload))

    def update_note(self, note_id: str, title: str, body: str, tags: list[str]) -> dict[str, Any]:
        return dict(self._call("PUT", f"/notes/{note_id}", json={"title": title, "body": body, "tags": tags}))

    def delete_note(self, note_id: str) -> None:
        self._call("DELETE", f"/notes/{note_id}")

    # ── 카드·복습 ────────────────────────────────────────────────────

    def cards(self, notebook_id: str, note_id: str | None = None) -> list[dict[str, Any]]:
        params = {"note_id": note_id} if note_id else {}
        return list(self._call("GET", f"/notebooks/{notebook_id}/cards", params=params))

    def due(self, notebook_id: str, base_date: str) -> list[dict[str, Any]]:
        return list(self._call("GET", f"/notebooks/{notebook_id}/due", params={"base_date": base_date}))

    def review(self, card_id: str, grade: str, reviewed_on: str) -> dict[str, Any]:
        return dict(self._call("POST", f"/cards/{card_id}/review", json={"grade": grade, "reviewed_on": reviewed_on}))

    def stats(self, notebook_id: str, base_date: str) -> dict[str, Any]:
        return dict(self._call("GET", f"/notebooks/{notebook_id}/stats", params={"base_date": base_date}))

    def daily_plan(self, notebook_id: str, base_date: str) -> dict[str, Any]:
        return dict(self._call("GET", f"/notebooks/{notebook_id}/daily-plan", params={"base_date": base_date}))

    def run_daily_review(self, base_date: str) -> list[dict[str, Any]]:
        return list(self._call("POST", "/jobs/daily-review", json={"base_date": base_date})["saved"])

    # ── 프로필·제안 ──────────────────────────────────────────────────

    def profile(self, base_date: str | None = None) -> dict[str, Any]:
        return dict(self._call("GET", "/profile", params={"base_date": base_date} if base_date else {}))

    def set_profile(self, summary_length: str | None = None, quiz_difficulty: str | None = None) -> dict[str, Any]:
        body = {"summary_length": summary_length, "quiz_difficulty": quiz_difficulty}
        return dict(self._call("PUT", "/profile", json=body))

    def accept(self, proposal: dict[str, Any], accepted_on: str) -> dict[str, Any]:
        return dict(self._call("POST", "/proposals/accept", json={"proposal": proposal, "accepted_on": accepted_on}))

    def reindex(self) -> int:
        return int(self._call("POST", "/admin/reindex")["chunks"])

    # ── 채팅 ─────────────────────────────────────────────────────────

    def new_thread(self) -> str:
        return str(self._call("POST", "/chat/threads")["thread_id"])

    def stream_chat(
        self, thread_id: str, text: str, notebook_id: str, screen: dict[str, Any]
    ) -> Iterator[dict[str, Any]]:
        body = {"thread_id": thread_id, "text": text, "notebook_id": notebook_id, "screen": screen}
        try:
            with self._http.stream("POST", "/chat/stream", json=body) as resp:
                if resp.status_code >= 400:
                    resp.read()
                    yield {"type": "error", "text": f"BE 오류 {resp.status_code}: {resp.text[:200]}"}
                    return
                yield from parse_sse_lines(resp.iter_lines())
        except httpx.HTTPError as e:
            yield {"type": "error", "text": f"BE에 연결할 수 없습니다 ({type(e).__name__})"}
