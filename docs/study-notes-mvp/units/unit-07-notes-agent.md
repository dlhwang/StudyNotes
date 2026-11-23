# Unit 07: notes Agent(찾기·요약·RAG 질의) + 대화 메모리 + 예시 제거

## Goal (목표)

chat 그래프에 `notes` 하위 Agent가 등록돼 "노트 찾아줘"(찾기), "이 노트 요약해줘"(요약, Structured Output), "체크포인터가 뭐야?"(노트 기반 질의, ReAct + RAG)에 근거(citation)와 함께 답하고, 모델이 없으면 규칙 답으로 돌며, 최근 다룬 노트를 대화 메모리(`focus_note_ids`)로 기억해 "그 노트"를 이어 받는 상태가 된다. 예시 `tasks` Agent·`daily_check` 그래프는 지워져 있다.

## 배경 / 컨텍스트

- 과제: 멀티 에이전트, Tool Calling·ReAct, Memory, RAG, 프롬프트 엔지니어링(역할·CoT·few-shot·구조화).
- 하위 Agent 약속: `src/study_notes/agents/base.py`의 `BaseAgent`(`name`, `title`, `intents`, `run(req) -> AgentResult`), 도구는 `self.tool(name, args)`, 모델은 `ask_llm`/`ask_llm_json`/`react`(Unit 06). 모델 실패 시 `LlmUnavailableError` → 규칙 답.
- 의도 판정: 각 Agent의 `IntentSpec(name, help, patterns)` 규칙(공백 제거·소문자 질문에 정규식)을 등록 순서대로 걸고, 없으면 모델(router)이 고른다(`orchestrator/classify.py`, 프롬프트 `orchestrator/prompts/orchestrator.classify.v1.md`).
- `context.subject_id` = 노트북 ID(`NB-1`), `context.screen.note_id` = 보고 있는 노트, `screen.base_date` = 기준일.
- BeClient 조회 메서드(Unit 05): `list_notes`, `get_note`, `search_chunks`, `get_learner_profile` 등. FakeBeClient의 합성 데이터로 시험한다.

## 선행 조건 (Dependencies)

- Unit 05(BeClient·FakeBeClient), Unit 06(`react`, FakeLlm `script`)
- 참고: `src/study_notes/agents/tasks/`(본보기, 이 Unit에서 지움), `src/study_notes/graphs/chat.py`, `AGENTS.md` §7 체크리스트, `docs/02-개발-가이드.md` §4

## 작업 범위 (Scope)

### 한다

- `agents/notes/`: `__init__.py`, `agent.py`, `tools.py`, `rules.py`, `prompts/notes.summary.v1.md`, `prompts/notes.qa.v1.md`
- 의도
  - `note_summary` "노트 요약하기" — `(요약|정리해|핵심만)`
  - `note_search` "노트 찾기·목록 보기" — `(노트|메모).*(찾아|검색|목록|뭐있|보여)`, `(찾아줘|검색해)`
  - `note_qa` "노트 내용으로 질문에 답하기" — `^(?!.*(퀴즈|문제|복습|요약|정리)).*(뭐야|뭐지|뭔데|무엇|차이|어떻게|왜|설명해|알려줘)`
