# Unit 04: FastAPI BE(공개 API·내부 조회 API)

## Goal (목표)

`uvicorn notes_api.main:app`으로 뜨는 FastAPI BE가 있고, (1) UI용 공개 API로 노트북·노트(저장 시 RAG 적재)·카드·복습·통계·프로필·제안 수락을 처리하며, (2) Agent용 내부 조회 API(`/internal/agent/*`, 조회만)로 노트·청크 검색·카드·통계·프로필을 내주는 상태가 된다. `TestClient` 시험이 통과한다.

## 배경 / 컨텍스트

- 구조: Streamlit(FE) → **FastAPI(BE)** → Agent. Agent는 템플릿의 `HttpBeClient`로 `base_url + "/internal/agent"` 아래를 GET(검색만 POST 조회)으로 부른다.
- 오류 본문은 RFC 9457 형식 `{"type","title","status","detail"}` — 템플릿 `HttpBeClient._raise_for`가 `detail`을 읽는다. 404/400 → Agent 쪽 `ToolInputError`, 5xx → 재시도.
- Agent 호출 중계(`/chat/*`, `/jobs/*`)는 Unit 10에서 붙인다.

## 선행 조건 (Dependencies)

- Unit 02: `notes_api.store` (`Store`, 모델, `seed_demo`)
- Unit 03: `notes_api.rag` (`NoteIndex`, `make_client`, `build_embedder`, `ChunkHit`)
- 참고: `src/study_notes/tools/be_client/http.py`(호출 쪽 기대 형식)

## 작업 범위 (Scope)

### 한다

- `src/notes_api/config.py`: `ApiSettings`(pydantic-settings, 접두어 `NOTES_API_`, `.env` 읽음)
  - `db_path="data/notes.db"`, `chroma_dir="data/chroma"`, `embedding_mode: Literal["hash","litellm"]="hash"`, `embedding_model: str | None=None`, `seed_demo: bool=True`, `agent_mode: Literal["inprocess","aegra"]="inprocess"`, `aegra_url="http://127.0.0.1:2026"`, `user_id="local-user"`
- `src/notes_api/deps.py`: `AppState(store, index, settings)` 만들기·가져오기(`request.app.state`)
- `src/notes_api/main.py`: `create_app(settings: ApiSettings | None = None, *, store: Store | None = None, index: NoteIndex | None = None) -> FastAPI`, 모듈 변수 `app = create_app()`는 **지연 생성**하지 말고 lifespan에서 데이터 폴더를 만든다. seed가 켜져 있으면 비어 있을 때 `seed_demo` 후 전체 재색인
- `src/notes_api/errors.py`: `ProblemError(status, title, detail)` + 예외 처리기
- `src/notes_api/routes/public.py`, `routes/internal.py`
- `tests/api/test_api.py`

### 하지 않는다

- `/chat/*`, `/jobs/*`(Unit 10), 인증(로컬 전용)

## 상세 작업 단계

1. 공개 API (응답 모델은 `notes_api.store.models` 그대로)

| 메서드 | 경로 | 본문/인자 | 응답 |
|---|---|---|---|
| GET | `/health` | | `{"status":"ok","notes":n,"chunks":m}` |
| GET | `/notebooks` | | `list[Notebook]` |
| POST | `/notebooks` | `{"name"}` | `Notebook` |
| GET | `/notebooks/{nb}/notes` | `query?`, `limit=50` | `list[NoteSummary]` |
| POST | `/notebooks/{nb}/notes` | `{"title","body","tags":[],"source":""}` | `Note` (저장 후 `index.upsert_note`) |
| GET | `/notes/{id}` | | `Note` |
| PUT | `/notes/{id}` | 위와 같음 | `Note` (재적재) |
| DELETE | `/notes/{id}` | | 204 (청크 삭제) |
| GET | `/notebooks/{nb}/cards` | `note_id?` | `list[Card]` |
| GET | `/notebooks/{nb}/due` | `base_date`, `limit=20` | `list[Card]` |
| POST | `/cards/{id}/review` | `{"grade","reviewed_on"}` | `Card` |
| GET | `/notebooks/{nb}/stats` | `base_date` | `ReviewStats` |
| GET | `/profile` | `base_date?` | `LearnerProfile` |
| PUT | `/profile` | `{"summary_length"?,"quiz_difficulty"?}` | `LearnerProfile` |
| POST | `/proposals/accept` | `{"proposal": ProposalDraft dict, "accepted_on"}` | `ProposalRecord` |
| GET | `/proposals` | `subject_id?`, `kind?` | `list[ProposalRecord]` |
| GET | `/notebooks/{nb}/daily-plan` | `base_date` | `{"plan": ProposalRecord | null, "cards": list[Card]}` |
| POST | `/admin/reindex` | | `{"chunks": n}` |

2. 내부 조회 API — 접두어 `/internal/agent`, **조회만**(검색은 본문이 있어 POST지만 상태를 바꾸지 않는다)

| 메서드 | 경로 | 응답 |
|---|---|---|
| GET | `/notebooks` | `list[str]` (노트북 ID) |
| GET | `/notebooks/{nb}/notes?query=&limit=10` | `list[NoteSummary]` |
| GET | `/notes/{id}` | `Note` |
| POST | `/notebooks/{nb}/search` `{"query","k":5}` | `list[ChunkHit]` |
| GET | `/notebooks/{nb}/cards?note_id=` | `list[Card]` |
| GET | `/notebooks/{nb}/due?base_date=&limit=20` | `list[Card]` |
| GET | `/notebooks/{nb}/stats?base_date=` | `ReviewStats` |
| GET | `/profile?base_date=` | `LearnerProfile` |

   - 없는 노트북·노트 → 404 Problem(`detail`에 "노트 N-9를 찾을 수 없습니다. 노트 목록에서 ID를 확인하세요" 같은 고칠 방법)
   - 날짜 형식 오류 → 400 Problem
3. `create_app`이 테스트에서 메모리 `Store(":memory:")`·`make_client(None)`·`HashEmbedder`를 받을 수 있게 한다.
4. 시험(`tests/api/test_api.py`, `fastapi.testclient.TestClient`)
   - 노트 생성 → 검색(`/internal/agent/notebooks/NB-1/search`)에 나옴 → 수정·삭제 반영
   - 내부 API에 쓰기 메서드(POST 검색 제외 PUT/PATCH/DELETE/POST)가 없는지 라우트 목록으로 확인
   - 제안 수락 두 번 → 카드 한 번
   - 404 본문에 `detail`
   - 복습 → stats 변화

## 사용할 수 있는 SKILL / 참고 자료

- FastAPI `APIRouter`, `lifespan`, `TestClient`
- `src/study_notes/tools/be_client/http.py` `_raise_for`

## 완료 조건 (Definition of Done)

- [ ] `.\.venv\Scripts\python.exe -m pytest -q tests/api` 통과
- [ ] `ruff check`·`ruff format --check`·`mypy` 통과
- [ ] `.\.venv\Scripts\python.exe -m uvicorn notes_api.main:app --port 8000` 실행 후 `GET /health`가 seed 기준 notes 5 이상, chunks 1 이상(수동 확인, 확인 후 종료)

## 산출물 (Output)

- `src/notes_api/{config,deps,errors,main}.py`, `src/notes_api/routes/{__init__,public,internal}.py`
- `tests/api/test_api.py`
