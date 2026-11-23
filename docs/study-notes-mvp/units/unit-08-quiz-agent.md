# Unit 08: quiz Agent(Structured Output·few-shot·제안)

## Goal (목표)

"이 노트로 퀴즈 3개 내줘"에 `quiz` Agent가 노트 근거가 확인된 문답 카드 초안을 만들고, 답에 제안 초안(`quiz.cards_add`)과 [카드 N장 저장] 버튼(`save_proposal`)을 담아 돌려주는 상태가 된다. 모델이 있으면 Structured Output(few-shot 프롬프트)으로, 없으면 노트의 `- 용어: 설명` 줄로 만든다. 같은 요청을 두 번 해도 `dedupe_key`가 같다.

## 배경 / 컨텍스트

- 과제: 멀티 에이전트(두 번째 하위 Agent), Structured Output, few-shot 프롬프트.
- 절대 규칙: Agent는 BE에 쓰지 않는다. 카드 저장은 사용자가 버튼을 누르면 BE(`POST /proposals/accept`)가 한다. 제안 초안은 `BaseAgent.proposal(kind, title, payload, reasons)`로 만들면 `dedupe_key`(thread·Agent·내용 해시)가 붙는다.
- 버튼: `UiAction(kind="save_proposal", label=..., params={"index": 0})`.
- 하위 Agent끼리 부르지 않는다. 노트 고르기는 quiz 자기 도구로 한다.
- `AgentRequest`에 `text, intent, history, focus_note_ids, screen`이 있다(Unit 07). 답 `data.focus_note_ids`로 다룬 노트를 알린다.

## 선행 조건 (Dependencies)

- Unit 07(notes Agent, 대화 메모리, `rules.resolve_note_id` 본보기)
- BeClient: `list_notes`, `get_note`, `list_cards`, `get_learner_profile`
- 참고: `src/study_notes/agents/notes/`, `src/study_notes/core/proposal.py`, `AGENTS.md` §4.4, §7 "바꾸는 기능 추가"

## 작업 범위 (Scope)

### 한다

- `agents/quiz/`: `__init__.py`, `agent.py`, `tools.py`, `rules.py`, `prompts/quiz.make.v1.md`
- 의도 `quiz_make` "노트로 퀴즈 카드 만들기" — `(퀴즈|문제).*(내|만들|줘|출제)`, `카드.*만들`
- 도구: `quiz_list_notes`, `quiz_get_note`, `quiz_list_cards`, `quiz_get_profile` (조회)
- 장 수: 질문의 숫자(`(\d+)\s*(개|장|문제)`) 기본 3, 1~5로 자름
- 모델 경로: `ask_llm_json(QuizOut, "worker", prompt("make"), text, note=..., count=..., difficulty=..., existing=...)`
  - `QuizOut(reasoning: str, cards: list[QuizCard])`, `QuizCard(question: str, answer: str, evidence: str)`
  - 검증(규칙 함수): evidence를 공백 제거해 노트 본문(공백 제거)에 들어 있는 카드만, 기존 카드와 같은 질문 제외, 개수 자름. 남은 카드가 0이면 규칙 경로
- 규칙 경로: `rules.cards_from_note(body, count, existing)` — `^\s*[-*]\s*(.+?)\s*[:：]\s*(.+)$` 줄 → 질문 `"{용어}란 무엇인가?"`, 답 `설명`
- 답: 질문 목록 텍스트, `proposals=[quiz.cards_add {note_id, cards:[{question,answer}]}]`, 버튼 [카드 N장 저장], `ask` 버튼 "다른 노트로 퀴즈", `data.cards`, `data.focus_note_ids`. 만들 카드가 없으면 제안 없이 이유 설명
- 프롬프트: 역할(학습 코치), 근거 제한, 난이도별 질문 방식, 단계적 사고는 `reasoning`에, few-shot 2개, JSON 스키마
- 등록 `AGENTS = [NotesAgent, QuizAgent]` (notes 먼저)
- 오케스트레이터 v2 프롬프트 few-shot에 quiz 예시 추가는 Unit 07에서 이미 포함했으면 생략
- 시험: `tests/unit/test_quiz_rules.py`, `tests/graph/test_quiz_graph.py`, 평가 `eval/cases/quiz.yaml`(3건 이상)

### 하지 않는다

- 카드 저장(BE), 퀴즈 풀이·채점(UI 복습 화면, Unit 11)

## 상세 작업 단계

1. 규칙 함수와 단위 시험(줄 파싱, 개수, 기존 카드 제외, evidence 검증)
2. Agent·도구·프롬프트
3. 그래프 시험
   - 규칙 답: 제안 1건, kind `quiz.cards_add`, 버튼 `save_proposal` index 0, payload.cards 길이 = 요청 장 수
   - 같은 thread에서 같은 질문 두 번 → dedupe_key 같음, 다른 thread → 다름
   - 모델 답: QuizOut 등록, 근거 없는 카드 1장 섞음 → 걸러짐, source ai
   - "노트 요약하고 퀴즈도 내줘" → 의도 두 개, 답 두 개(notes 먼저)
   - "그 노트로 퀴즈" → focus 노트
4. 평가 통과

## 사용할 수 있는 SKILL / 참고 자료

- `AGENTS.md` §7 "바꾸는 기능 추가" 체크리스트

## 완료 조건 (Definition of Done)

- [ ] `.\.venv\Scripts\python.exe -m pytest -q` 전체 통과
- [ ] `.\.venv\Scripts\python.exe -m study_notes.eval` 통과
- [ ] `ruff check`·`ruff format --check`·`mypy` 통과

## 산출물 (Output)

- `src/study_notes/agents/quiz/**`, `src/study_notes/agents/registry.py`
- `tests/unit/test_quiz_rules.py`, `tests/graph/test_quiz_graph.py`, `src/study_notes/eval/cases/quiz.yaml`