- 도구(모두 조회, 이름 `notes_<동사>_<대상>`): `notes_list_items`(노트 목록·키워드), `notes_get_item`(노트 본문, llm_selectable), `notes_search_chunks`(RAG 검색, llm_selectable), `notes_get_profile`(학습자 프로필)
- 대상 노트 고르기 `rules.resolve_note_id(text, notes, screen_note_id, focus_ids)`: ① 질문에 노트 제목(공백 제거)이 들어 있음 ② "이 노트"·"지금 노트" + screen.note_id ③ "그 노트"·"그거"·"방금" 또는 아무것도 없으면 focus의 첫 번째 ④ 그래도 없으면 None → 검색 상위 청크의 노트
- 요약: `ask_llm_json(SummaryOut, "worker", ...)` — `SummaryOut(reasoning: str, key_points: list[str] (3~5), one_line: str)`. `reasoning`은 화면에 내지 않는다. 프로필 `summary_length`를 프롬프트에 넣는다. 규칙 답: 본문의 `- 용어: 설명` 줄과 각 소제목 첫 문장으로 핵심 3개(short)/4개(normal)/5개(long)
- 질의: `react("worker", prompt("qa"), text, tools=["notes_search_chunks","notes_get_item"])`. 최종 답 + 관찰된 청크로 citation(노트 제목, `"N-1 · 체크포인터 > 소제목"`) 최대 3개, `data.trace`에 단계(도구명·인자). 규칙 답: `search_chunks` 상위 3개 중 score ≥ 0.15인 것을 발췌해 "노트에서 찾은 내용입니다: …", 없으면 "노트에 관련 내용이 없습니다" + `ask` 버튼 "노트 목록 보기"
- 찾기: `list_notes(query)`와 `search_chunks` 결과를 노트 단위로 합쳐 최대 5개, 모델 없이 규칙 답. `data.notes`
- 모든 답: `data.focus_note_ids` = 다룬 노트 ID들. 요약·질의 답에는 `ask` 버튼 "이 노트로 퀴즈"(`"{제목} 퀴즈 내줘"`)
- 프롬프트(역할·근거 제한·단계적 사고·few-shot 1~2개·JSON 형식). 파일 이름 `notes.<용도>.v1.md`
- 오케스트레이터 프롬프트 `orchestrator.classify.v2.md`: 역할, 의도 목록, few-shot 예시 5개 이상(다중 의도 포함), JSON 출력
- **대화 메모리**: `graphs/chat.py`
  - `ChatState`에 `focus_note_ids: list[str]` 추가
  - `AgentRequest`(`agents/base.py`)에 `focus_note_ids: list[str] = []`, `screen: dict = {}` 추가해 넘김
  - 답들의 `data.focus_note_ids`를 모아(최신 먼저, 중복 제거, 최대 3개) State에 저장
- 예시 제거: `agents/tasks/`, `graphs/daily_check.py`, `aegra.json`의 `daily_check`, `TaskItem`·`list_tasks`(protocol·http·fake), tasks를 쓰는 시험·평가(`eval/cases/examples.yaml`). `tools/smoke_aegra.py`의 질문을 "노트 찾아줘"로
- `agents/registry.py`: `AGENTS = [NotesAgent]`
- 시험: `tests/unit/test_notes_rules.py`, `tests/graph/test_notes_graph.py`, 평가 `eval/cases/notes.yaml`(5건 이상). 기존 `tests/unit/test_platform.py`·`test_rules_and_intents.py`·`tests/graph/test_graphs.py`는 notes 기준으로 고친다(쓰기 금지 시험·중복 방지 키 시험은 유지)

### 하지 않는다

- quiz·review Agent(Unit 08·09), 예약 그래프(Unit 09)
- BE 수정

## 상세 작업 단계

1. 도구 → 규칙 → Agent → 프롬프트 → 등록 순서로 작성
2. chat 그래프 메모리 필드 추가
3. 예시 제거와 시험·평가 교체
4. 그래프 시험(가짜 모델 기본 = 규칙 답, `env.llm`에 응답 등록 = 모델 답)
   - 요약 규칙 답: 핵심 줄 + citation, source rule
   - 요약 모델 답: `SummaryOut` JSON을 등록 → source ai, `prompt_version == "notes.summary.v1"`, 답에 reasoning이 안 나옴
   - 질의 ReAct: `script("worker", [도구 호출 결과, 최종 답])` → `data.trace` 1단계, citation 있음
   - 질의 규칙 답: 관련 노트 발췌
   - 메모리: 같은 thread에서 "StateGraph 기초 요약해줘" → "그 노트 핵심만 다시" → 같은 노트
   - 모르는 질문 → 안내 답
5. 평가 `python -m study_notes.eval` 통과

## 사용할 수 있는 SKILL / 참고 자료

- `AGENTS.md` §7 "새 하위 Agent 추가" 체크리스트
- `docs/02-개발-가이드.md` §4

## 완료 조건 (Definition of Done)

- [ ] `.\.venv\Scripts\python.exe -m pytest -q` 전체 통과
- [ ] `.\.venv\Scripts\python.exe -m study_notes.eval` 통과(notes 5건 이상)
- [ ] `ruff check`·`ruff format --check`·`mypy` 통과
- [ ] `grep -ri "tasks\|TaskItem\|daily_check" src tests aegra.json`에 예시 잔재 없음(문서 제외)

## 산출물 (Output)

- `src/study_notes/agents/notes/**`, `src/study_notes/agents/{base,registry}.py`, `src/study_notes/graphs/chat.py`
- `src/study_notes/orchestrator/prompts/orchestrator.classify.v2.md`
- `src/study_notes/tools/be_client/*`, `src/study_notes/tools/fakes/be.py`, `aegra.json`, `tools/smoke_aegra.py`
- 시험·평가 파일
