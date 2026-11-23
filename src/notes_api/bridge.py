"""BE → Agent 호출. 화면은 Agent에 직접 붙지 않는다 (FE → BE → Agent).

- ``InProcessBridge``: BE 프로세스 안에서 그래프를 바로 돌린다. PostgreSQL·Aegra 없이 개발·시험할 때.
  Agent의 BE 조회(``HttpBeClient``)는 네트워크 없이 같은 BE 앱(ASGI)의 ``/internal/agent``로 간다.
- ``AegraBridge``: 떠 있는 Aegra 서버를 langgraph-sdk로 부른다. 대화 상태는 Aegra(PostgreSQL)가 보관한다.

두 구현 모두 Agent의 custom 이벤트(``orchestrator``, ``agent_reply``)를 그대로 흘려보낸다.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any, Protocol
from urllib.parse import quote

import httpx
from fastapi import FastAPI

from notes_api.config import ApiSettings


class AgentBridge(Protocol):
    async def new_thread(self, user_id: str) -> str: ...
    def stream_chat(
        self, thread_id: str, user_id: str, text: str, notebook_id: str, screen: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]: ...
    async def run_daily_review(self, base_date: str, notebook_ids: list[str] | None) -> list[dict[str, Any]]: ...


def _chat_input(text: str) -> dict[str, Any]:
    return {"messages": [{"role": "user", "content": text}]}


class InProcessBridge:
    def __init__(self, app: FastAPI) -> None:
        self.app = app
        self._ready = False
        self._chat: Any = None
        self._daily: Any = None
        self._deps: Any = None

    def _ensure(self) -> None:
        """처음 쓸 때 그래프와 Agent 의존성을 만든다. 매번 Agent deps를 이 BE로 다시 맞춘다."""
        from study_notes.deps import Deps, build_deps, set_deps

        if not self._ready:
            from langgraph.checkpoint.memory import InMemorySaver

            from study_notes.config import get_settings
            from study_notes.graphs.chat import build_chat_graph
            from study_notes.graphs.daily_review import build_daily_review_graph
            from study_notes.tools.be_client.http import HttpBeClient

            settings = get_settings()
            base = build_deps(settings)
            client = httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app),
                base_url="http://notes-be" + settings.be.path_prefix,
                timeout=settings.be.timeout_seconds,
            )
            self._deps = Deps(
                settings=settings,
                be=HttpBeClient(settings.be, client=client),
                llm=base.llm,
                recorder=base.recorder,
            )
            self._chat = build_chat_graph(InMemorySaver())
            self._daily = build_daily_review_graph(InMemorySaver())
            self._ready = True
        set_deps(self._deps)

    async def new_thread(self, user_id: str) -> str:
        from study_notes.core.ids import new_thread_id

        return new_thread_id("chat", user_id)

    async def stream_chat(
        self, thread_id: str, user_id: str, text: str, notebook_id: str, screen: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        from study_notes.core.context import AgentContext

        self._ensure()
        config = {"configurable": {"thread_id": thread_id, "user_id": user_id}}
        context = AgentContext(subject_id=notebook_id, screen=dict(screen))
        async for _mode, chunk in self._chat.astream(
            _chat_input(text), config, context=context, stream_mode=["custom"]
        ):
            yield dict(chunk)

    async def run_daily_review(self, base_date: str, notebook_ids: list[str] | None) -> list[dict[str, Any]]:
        self._ensure()
        config = {"configurable": {"thread_id": f"daily_review:{base_date}:{uuid.uuid4()}"}}
        out = await self._daily.ainvoke({"base_date": base_date, "subject_ids": notebook_ids}, config)
        return list(out.get("proposals") or [])


class AegraBridge:
    def __init__(self, url: str, user_id: str, user_name: str, client: Any = None) -> None:
        self.url = url
        self.user_id = user_id
        self.user_name = user_name
        self._client = client

    def _sdk(self) -> Any:
        if self._client is None:
            from langgraph_sdk import get_client

            # 헤더는 ASCII만 되므로 한글 이름은 URL 인코딩 (server/auth.py가 되돌린다)
            headers = {"X-User-Id": self.user_id, "X-User-Name": quote(self.user_name), "X-User-Role": "user"}
            self._client = get_client(url=self.url, headers=headers)
        return self._client

    async def new_thread(self, user_id: str) -> str:
        thread = await self._sdk().threads.create(metadata={"entry": "chat"})
        return str(thread["thread_id"])

    async def stream_chat(
        self, thread_id: str, user_id: str, text: str, notebook_id: str, screen: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        context = {"subject_id": notebook_id, "screen": dict(screen)}
        async for part in self._sdk().runs.stream(
            thread_id, "chat", input=_chat_input(text), context=context, stream_mode=["custom"]
        ):
            if part.event == "custom" and isinstance(part.data, dict):
                yield dict(part.data)

    async def run_daily_review(self, base_date: str, notebook_ids: list[str] | None) -> list[dict[str, Any]]:
        sdk = self._sdk()
        thread = await sdk.threads.create(metadata={"entry": "daily_review"})
        out = await sdk.runs.wait(
            thread["thread_id"], "daily_review", input={"base_date": base_date, "subject_ids": notebook_ids}
        )
        return list((out or {}).get("proposals") or [])


def build_bridge(settings: ApiSettings, app: FastAPI) -> AgentBridge:
    if settings.agent_mode == "aegra":
        return AegraBridge(settings.aegra_url, settings.user_id, settings.user_name)
    return InProcessBridge(app)
