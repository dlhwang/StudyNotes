"""BE 시험 공통: 메모리 SQLite·메모리 Chroma·해시 임베딩·데모 시드로 BE 앱을 만든다."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from notes_api.config import ApiSettings
from notes_api.main import create_app
from notes_api.rag import HashEmbedder, NoteIndex, make_client
from notes_api.store import Store

TODAY = "2026-11-23"


def make_test_app() -> FastAPI:
    settings = ApiSettings(_env_file=None, seed_demo=True)  # type: ignore[call-arg]
    store = Store(":memory:", clock=lambda: datetime(2026, 11, 23, 9, 0, 0))
    index = NoteIndex(make_client(None), HashEmbedder(), collection=f"t-{uuid.uuid4().hex[:8]}")
    return create_app(settings, store=store, index=index)


@pytest.fixture
def api_app() -> FastAPI:
    return make_test_app()


@pytest.fixture
def client(api_app: FastAPI) -> TestClient:
    return TestClient(api_app)
