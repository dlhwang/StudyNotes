"""FastAPI BE 진입점.

    uvicorn notes_api.main:app --port 8000

- 공개 API(화면용)와 내부 조회 API(Agent용, ``/internal/agent``)를 연다.
- 저장소·색인을 넘기지 않으면 시작할 때 설정(``NOTES_API_*``)으로 만든다. 비어 있으면 데모 노트를 넣고 적재한다.
- 시험은 ``create_app(settings, store=Store(":memory:"), index=메모리 색인)``으로 만든다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from notes_api.config import ApiSettings, get_api_settings
from notes_api.deps import AppState
from notes_api.errors import install_handlers
from notes_api.rag import NoteIndex, build_embedder, make_client, reindex_all
from notes_api.routes import internal, public
from notes_api.store import Store, seed_demo


def _prepare(settings: ApiSettings, store: Store, index: NoteIndex) -> AppState:
    if settings.seed_demo and seed_demo(store, store.today()):
        reindex_all(index, store.all_notes())
    elif index.count() == 0 and store.all_notes():
        reindex_all(index, store.all_notes())
    return AppState(settings=settings, store=store, index=index)


def _build_default(settings: ApiSettings) -> AppState:
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    Path(settings.chroma_dir).mkdir(parents=True, exist_ok=True)
    store = Store(settings.db_path)
    index = NoteIndex(
        make_client(settings.chroma_dir), build_embedder(settings.embedding_mode, settings.embedding_model)
    )
    return _prepare(settings, store, index)


def create_app(
    settings: ApiSettings | None = None, *, store: Store | None = None, index: NoteIndex | None = None
) -> FastAPI:
    cfg = settings or get_api_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if getattr(app.state, "notes", None) is None:
            app.state.notes = _build_default(cfg)
        yield

    app = FastAPI(title="학습 노트 비서 BE", version="0.1.0", lifespan=lifespan)
    install_handlers(app)
    app.include_router(public.router)
    app.include_router(internal.router)
    if store is not None and index is not None:
        app.state.notes = _prepare(cfg, store, index)
    return app


app = create_app()
