"""채팅·예약 실행 중계. 화면 → BE → Agent.

- ``POST /chat/stream``은 Agent의 custom 이벤트를 SSE(``data: {json}``)로 흘려보내고 ``{"type":"done"}``으로 끝낸다.
- ``POST /jobs/daily-review``는 예약 그래프를 돌려 돌려받은 제안을 BE가 저장한다(규칙: 예약 결과 저장은 BE의 일).
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from notes_api.bridge import AgentBridge
from notes_api.deps import AppState, app_state
from notes_api.store import ProposalRecord

router = APIRouter()
log = logging.getLogger("notes_api.chat")


def get_bridge(request: Request) -> AgentBridge:
    bridge: AgentBridge = request.app.state.bridge
    return bridge


class ChatIn(BaseModel):
    thread_id: str
    text: str = Field(min_length=1, max_length=2000)
    notebook_id: str
    screen: dict[str, Any] = Field(default_factory=dict)


class DailyReviewIn(BaseModel):
    base_date: str
    notebook_ids: list[str] | None = None


class DailyReviewOut(BaseModel):
    saved: list[ProposalRecord]


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/chat/threads")
async def new_thread(s: AppState = Depends(app_state), bridge: AgentBridge = Depends(get_bridge)) -> dict[str, str]:
    return {"thread_id": await bridge.new_thread(s.settings.user_id)}


@router.post("/chat/stream")
async def chat_stream(
    body: ChatIn, s: AppState = Depends(app_state), bridge: AgentBridge = Depends(get_bridge)
) -> StreamingResponse:
    s.store.get_notebook(body.notebook_id)  # 없는 노트북이면 404

    async def events() -> AsyncIterator[str]:
        try:
            async for ev in bridge.stream_chat(
                body.thread_id, s.settings.user_id, body.text, body.notebook_id, body.screen
            ):
                yield _sse(ev)
        except Exception as e:  # 스트림 중 오류는 이벤트로 알리고 끝낸다
            log.exception("Agent 호출 실패")
            yield _sse({"type": "error", "text": f"Agent 호출에 실패했습니다: {type(e).__name__}"})
        yield _sse({"type": "done"})

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.post("/jobs/daily-review")
async def daily_review(
    body: DailyReviewIn, s: AppState = Depends(app_state), bridge: AgentBridge = Depends(get_bridge)
) -> DailyReviewOut:
    proposals = await bridge.run_daily_review(body.base_date, body.notebook_ids)
    return DailyReviewOut(saved=[s.store.accept_proposal(p, body.base_date) for p in proposals])
