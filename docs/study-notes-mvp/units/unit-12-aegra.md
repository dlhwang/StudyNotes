# Unit 12: Aegra 실행 연동

## Goal (목표)

PostgreSQL이 떠 있는 개발 PC에서 `aegra serve`로 `chat`·`daily_review` 그래프가 뜨고, BE를 `NOTES_API_AGENT_MODE=aegra`로 띄우면 UI의 채팅·예약 실행이 Aegra를 거쳐 같은 결과를 내는 상태가 된다. `tools/smoke_aegra.py`가 통과한다. PostgreSQL을 쓸 수 없으면 코드·설정·문서까지 마치고 차단 사유를 기록한다.

## 배경 / 컨텍스트

- Aegra 0.12는 LangGraph Platform 대체 서버다. `aegra.json`(그래프·인증·체크포인터 설정)을 읽고, PostgreSQL에 thread·run·체크포인트 테이블을 스스로 만든다. 접속은 `.env`의 `POSTGRES_HOST/PORT/DB/USER/PASSWORD`(`DATABASE_URL`은 두지 않는다).
- 인증: `src/study_notes/server/auth.py`, `STUDY_NOTES_AUTH__MODE=dev`면 `X-User-Id` 헤더만 본다.
- Aegra 안의 Agent는 BE를 HTTP로 부른다: `.env`에 `STUDY_NOTES_BE__MODE=http`, `STUDY_NOTES_BE__BASE_URL=http://127.0.0.1:8000`, `STUDY_NOTES_BE__PATH_PREFIX=/internal/agent`.
- BE의 `AegraBridge`(Unit 10)가 `NOTES_API_AEGRA_URL`(기본 `http://127.0.0.1:2026`)로 붙는다.
- 개발 PC: PostgreSQL 17 서비스 `postgresql-x64-17` 설치·**멈춤**(2026-11-23). 서비스를 켜고 비밀번호를 `.env`에 넣는 것은 사용자 확인이 필요하다.

## 선행 조건 (Dependencies)

- Unit 10(AegraBridge), Unit 11(UI)
- `pip install -e ".[server]"`(aegra-cli 0.12)
- 참고: `docs/02-개발-가이드.md` §3, `.env.example`, `aegra.json`, `tools/smoke_aegra.py`

## 작업 범위 (Scope)

### 한다

- `.env.example` 갱신: BE 모드 http·주소, `NOTES_API_*`, `NOTES_UI_*`, 임베딩 설정
- `tools/smoke_aegra.py`: 노트 질문(`subject_id="NB-1"`)과 `daily_review` 실행 확인
- `tools/run_dev.ps1`(선택): BE·UI(·Aegra)를 각각 새 창으로 띄우는 스크립트
- PostgreSQL 사용 가능하면: `python -m study_notes.db check` → `aegra serve` → `smoke_aegra.py` → BE aegra 모드로 UI 채팅 1회
- 불가능하면: 상태 기록에 "차단" + 사유, 질문 목록 갱신

### 하지 않는다

- PostgreSQL 설치·서비스 설정 변경(사용자 몫), Aegra 내부 수정

## 상세 작업 단계

1. `pip install -e ".[server]"`, `aegra --help` 확인
2. `.env.example` 갱신
3. 5432 포트 확인. 응답이 없으면 차단 기록 후 6번으로
4. `.env` 작성(사용자 값), `aegra serve --host 127.0.0.1 --port 2026`(백그라운드)
5. `smoke_aegra.py` 실행, BE aegra 모드 확인
6. 문서(`docs/02-개발-가이드.md` §3)에 이 서비스 기준 실행 순서 반영

## 사용할 수 있는 SKILL / 참고 자료

- `docs/02-개발-가이드.md` §3
- Aegra 문서(docs.aegra.dev)

## 완료 조건 (Definition of Done)

- [ ] `aegra-cli` 설치, `aegra.json` 그래프 경로가 import 가능(`python -c "import study_notes.graphs.chat, study_notes.graphs.daily_review"`)
- [ ] PostgreSQL 가능 시 `smoke_aegra.py` 통과 / 불가 시 차단 사유 기록
- [ ] `.\.venv\Scripts\python.exe -m pytest -q` 통과(변경 없음 확인)

## 산출물 (Output)

- `.env.example`, `tools/smoke_aegra.py`, `tools/run_dev.ps1`(선택), `docs/02-개발-가이드.md`
