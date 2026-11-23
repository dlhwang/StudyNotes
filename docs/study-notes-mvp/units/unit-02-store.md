# Unit 02: BE 저장소(SQLite)와 복습 계산

## Goal (목표)

`src/notes_api/store/`에 노트북·노트·카드·복습 기록·제안·학습자 프로필을 다루는 SQLite 저장소(`Store`)가 있고, 복습 간격(SM-2 단순화)과 학습 통계를 BE가 계산하며, 합성 시드 데이터로 채울 수 있는 상태가 된다. 단위 시험이 메모리 SQLite로 통과한다.

## 배경 / 컨텍스트

- 이 서비스의 BE는 FastAPI(`src/notes_api`)다. 이 Unit은 그 아래 데이터 계층이다. API(Unit 04)와 RAG(Unit 03)가 이것을 쓴다.
- AGENTS.md 절대 규칙: Agent는 BE에 쓰지 않고, 숫자 계산은 BE가 한다. 그래서 복습 간격·통계·약한 노트 판정은 여기서 한다.
- Agent는 제안 초안(`ProposalDraft`: `kind, subject_id, title, payload, reasons, source, source_ref, dedupe_key`)을 돌려준다. BE는 사용자가 수락하면 `dedupe_key`로 한 번만 저장하고 종류별로 반영한다.

## 선행 조건 (Dependencies)

- Unit 01 완료: `.venv`, `src/notes_api/__init__.py`
- 참고: `src/study_notes/core/proposal.py`(제안 초안 형식), `AGENTS.md` §1

## 작업 범위 (Scope)

### 한다

- `src/notes_api/store/` : `__init__.py`, `models.py`, `schema.py`, `srs.py`, `store.py`, `seed.py`
- `tests/api/test_store.py`, `tests/api/test_srs.py` (`tests/api/__init__.py` 포함)

### 하지 않는다

- HTTP API(Unit 04), 임베딩·Chroma(Unit 03)
- 다중 사용자·인증

## 상세 작업 단계

1. `models.py` (Pydantic v2, 모두 API 응답에 그대로 쓴다)
   - `Notebook(id: str, name: str)` — id 형식 `NB-<정수>`
   - `Note(id, notebook_id, title, body, tags: list[str], source: str = "", created_at: str, updated_at: str)` — id `N-<정수>`, 날짜는 ISO(`YYYY-MM-DDTHH:MM:SS`)
   - `NoteSummary(id, notebook_id, title, tags, updated_at, snippet: str)` — snippet은 본문 앞 120자
   - `Card(id, note_id, note_title, question, answer, ease: float, interval_days: int, repetitions: int, due_date: str, lapses: int)` — id `C-<정수>`, due_date `YYYY-MM-DD`
   - `Grade = Literal["again", "hard", "good", "easy"]`
   - `ReviewStats(notebook_id, base_date, total_cards, due_today, overdue, new_cards, reviewed_7d, correct_rate_7d_pct: int | None, streak_days)`
     - due_today: `due_date <= base_date`인 카드 수, overdue: `due_date < base_date`, new_cards: `repetitions == 0`
     - reviewed_7d: base_date 포함 최근 7일 복습 횟수, correct_rate_7d_pct: 그중 grade≠again 비율(반올림 정수 %), 없으면 None
     - streak_days: base_date부터 거꾸로 하루도 빠짐없이 복습한 날 수(base_date에 복습이 없으면 0)
   - `LearnerProfile(summary_length: Literal["short","normal","long"]="normal", quiz_difficulty: Literal["easy","normal","hard"]="normal", weak_notes: list[WeakNote])`, `WeakNote(note_id, title, again_count_14d: int)` — 최근 14일(기준: 오늘 또는 인자) again이 2회 이상인 노트, 많은 순 최대 3개
   - `ProposalRecord(id: int, dedupe_key, kind, subject_id, title, payload: dict, reasons: list[str], source, status: Literal["saved","applied"], created_at: str, applied: dict = {})`
2. `schema.py`: `DDL` 문자열(테이블 `notebooks, notes, cards, reviews, proposals, profile`). 카드에는 `dedupe_key TEXT UNIQUE`(`note_id` + 정규화한 질문), 제안에는 `dedupe_key TEXT UNIQUE`. 외래 키 ON.
3. `srs.py`: 순수 함수 `schedule(ease: float, interval_days: int, repetitions: int, grade: Grade) -> tuple[float, int, int]` (새 ease, 새 간격, 새 반복 수)
   - again: 반복 0, 간격 1, ease = max(1.3, ease-0.2)
   - hard: 반복+1, 간격 = max(1, round(max(간격,1)*1.2)), ease = max(1.3, ease-0.15)
   - good: 반복+1, 간격 = 1(반복 0이었으면) / 3(반복 1이었으면) / round(간격*ease)
   - easy: 반복+1, 간격 = max(2, round(good 간격*1.3)), ease+0.15
   - `next_due(reviewed_on: str, interval_days: int) -> str`
