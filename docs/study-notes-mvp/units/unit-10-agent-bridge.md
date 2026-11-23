# Unit 10: BE ↔ Agent 연결(SSE 중계·예약 실행·제안 수락)

## Goal (목표)

FastAPI BE가 Agent를 부르는 `AgentBridge`(같은 프로세스 `inprocess` / Aegra `aegra`)를 갖고, `POST /chat/threads`·`POST /chat/stream`(SSE로 Agent의 custom 이벤트 중계)·`POST /jobs/daily-review`(예약 그래프 실행 후 제안 저장)가 동작하는 상태가 된다. `inprocess` 모드는 PostgreSQL 없이 돌고, Agent의 BE 조회는 같은 BE 앱으로 간다.

## 배경 / 컨텍스트

- 구조: UI → BE → Agent. UI는 Agent에 직접 붙지 않는다(`docs/01-구조.md` §1).
- Agent custom 이벤트(`src/study_notes/core/reply.py`): `{"type":"orchestrator","schema_version":1,"agents":[...],"text":...}`, `{"type":"agent_reply","schema_version":1,"reply":{agent,text,source,actions,citations,proposals,data,prompt_version}}`
- chat 그래프 입력: `{"messages":[{"role":"user","content":...}]}`, context: `AgentContext(subject_id=노트북, screen={note_id?, base_date?})`, config: `{"configurable":{"thread_id", "user_id"}}`. thread_id 형식 `chat:{user_id}:{uuid}`(`core/ids.new_thread_id`)
- 예약 그래프 `daily_review`: 입력 `{"base_date","subject_ids"?}`, 출력 `{"proposals":[ProposalDraft dict]}` — BE가 `store.accept_proposal`로 저장
- Agent 의존성은 `study_notes.deps.set_deps(Deps(settings, be, llm, recorder))`로 바꿔 끼운다. `HttpBeClient(settings.be, client=httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://be/internal/agent"))`면 네트워크 없이 같은 앱을 부른다.
- Aegra: `langgraph_sdk.get_client(url, headers={"X-User-Id":..., "X-User-Name": URL인코딩, "X-User-Role":"user"})`, `threads.create`, `runs.stream(thread_id, "chat", input=..., context=..., stream_mode=["custom"])`, `runs.wait(thread_id, "daily_review", input=...)`

## 선행 조건 (Dependencies)

- Unit 04(BE 앱·설정 `agent_mode`, `aegra_url`, `user_id`), Unit 09(chat·daily_review 그래프)
- 참고: `src/study_notes/graphs/{chat,daily_review}.py`, `src/study_notes/deps.py`, `tools/smoke_aegra.py`

## 작업 범위 (Scope)

### 한다

- `src/notes_api/bridge.py`
  - `class AgentBridge(Protocol)`: `async def new_thread(user_id) -> str`, `def stream_chat(thread_id, user_id, text, notebook_id, screen) -> AsyncIterator[dict]`, `async def run_daily_review(base_date, notebook_ids: list[str] | None) -> list[dict]`
  - `InProcessBridge(app)`: 그래프를 한 번 만들고 `InMemorySaver` 공유. 처음 쓸 때 Agent deps를 위 ASGI `HttpBeClient`로 설정(LLM은 Agent 설정 그대로 `build_deps`의 llm·recorder 재사용)
  - `AegraBridge(url)`
  - `build_bridge(settings, app) -> AgentBridge`
- `src/notes_api/routes/chat.py`
  - `POST /chat/threads` `{}` → `{"thread_id"}`
  - `POST /chat/stream` `{"thread_id","text","notebook_id","screen":{}}` → `text/event-stream`, 이벤트마다 `data: {json}\n\n`, 끝에 `data: {"type":"done"}\n\n`. Agent 오류는 `{"type":"error","text":...}`
  - `POST /jobs/daily-review` `{"base_date","notebook_ids"?}` → `{"saved": list[ProposalRecord]}`(Agent가 돌려준 제안을 `accept_proposal`로 저장)
- `create_app`에 bridge 주입 인자(`bridge: AgentBridge | None`) 추가
- 시험 `tests/api/test_chat_bridge.py`: InProcessBridge + 메모리 BE, 가짜 모델
  - 스트림이 orchestrator → agent_reply → done 순서
  - "체크포인터가 뭐야?"(NB-1) 답에 citation, 같은 thread 두 번째 질문 "그 노트로 퀴즈 내줘" → quiz 답에 제안
  - 제안을 `/proposals/accept`로 수락 → 카드 증가
  - `/jobs/daily-review` 두 번 → 저장 기록 dedupe(같은 id)

### 하지 않는다

- UI(Unit 11), 실제 Aegra 실행 확인(Unit 12 — 여기서는 AegraBridge 코드와 가짜 클라이언트 시험까지)

## 상세 작업 단계

1. bridge 작성 → 라우트 → create_app 주입
2. 시험. 스트리밍 응답은 `TestClient.stream("POST", ...)`로 줄을 읽는다
3. AegraBridge는 `langgraph_sdk` 클라이언트를 인자로 받을 수 있게 해 가짜 객체로 시험(이벤트 변환만)

## 사용할 수 있는 SKILL / 참고 자료

- FastAPI `StreamingResponse`
- `tools/smoke_aegra.py`(Aegra 호출 본보기)

## 완료 조건 (Definition of Done)

- [ ] `.\.venv\Scripts\python.exe -m pytest -q` 전체 통과
- [ ] `ruff check`·`ruff format --check`·`mypy` 통과
- [ ] BE를 띄우고 `curl -N -X POST /chat/stream`으로 이벤트가 흘러나옴(수동, 확인 후 종료)

## 산출물 (Output)

- `src/notes_api/bridge.py`, `src/notes_api/routes/chat.py`, `src/notes_api/main.py`
- `tests/api/test_chat_bridge.py`
