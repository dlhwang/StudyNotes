# Unit 01: 개발 환경과 기준선

## Goal (목표)

`D:\workspace\study-notes`에 `.venv`가 있고, 이후 Unit이 쓸 의존성 묶음(`api`·`ui`·`mcp`)이 `pyproject.toml`에 선언돼 설치돼 있으며, 템플릿 그대로의 검사 다섯 개(시험·린트·형식·타입·평가)가 통과하는 상태가 된다.

## 배경 / 컨텍스트

- 이 저장소는 agent-template(`D:\workspace\agent-template`)을 `tools/new_project.py`로 복사해 패키지 이름을 `study_notes`로 바꾼 것이다(커밋 `5673e1f`). `.venv`는 복사되지 않았다.
- 이후 Unit이 FastAPI BE(`src/notes_api`), Streamlit UI 로직(`src/notes_ui`), MCP 서버(`src/notes_mcp`)를 추가한다. 패키지 목록·mypy 대상·의존성을 미리 열어 둔다.

## 선행 조건 (Dependencies)

- Python 3.12 이상(이 PC: `py -3.13`, 3.13.7)
- 인터넷으로 PyPI 설치 가능
- 참고: `pyproject.toml`, `docs/02-개발-가이드.md` §1~§2, `.gitignore`

## 작업 범위 (Scope)

### 한다

- `.venv` 만들기, `pip install -e ".[dev,postgres,llm,api,ui,mcp]"`
- `pyproject.toml`
  - 선택 의존성 추가: `api = ["fastapi>=0.115", "uvicorn[standard]>=0.30", "chromadb>=1.0"]`, `ui = ["streamlit>=1.40"]`, `mcp = ["mcp>=1.2"]`
  - wheel 패키지 목록에 `src/notes_api`, `src/notes_ui`, `src/notes_mcp` 추가(폴더는 빈 `__init__.py`로 만든다)
  - mypy `packages`에 세 패키지 추가, 타입 정보가 없는 외부 모듈(`chromadb`, `streamlit`, `mcp` 등)은 `ignore_missing_imports`
  - 프로젝트 설명을 "학습 노트 비서"로
- `.gitignore`에 `data/`(개발 SQLite·Chroma) 추가
- 다섯 검사 실행, 결과 기록

### 하지 않는다

- 기능 코드 작성, 예시 Agent 삭제(Unit 07)
- README 전면 개정(Unit 14)

## 상세 작업 단계

1. `py -3.13 -m venv .venv`
2. `pyproject.toml` 수정(위 목록). `ruff` 검사 대상에 `app` 폴더가 생기므로 `[tool.ruff] src`에 `"app"` 추가.
3. `src/notes_api/__init__.py`, `src/notes_ui/__init__.py`, `src/notes_mcp/__init__.py` 생성(한 줄 독스트링).
4. `.\.venv\Scripts\python.exe -m pip install -e ".[dev,postgres,llm,api,ui,mcp]"` — 설치 실패 패키지는 원인(휠 없음 등)을 상태 기록에 남긴다. chromadb가 실패하면 `faiss-cpu`로 바꿀 수 있는지 확인만 하고 기록한다.
5. 다섯 검사 실행.

## 사용할 수 있는 SKILL / 참고 자료

- `docs/02-개발-가이드.md` §2 검사 명령 표

## 완료 조건 (Definition of Done)

- [ ] `.\.venv\Scripts\python.exe -c "import fastapi, chromadb, streamlit, mcp, litellm"` 성공
- [ ] `.\.venv\Scripts\python.exe -m pytest -q` 통과
- [ ] `.\.venv\Scripts\python.exe -m ruff check src tests tools migrations` 통과
- [ ] `.\.venv\Scripts\python.exe -m ruff format --check src tests tools migrations` 통과
- [ ] `.\.venv\Scripts\python.exe -m mypy` 통과
- [ ] `.\.venv\Scripts\python.exe -m study_notes.eval` 통과

## 산출물 (Output)

- `pyproject.toml`, `.gitignore`
- `src/notes_api/__init__.py`, `src/notes_ui/__init__.py`, `src/notes_mcp/__init__.py`
