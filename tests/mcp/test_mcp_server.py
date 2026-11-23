"""MCP 서버: 도구 목록(조회만), 검색·노트·복습 카드 호출을 실제 BE 앱(메모리)으로.

MCP 클라이언트는 같은 작업(task) 안에서 열고 닫아야 해서 픽스처 대신 ``connect()``를 시험 안에서 쓴다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from mcp.client import Client

from notes_mcp.server import build_server
from tests.api.conftest import TODAY, make_test_app


@asynccontextmanager
async def connect() -> AsyncIterator[Client]:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=make_test_app()), base_url="http://be") as http:
        async with Client(build_server(http)) as client:
            yield client


async def test_tools_are_read_only() -> None:
    async with connect() as client:
        tools = (await client.list_tools()).tools
    assert sorted(t.name for t in tools) == ["get_note", "list_due_cards", "list_notebooks", "search_notes"]
    assert all(t.annotations and t.annotations.read_only_hint for t in tools)


async def test_search_then_get_note() -> None:
    async with connect() as client:
        res = await client.call_tool("search_notes", {"query": "체크포인터가 뭐야", "notebook_id": "NB-1", "k": 3})
        assert not res.is_error and res.structured_content is not None
        hits = res.structured_content["hits"]
        note = await client.call_tool("get_note", {"note_id": hits[0]["note_id"]})
    assert hits[0]["title"] == "체크포인터와 메모리" and hits[0]["note_id"] == "N-2"
    assert note.structured_content is not None and "thread_id" in note.structured_content["body"]


async def test_notebooks_and_due_cards() -> None:
    async with connect() as client:
        nbs = await client.call_tool("list_notebooks", {})
        due = await client.call_tool("list_due_cards", {"notebook_id": "NB-1", "base_date": TODAY})
    assert nbs.structured_content is not None
    assert [n["name"] for n in nbs.structured_content["notebooks"]] == ["LangGraph 공부", "파이썬 비동기"]
    assert due.structured_content is not None and due.structured_content["cards"]


async def test_errors_are_reported() -> None:
    async with connect() as client:
        res = await client.call_tool("get_note", {"note_id": "N-99"})
    assert res.is_error
