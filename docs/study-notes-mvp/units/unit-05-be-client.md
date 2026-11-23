# Unit 05: Agent의 BeClient를 학습 노트 업무로

## Goal (목표)

Agent 패키지의 BE 약속(`BeClient`)이 학습 노트 조회 메서드(노트북 목록·노트 목록·노트·청크 검색·카드·복습 대상·통계·학습자 프로필)를 갖고, `HttpBeClient`가 FastAPI BE 내부 API를 그대로 부르며, `FakeBeClient`가 합성 데이터로 같은 약속을 지키는 상태가 된다. 계약 시험(HttpBeClient ↔ 실제 BE 앱, ASGI 전송)이 통과한다.

## 배경 / 컨텍스트

- 템플릿 규칙: Agent는 BE를 조회만 한다. `BeClient`와 구현에 쓰기로 보이는 이름(save, submit, create, update, delete, approve, confirm, apply, write, post)이 있으면 `tests/unit/test_platform.py`가 실패한다.
- Agent 패키지(`src/study_notes`)는 BE 패키지(`notes_api`)를 import하지 않는다. 그래서 응답 모델을 Agent 쪽에 따로 둔다(같은 JSON 모양).
- 이 Unit에서는 예시 할 일 업무(`TaskItem`, `list_tasks`)를 **남겨 둔다**. 예시 Agent는 Unit 07에서 지우면서 함께 지운다.

## 선행 조건 (Dependencies)

- Unit 04: BE 내부 API (`/internal/agent/*`, 형식은 아래 표)
- 참고: `src/study_notes/tools/be_client/{protocol,http}.py`, `src/study_notes/tools/fakes/be.py`, `src/study_notes/config.py`(`BeSettings`)

| BeClient 메서드 | HTTP |
|---|---|
| `list_subjects(*, token)` → `list[str]` | GET `/notebooks` |
| `list_notes(notebook_id, *, query=None, limit=10, token)` → `list[NoteSummary]` | GET `/notebooks/{nb}/notes` |
| `get_note(note_id, *, token)` → `Note` | GET `/notes/{id}` |
| `search_chunks(notebook_id, query, *, k=5, token)` → `list[ChunkHit]` | POST `/notebooks/{nb}/search` `{"query","k"}` |
| `list_cards(notebook_id, *, note_id=None, token)` → `list[Card]` | GET `/notebooks/{nb}/cards` |
| `list_due_cards(notebook_id, base_date, *, limit=20, token)` → `list[Card]` | GET `/notebooks/{nb}/due` |
| `get_review_stats(notebook_id, base_date, *, token)` → `ReviewStats` | GET `/notebooks/{nb}/stats` |
| `get_learner_profile(*, token, base_date=None)` → `LearnerProfile` | GET `/profile` |

모델 필드(BE와 같음)

- `NoteSummary(id, notebook_id, title, tags: list[str], updated_at, snippet)`
- `Note(id, notebook_id, title, body, tags, source, created_at, updated_at)`
- `ChunkHit(note_id, chunk_id, notebook_id, title, heading, text, position: int, score: float)`
- `Card(id, note_id, note_title, question, answer, ease, interval_days, repetitions, due_date, lapses)`
- `ReviewStats(notebook_id, base_date, total_cards, due_today, overdue, new_cards, reviewed_7d, correct_rate_7d_pct: int | None, streak_days)`
- `LearnerProfile(summary_length: "short"|"normal"|"long", quiz_difficulty: "easy"|"normal"|"hard", weak_notes: list[WeakNote(note_id, title, again_count_14d)])`

## 작업 범위 (Scope)

### 한다

- `tools/be_client/protocol.py`: 위 모델·메서드 추가
- `tools/be_client/http.py`: 위 메서드 구현(`_get`, `_post_query`)
- `tools/fakes/be.py`: 합성 데이터(노트북 2개 `NB-1` "LangGraph 공부", `NB-2` "파이썬 비동기", 노트 4~5개, 카드 몇 장, 통계·프로필 고정값)와 단순 검색(질의 단어와 청크 text 문자 2-gram 겹침 비율을 score로). 청크는 노트 본문을 빈 줄로 나눈 것. 시험에서 바꿔 끼울 수 있게 속성(`notes`, `cards`, `stats`, `profile`)을 연다. `DEMO_SUBJECT = "NB-1"`로 바꾸되 예시 할 일 데이터는 `DEMO_SUBJECT` 아래 그대로 둔다
- `tests/unit/test_be_client.py`: FakeBeClient 동작
- `tests/contract/test_http_vs_api.py`: `HttpBeClient(settings, client=httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://be/internal/agent"))`로 실제 BE 앱(메모리 Store·메모리 Chroma·seed) 상대 모든 메서드 호출, 404 → `ToolInputError`

### 하지 않는다

- 업무 도구(`agents/*/tools.py`) — Unit 07~09
- BE 코드 수정(필요하면 이 Unit에서 최소로 고치고 사유를 적는다)

## 상세 작업 단계

1. 모델·Protocol 추가
2. `HttpBeClient` 구현. `ToolInputError`의 hint에 BE의 `detail`이 들어가는지 확인
3. `FakeBeClient` 확장. 기존 tasks 시험이 깨지지 않게 `tasks` 속성과 `list_tasks`는 유지
4. 시험 작성, `tests/contract/__init__.py`
5. `pytest -q` 전체 통과 확인(기존 tasks 시험 포함)

## 사용할 수 있는 SKILL / 참고 자료

- `httpx.ASGITransport`
- `tests/unit/test_platform.py`의 `_WRITE_WORDS`

## 완료 조건 (Definition of Done)

- [ ] `.\.venv\Scripts\python.exe -m pytest -q` 전체 통과(쓰기 금지 시험 포함)
- [ ] 계약 시험이 BeClient의 모든 조회 메서드를 실제 BE 앱으로 부른다
- [ ] `ruff check`·`ruff format --check`·`mypy` 통과

## 산출물 (Output)

- `src/study_notes/tools/be_client/{protocol,http}.py`, `src/study_notes/tools/fakes/{__init__,be}.py`
- `tests/unit/test_be_client.py`, `tests/contract/{__init__,test_http_vs_api}.py`
