# Unit 11: Streamlit UI

## Goal (목표)

`streamlit run app/streamlit_app.py`로 뜨는 화면에서 (1) 노트를 보고·쓰고·고치고, (2) 채팅으로 질문해 Agent 답(담당 Agent, 근거, ReAct 실행 흔적, 표 데이터, 버튼)을 보고 버튼(ask·save_proposal·navigate)을 누를 수 있고, (3) 복습 화면에서 오늘 계획을 만들고 카드를 넘기며 등급을 매기고, (4) 설정 화면에서 학습자 프로필을 바꿀 수 있는 상태가 된다. UI는 BE 공개 API만 부른다.

## 배경 / 컨텍스트

- 구조: Streamlit(FE) → FastAPI BE(`http://127.0.0.1:8000`, 설정 `NOTES_UI_API_URL`) → Agent.
- BE 공개 API(Unit 04·10): `/notebooks`, `/notebooks/{nb}/notes`, `/notes/{id}`(GET·PUT·DELETE), `/notebooks/{nb}/cards`, `/notebooks/{nb}/due`, `/cards/{id}/review`, `/notebooks/{nb}/stats`, `/profile`(GET·PUT), `/proposals/accept`, `/notebooks/{nb}/daily-plan`, `/chat/threads`, `/chat/stream`(SSE, `data: {json}` 줄, 끝 `{"type":"done"}`), `/jobs/daily-review`, `/admin/reindex`, `/health`
- 이벤트: `orchestrator`(agents, text), `agent_reply`(reply: agent, text, source, actions, citations, proposals, data{trace?, notes?, cards?, stats?}), `error`
- 버튼 `UiAction(kind, label, target?, text?, params)`: `ask` → text를 다음 질문으로, `save_proposal` → 그 답의 `proposals[params.index]`를 `/proposals/accept`, `navigate` → target(`review`, `notes`) 화면으로

## 선행 조건 (Dependencies)

- Unit 10(BE 채팅·예약 실행)
- `streamlit` 설치(Unit 01)
- 참고: `src/notes_api/routes/*.py`, `src/study_notes/core/reply.py`

## 작업 범위 (Scope)

### 한다

- `src/notes_ui/`
  - `config.py`: `UiSettings`(접두어 `NOTES_UI_`, `api_url="http://127.0.0.1:8000"`, `timeout_seconds=60`)
  - `api.py`: `BeApi`(httpx 동기) — 위 공개 API 메서드, `stream_chat(...) -> Iterator[dict]`(SSE 줄 파싱)
  - `sse.py`: `parse_sse_lines(lines: Iterable[str]) -> Iterator[dict]`
  - `actions.py`: `ActionOutcome(kind, ask_text?, page?, message?)`, `handle_action(api, reply: dict, action: dict, today: str) -> ActionOutcome`
  - `view.py`: 이벤트 → 화면 요소 데이터로 바꾸는 순수 함수(`summarize_reply(reply) -> ReplyView` 등)
- `app/streamlit_app.py`(진입, `st.navigation`), `app/pages/notes.py`, `app/pages/chat.py`, `app/pages/review.py`, `app/pages/settings.py`, `app/common.py`(사이드바: 노트북 선택, 기준일, BE 상태)
  - 채팅: `st.chat_message`, 담당 Agent 캡션, 답 본문, 근거 접기, "Agent 실행 흔적"(data.trace) 접기, 카드·노트 표, 버튼. thread_id는 노트북별 `st.session_state`. 보고 있는 노트(노트 화면에서 고른 것)를 `screen.note_id`로 넘김
  - 복습: [오늘 계획 만들기] → `/jobs/daily-review`, 계획 카드 하나씩 질문 → [답 보기] → again/hard/good/easy
  - 노트: 목록(검색), 선택 시 본문, 새 노트·수정·삭제, 저장 후 "적재됨(청크 n개)" 안내
  - 설정: 프로필 요약 길이·난이도, 약한 노트, [다시 적재]
- 시험 `tests/ui/test_ui_logic.py`: SSE 파싱, handle_action(가짜 BeApi), view 변환. Streamlit을 import하지 않는다
- 화면 확인: BE와 UI를 띄우고 내장 브라우저로 네 화면을 열어 본다(스크린샷)

### 하지 않는다

- Aegra 모드 확인(Unit 12), 디자인 다듬기, 다중 사용자

## 상세 작업 단계

1. `notes_ui` 로직과 시험
2. 페이지 작성
3. 실행: 터미널 1 `uvicorn notes_api.main:app --port 8000`, 터미널 2 `streamlit run app/streamlit_app.py --server.port 8501 --server.headless true`
4. 내장 브라우저로 `http://localhost:8501` 확인: 노트 목록, 채팅 "체크포인터가 뭐야?" → 근거, "그 노트로 퀴즈 내줘" → [카드 저장] → 성공 메시지, 복습 화면 계획 만들기 → 카드 넘기기

## 사용할 수 있는 SKILL / 참고 자료

- Streamlit `st.navigation`/`st.Page`, `st.chat_input`, `st.session_state`, `st.rerun`
- `.claude/launch.json`로 미리보기 서버 등록 가능

## 완료 조건 (Definition of Done)

- [ ] `.\.venv\Scripts\python.exe -m pytest -q` 전체 통과
- [ ] `ruff check`·`ruff format --check`(app 포함)·`mypy` 통과
- [ ] 위 4번 흐름을 브라우저에서 확인(스크린샷 또는 페이지 텍스트로 기록)

## 산출물 (Output)

- `src/notes_ui/{config,api,sse,actions,view}.py`
- `app/streamlit_app.py`, `app/common.py`, `app/pages/{notes,chat,review,settings}.py`
- `tests/ui/{__init__,test_ui_logic}.py`
