# 03. MCP 서버 — 다른 에이전트에서 내 노트 쓰기

학습 노트 비서의 노트 지식을 MCP(Model Context Protocol) 도구로 내놓는다. Claude Desktop, Claude Code 같은 MCP 클라이언트가 "내 노트에서 찾아서 답해 줘"를 할 수 있다.

- 위치: `src/notes_mcp/` (공식 Python SDK `mcp` 2.x의 `MCPServer`)
- 전송: stdio
- **조회만 있다.** 모든 도구에 `readOnlyHint`. 노트·카드를 바꾸는 일은 화면에서 사람이 한다(Agent와 같은 원칙).
- 도구는 BE HTTP API를 부른다. BE(`uvicorn notes_api.main:app --port 8000`)가 떠 있어야 한다.

## 도구

| 도구 | 인자 | 하는 일 | 부르는 BE API |
|---|---|---|---|
| `list_notebooks` | — | 노트북 목록(ID·이름) | `GET /notebooks` |
| `search_notes` | `query`, `notebook_id="NB-1"`, `k=5` | 노트 조각 의미 검색(RAG). 출처(note_id·title·heading)·score | `POST /internal/agent/notebooks/{nb}/search` |
| `get_note` | `note_id` | 노트 본문 전체 | `GET /internal/agent/notes/{id}` |
| `list_due_cards` | `notebook_id="NB-1"`, `base_date=오늘` | 복습할 카드 | `GET /internal/agent/notebooks/{nb}/due` |

## 실행

```powershell
.\.venv\Scripts\python.exe -m notes_mcp
```

설정: `NOTES_MCP_BE_URL`(기본 `http://127.0.0.1:8000`).

## Claude Desktop에 등록

`claude_desktop_config.json`의 `mcpServers`에 넣는다. 경로는 이 저장소 위치로 바꾼다.

```json
{
  "mcpServers": {
    "study-notes": {
      "command": "D:\\workspace\\study-notes\\.venv\\Scripts\\python.exe",
      "args": ["-m", "notes_mcp"],
      "env": { "NOTES_MCP_BE_URL": "http://127.0.0.1:8000" }
    }
  }
}
```

## Claude Code에 등록

```powershell
claude mcp add study-notes --env NOTES_MCP_BE_URL=http://127.0.0.1:8000 -- D:\workspace\study-notes\.venv\Scripts\python.exe -m notes_mcp
```

## 시험

`tests/mcp/test_mcp_server.py` — BE 앱(메모리)을 ASGI로 붙인 서버에 SDK의 메모리 클라이언트(`mcp.client.Client(server)`)로 도구 목록·호출·오류를 확인한다.