4. `store.py`: `class Store`
   - `Store(path: str)` — `":memory:"` 허용. `check_same_thread=False`, 쓰기는 `threading.Lock`으로 묶는다. 생성 시 `DDL` 실행.
   - 노트북: `list_notebooks()`, `create_notebook(name)`, `get_notebook(id)`
   - 노트: `create_note(notebook_id, title, body, tags, source="")`, `update_note(note_id, *, title, body, tags, source)`, `delete_note(note_id)`(카드·복습 함께 삭제), `get_note(note_id) -> Note | None`, `list_notes(notebook_id, query: str | None = None, limit=50) -> list[NoteSummary]`
     - query가 있으면 공백으로 나눈 단어(2자 이상)마다 제목 3점·태그 2점·본문 1점(포함 여부)으로 점수를 매겨 0점은 빼고 점수순. 없으면 수정 최신순.
   - 카드: `add_cards(note_id, cards: list[tuple[str, str]], created_on: str) -> list[Card]`(이미 있는 질문은 건너뜀, 새 카드 due=created_on), `list_cards(notebook_id, note_id=None)`, `list_due_cards(notebook_id, base_date, limit=20)`(due 오래된 순), `get_card(card_id)`
   - 복습: `record_review(card_id, grade, reviewed_on) -> Card` (srs로 갱신, again이면 lapses+1, reviews에 기록)
   - 통계: `review_stats(notebook_id, base_date) -> ReviewStats`
   - 프로필: `get_profile(base_date: str | None = None) -> LearnerProfile`, `set_preferences(summary_length=None, quiz_difficulty=None) -> LearnerProfile`
   - 제안: `accept_proposal(draft: dict, accepted_on: str) -> ProposalRecord`
     - 같은 dedupe_key가 있으면 그 기록을 그대로 돌려준다(두 번 반영 안 함)
     - `quiz.cards_add`: payload `{"note_id", "cards": [{"question","answer"}]}` → `add_cards`, `applied={"card_ids": [...]}`, status applied
     - `review.daily_plan`: payload `{"base_date", "card_ids"}` → 저장만, status applied(계획은 보기용)
     - `profile.update`: payload `{"summary_length"?: ..., "quiz_difficulty"?: ...}` → `set_preferences`, status applied
     - 그 밖: status saved
   - `list_proposals(subject_id=None, kind=None)`, `get_daily_plan(notebook_id, base_date) -> ProposalRecord | None`
5. `seed.py`: `seed_demo(store, today: str) -> None` — 비어 있을 때만 넣는다.
   - NB-1 "LangGraph 공부": 노트 3개 — "StateGraph 기초", "체크포인터와 메모리", "도구 호출과 ReAct". 각 본문에 `## 소제목` 2개 이상, `- 용어: 설명` 줄 3개 이상, 300~700자. 직접 쓴 합성 학습 메모.
   - NB-2 "파이썬 비동기": 노트 2개 — "asyncio 기초", "동시성과 병렬성"
   - 카드: N-1에 4장, N-2에 3장. 복습 기록: 오늘 기준 지난 5일 동안 몇 건(again 포함)으로 통계·약한 노트가 비어 있지 않게.
6. 시험 작성.

## 사용할 수 있는 SKILL / 참고 자료

- 표준 라이브러리 `sqlite3`, `datetime.date.fromisoformat`
- 제안 초안 형식: `src/study_notes/core/proposal.py`

## 완료 조건 (Definition of Done)

- [ ] `.\.venv\Scripts\python.exe -m pytest -q tests/api` 통과. 아래를 확인하는 시험 포함
  - srs 네 등급 결과와 ease 하한 1.3
  - 같은 질문 카드 두 번 추가 → 한 장
  - `accept_proposal` 같은 dedupe_key 두 번 → 카드가 한 번만 생김
  - `review_stats`(due_today·overdue·correct_rate_7d_pct·streak_days) 값
  - 키워드 `list_notes` 점수순
  - `seed_demo` 후 노트북 2개, 노트 5개, 약한 노트 1개 이상
- [ ] `ruff check`·`ruff format --check`·`mypy` 통과
- [ ] Goal 상태 확인

## 산출물 (Output)

- `src/notes_api/store/{__init__,models,schema,srs,store,seed}.py`
- `tests/api/__init__.py`, `tests/api/test_store.py`, `tests/api/test_srs.py`
