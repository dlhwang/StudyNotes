# Unit 09: review Agent + daily_review 예약 그래프 + 장기 메모리

## Goal (목표)

`review` Agent가 "오늘 뭐 복습해?"(복습 대상), "공부 현황 어때?"(BE가 계산한 통계 + 약한 노트 코칭), "앞으로 요약은 짧게 해줘"(장기 메모리 갱신 제안 `profile.update`)에 답하고, `daily_review` 예약 그래프가 노트북별 오늘 복습 계획 제안(`review.daily_plan`, 같은 날 같은 키)을 돌려주는 상태가 된다.

## 배경 / 컨텍스트

- 과제: 멀티 에이전트(세 번째), Memory(장기 — 학습자 프로필), 프롬프트(코칭, CoT).
- 숫자는 BE가 계산한다(`ReviewStats`: due_today, overdue, new_cards, reviewed_7d, correct_rate_7d_pct, streak_days). Agent는 설명만 한다.
- 장기 메모리 = BE의 `LearnerProfile(summary_length, quiz_difficulty, weak_notes)`. Agent는 읽기만 하고, 바꿀 때는 `profile.update` 제안 + 버튼 → 사용자가 누르면 BE가 반영한다. notes·quiz Agent는 이미 프로필을 읽어 요약 길이·난이도에 쓴다.
- 예약 그래프 규칙: BE가 부르고 결과(`proposals`)를 BE가 저장. 사람 없는 실행이라 `graphs/scheduled.py`의 `service_request`·`service_runner` 사용. 템플릿 본보기는 Unit 07에서 지운 `daily_check`(구조: `evaluate` 노드 하나, 입력 `base_date`·`subject_ids`, 출력 `proposals`).
- 기준일: `screen.base_date`, 없으면 오늘(`date.today().isoformat()`).

## 선행 조건 (Dependencies)

- Unit 08 완료(registry에 notes·quiz)
- BeClient: `list_subjects`, `list_due_cards`, `get_review_stats`, `get_learner_profile`
- 참고: `src/study_notes/graphs/scheduled.py`, `src/study_notes/core/ids.py`(`dedupe_key`), `aegra.json`

## 작업 범위 (Scope)

### 한다

- `agents/review/`: `__init__.py`, `agent.py`, `tools.py`, `rules.py`, `prompts/review.coach.v1.md`
- 의도 (등록 순서대로 규칙을 건다)
  - `review_stats` "학습 현황·정답률·약한 노트 보기" — `(현황|통계|정답률|진도|연속|얼마나공부|약한|취약)`
  - `review_today` "오늘 복습할 카드 보기" — `^(?!.*(현황|통계|정답률)).*(복습|외울|다시볼)`
  - `profile_update` "요약 길이·퀴즈 난이도 기억하기" — `(앞으로|항상|기억해|이제부터).*(짧게|길게|자세히|간단히|쉽게|어렵게)`
- 도구: `review_list_notebooks`, `review_list_due`, `review_get_stats`, `review_get_profile`
- review_today: "오늘 복습할 카드 N장(밀린 카드 M장)" + 앞 5개 질문, `navigate` 버튼 target `review` "복습 시작". 0장이면 안내 + `ask` 버튼 "퀴즈 내줘". `data.cards`
- review_stats: 통계·약한 노트를 `ask_llm("worker", prompt("coach"), ...)`로 코칭 문장(숫자는 받은 값만), 규칙 답은 숫자 나열 + 약한 노트 1개 추천. `ask` 버튼 "{약한 노트} 요약해줘". `data.stats`
- profile_update: `rules.parse_preference(text) -> dict` (짧게/간단히→summary_length short, 길게/자세히→long, 쉽게→quiz_difficulty easy, 어렵게→hard) → 제안 `profile.update` + 버튼 [기억하기]. 못 읽으면 예시 안내
- `rules.daily_plan(notebook_id, cards, base_date) -> ProposalDraft | None` — kind `review.daily_plan`, title `"{base_date} 복습 {n}장"`, payload `{"base_date","card_ids"}`, source `agent`, source_ref notebook_id, `dedupe_key("daily_review", notebook_id, base_date)`
- `graphs/daily_review.py`: `DailyReviewState(base_date, subject_ids, proposals)`, 노드 `plan`, `build_daily_review_graph()`, 모듈 변수 `graph`. `aegra.json`에 `daily_review` 등록
- 등록 `AGENTS = [NotesAgent, QuizAgent, ReviewAgent]`
- 시험: `tests/unit/test_review_rules.py`, `tests/graph/test_review_graph.py`, 평가 `eval/cases/review.yaml`(4건 이상). 평가 실행기(`eval/runner.py`)가 케이스의 `screen`(예: `{base_date: ...}`)을 넘기게 고친다(없으면 기존과 같음)

### 하지 않는다

- 예약 실행 스케줄러(BE가 부른다 — UI 버튼, Unit 10·11)
- 통계 계산(BE)

## 상세 작업 단계

1. 규칙·단위 시험(선호 파싱, daily_plan 키 안정성, 카드 0장이면 None)
2. Agent·도구·프롬프트, 등록
3. 예약 그래프와 aegra.json
4. 그래프 시험
   - "오늘 뭐 복습해?" (screen.base_date 고정) → 장 수·밀린 장 수가 FakeBeClient 값과 같음, navigate 버튼
   - "공부 현황 어때?" 규칙 답에 정답률·연속일, 모델 답 source ai
   - "앞으로 요약은 짧게 해줘" → 제안 `profile.update` payload `{"summary_length":"short"}`
   - 예약 그래프 두 번 → 같은 dedupe_key, 카드 없는 노트북은 제안 없음
   - 의도 충돌: "복습 현황" → review_stats만
5. 평가 통과

## 사용할 수 있는 SKILL / 참고 자료

- `AGENTS.md` §2(예약 그래프는 고정 순서), §4.4

## 완료 조건 (Definition of Done)

- [ ] `.\.venv\Scripts\python.exe -m pytest -q` 전체 통과
- [ ] `.\.venv\Scripts\python.exe -m study_notes.eval` 통과
- [ ] `ruff check`·`ruff format --check`·`mypy` 통과
- [ ] `aegra.json`에 `chat`, `daily_review`

## 산출물 (Output)

- `src/study_notes/agents/review/**`, `src/study_notes/graphs/daily_review.py`, `src/study_notes/agents/registry.py`, `aegra.json`, `src/study_notes/eval/runner.py`
- 시험·평가 파일
