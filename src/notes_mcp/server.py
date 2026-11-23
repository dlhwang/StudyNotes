"""학습 노트 MCP 서버 — 다른 에이전트(Claude Desktop, Claude Code 등)가 이 서비스의 노트 지식을 쓰게 한다.

- 도구는 **조회만** 있다(readOnlyHint). 쓰기는 사람이 화면에서 한다 — Agent와 같은 원칙.
- 도구는 BE HTTP API를 부른다: 노트북 목록은 공개 API, 나머지는 Agent용 내부 조회 API(``/internal/agent``).
- 결과는 구조화 데이터(dict)로 돌려주고, 검색 결과에는 출처(노트 제목·소제목·ID)를 함께 준다.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

INTERNAL = "/internal/agent"
READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)

INSTRUCTIONS = """사용자의 학습 노트(노트북 → 노트 → 복습 카드)를 조회한다.
먼저 list_notebooks로 노트북 ID를 확인하고, 질문에 답할 때는 search_notes로 근거 조각을 찾은 뒤
필요하면 get_note로 노트 전체를 읽는다. 답에는 근거 노트 제목을 밝힌다. 이 서버로는 노트를 바꿀 수 없다."""


async def _get(http: httpx.AsyncClient, method: str, path: str, **kw: Any) -> Any:
    resp = await http.request(method, path, **kw)
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail") or resp.text
        except ValueError:
            detail = resp.text
        raise ValueError(f"BE 오류 {resp.status_code}: {detail}")
    return resp.json()


def build_server(http: httpx.AsyncClient) -> MCPServer:
    """``http``는 BE 주소를 base_url로 가진 클라이언트(시험에서는 ASGI 전송)."""
    server = MCPServer(name="study-notes", title="학습 노트", instructions=INSTRUCTIONS, version="0.1.0")

    @server.tool(annotations=READ_ONLY)
    async def list_notebooks() -> dict[str, Any]:
        """노트북(공부 묶음) 목록. 다른 도구의 notebook_id를 여기서 고른다."""
        return {"notebooks": await _get(http, "GET", "/notebooks")}

    @server.tool(annotations=READ_ONLY)
    async def search_notes(query: str, notebook_id: str = "NB-1", k: int = 5) -> dict[str, Any]:
        """노트 조각을 의미 검색(RAG)한다. 질문에 답할 근거를 찾을 때 쓴다.

        score(0~1)가 0.15보다 낮으면 관련이 약하다. 결과마다 note_id·title·heading(출처)이 있다.
        """
        hits = await _get(
            http, "POST", f"{INTERNAL}/notebooks/{notebook_id}/search", json={"query": query, "k": max(1, min(k, 10))}
        )
        return {
            "query": query,
            "hits": [{k2: h[k2] for k2 in ("note_id", "title", "heading", "text", "score")} for h in hits],
        }

    @server.tool(annotations=READ_ONLY)
    async def get_note(note_id: str) -> dict[str, Any]:
        """노트 한 개의 본문 전체(마크다운). 검색 조각만으로 맥락이 부족할 때 쓴다."""
        note: dict[str, Any] = await _get(http, "GET", f"{INTERNAL}/notes/{note_id}")
        return note

    @server.tool(annotations=READ_ONLY)
    async def list_due_cards(notebook_id: str = "NB-1", base_date: str | None = None) -> dict[str, Any]:
        """기준일(기본: 오늘)까지 복습해야 할 카드. 다음 복습일은 BE가 계산한 값이다."""
        day = base_date or date.today().isoformat()
        cards = await _get(http, "GET", f"{INTERNAL}/notebooks/{notebook_id}/due", params={"base_date": day})
        return {
            "base_date": day,
            "cards": [{k2: c[k2] for k2 in ("id", "note_title", "question", "due_date")} for c in cards],
        }

    return server
