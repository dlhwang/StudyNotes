# Unit 13: MCP 서버(선택 B)

## Goal (목표)

`python -m notes_mcp`로 뜨는 MCP 서버(stdio)가 학습 노트 조회 도구(`search_notes`, `get_note`, `list_due_cards`, `list_notebooks`)를 내놓고, 도구들이 BE 내부 조회 API를 불러 결과(출처 포함)를 돌려주는 상태가 된다. MCP 클라이언트 세션 시험이 통과한다.

## 배경 / 컨텍스트

- 과제 선택 B: MCP 기반 도구 연결로 확장성 강화. 이 서비스의 노트 지식을 다른 에이전트(Claude Desktop, Claude Code 등)가 MCP로 쓰게 한다.
- 조회만 노출한다(쓰기 없음 — Agent와 같은 원칙).
- BE 내부 조회 API(Unit 04): `GET /internal/agent/notebooks`, `POST /internal/agent/notebooks/{nb}/search {"query","k"}`, `GET /internal/agent/notes/{id}`, `GET /internal/agent/notebooks/{nb}/due?base_date=&limit=`
- 공식 Python SDK `mcp`의 `FastMCP`. 시험은 `mcp.shared.memory.create_connected_server_and_client_session`(SDK 버전에 맞는 메모리 연결 도우미)로 한다.

## 선행 조건 (Dependencies)

- Unit 04(BE 내부 API), `mcp` 설치(Unit 01)
- 참고: `src/notes_api/routes/internal.py`

## 작업 범위 (Scope)

### 한다

- `src/notes_mcp/config.py`: `McpSettings`(접두어 `NOTES_MCP_`, `be_url="http://127.0.0.1:8000"`)
- `src/notes_mcp/server.py`: `build_server(http: httpx.AsyncClient) -> FastMCP`, 도구 4개(독스트링에 언제 쓰는지), 결과는 사람이 읽을 문자열 + 구조화(dict) 반환
- `src/notes_mcp/__main__.py`: stdio 실행
- `tests/mcp/test_mcp_server.py`: BE 앱(메모리)을 ASGI 전송 httpx로 붙인 서버에 메모리 MCP 클라이언트로 `list_tools`·`call_tool("search_notes")`
- `docs/03-mcp.md`: Claude Desktop/Claude Code 등록 예(`command`: `.venv\Scripts\python.exe`, `args`: `["-m","notes_mcp"]`, env `NOTES_MCP_BE_URL`)

### 하지 않는다

- 쓰기 도구, 인증, SSE/HTTP 전송(stdio만)

## 상세 작업 단계

1. 설정·서버·진입점
2. 시험
3. 문서

## 사용할 수 있는 SKILL / 참고 자료

- MCP Python SDK README(FastMCP, `@mcp.tool()`)

## 완료 조건 (Definition of Done)

- [ ] `.\.venv\Scripts\python.exe -m pytest -q tests/mcp` 통과
- [ ] `ruff check`·`ruff format --check`·`mypy` 통과
- [ ] 도구 목록에 쓰기 도구 없음(시험)

## 산출물 (Output)

- `src/notes_mcp/{config,server,__main__}.py`, `tests/mcp/{__init__,test_mcp_server}.py`, `docs/03-mcp.md`
