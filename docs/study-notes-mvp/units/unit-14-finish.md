# Unit 14: 평가 확장·문서·패키징 마무리

## Goal (목표)

평가 질문이 모든 의도(note_summary, note_search, note_qa, quiz_make, review_today, review_stats, profile_update)와 다중 의도·대화 메모리를 덮어 통과하고, README·구조·개발 가이드가 이 서비스(학습 노트 비서) 기준으로 고쳐져 있으며, Docker 실행 파일(미검증 표시)이 있고, 다섯 검사가 모두 통과하는 상태가 된다.

## 배경 / 컨텍스트

- 문서는 템플릿 내용(할 일 예시, BMS)을 담고 있다: `README.md`, `docs/01-구조.md`, `docs/02-개발-가이드.md`, `AGENTS.md`(규칙은 유지, 예시 이름만).
- 평가 실행기: `src/study_notes/eval/runner.py`, 케이스 `src/study_notes/eval/cases/*.yaml`(`id, question, expected_intent, must_include, subject_id, screen?`). 판정: 첫 의도 일치 + 핵심 말 포함.
- 과제 요구 대응표는 `docs/study-notes-mvp/00-overview.md`에 있다.
- 이 PC에 Docker가 없다(2026-11-23).

## 선행 조건 (Dependencies)

- Unit 01~13 완료(12는 차단이어도 됨)

## 작업 범위 (Scope)

### 한다

- 평가: 의도별 2건 이상, 다중 의도 2건, 합계 15건 이상. 실행기에 `expected_intents`(다중 의도 전체 일치, 선택 필드)
- `README.md` 전면 개정: 소개, 구조도, 과제 요구 대응표, 빠른 실행(BE·UI, 가짜 모델), 실제 모델 켜기, Aegra 모드, MCP, 시험·평가 명령, 데모 시나리오
- `docs/01-구조.md`: 그래프·Agent·의도·도구·이벤트·BE API 표를 이 서비스 기준으로
- `docs/02-개발-가이드.md`: 예시를 notes/quiz/review 기준으로, BE·UI 실행 절차
- `AGENTS.md`: 예시 이름(tasks) → notes, BE 패키지(`notes_api`)와 Agent 패키지 경계 규칙 한 줄
- `Dockerfile`(BE·Agent 공용 이미지), `docker-compose.yml`(postgres, aegra, api, ui) — 머리말에 "이 PC에서 미검증"
- 전체 검사 다섯 개

### 하지 않는다

- 새 기능

## 상세 작업 단계

1. 평가 케이스 추가, 실행기 확장, 실패 원인을 Agent 규칙 쪽에서 고침(평가 기준을 낮추지 않는다)
2. 문서 개정
3. Docker 파일
4. 전체 검사, 개요 상태 기록 갱신

## 사용할 수 있는 SKILL / 참고 자료

- `docs/study-notes-mvp/00-overview.md` 과제 요구 대응표

## 완료 조건 (Definition of Done)

- [ ] `.\.venv\Scripts\python.exe -m pytest -q` 통과
- [ ] `.\.venv\Scripts\python.exe -m ruff check src tests tools migrations app` 통과
- [ ] `.\.venv\Scripts\python.exe -m ruff format --check src tests tools migrations app` 통과
- [ ] `.\.venv\Scripts\python.exe -m mypy` 통과
- [ ] `.\.venv\Scripts\python.exe -m study_notes.eval` 통과(15건 이상)
- [ ] README에 과제 요구 대응표와 실행 방법

## 산출물 (Output)

- `src/study_notes/eval/**`, `README.md`, `docs/01-구조.md`, `docs/02-개발-가이드.md`, `AGENTS.md`, `Dockerfile`, `docker-compose.yml`
