# 학습 노트 비서 — BE·화면·Agent(Aegra)·MCP 공용 이미지.
# ⚠ 이 저장소를 만든 PC에는 Docker가 없어 빌드·실행을 확인하지 않았다(2026-11-23).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml README.md aegra.json alembic.ini ./
COPY src ./src
COPY app ./app
COPY migrations ./migrations
RUN pip install ".[api,ui,mcp,llm,server,postgres]"

# 노트(SQLite)·검색 색인(Chroma)
VOLUME ["/app/data"]
EXPOSE 8000 8501 2026

# 기본은 BE. 화면·Aegra는 docker-compose.yml에서 command를 바꾼다
CMD ["uvicorn", "notes_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
