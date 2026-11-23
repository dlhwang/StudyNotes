"""화면 공통: BE 클라이언트, 세션 상태, 사이드바(노트북·기준일), 페이지 목록."""

from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

from notes_ui.api import BeApi, BeApiError

PAGES: dict[str, Any] = {}


@st.cache_resource
def get_api() -> BeApi:
    return BeApi()


def init_state() -> None:
    defaults: dict[str, Any] = {
        "notebook_id": None,
        "base_date": date.today(),
        "threads": {},  # 노트북 → thread_id
        "chat_log": {},  # 노트북 → [{"role": "user", "text"} | {"role": "assistant", "events"}]
        "current_note_id": None,  # 노트 화면에서 고른 노트 → 채팅의 screen.note_id
        "pending_ask": None,  # ask 버튼이 보낸 다음 질문
        "flash": None,  # 다음 화면에 한 번 보여 줄 알림
        "show_answer": False,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def notebook_id() -> str:
    return str(st.session_state.notebook_id)


def base_date() -> str:
    value = st.session_state.base_date
    return value.isoformat() if isinstance(value, date) else str(value)


def flash(message: str, ok: bool = True) -> None:
    st.session_state.flash = (message, ok)


def show_flash() -> None:
    item = st.session_state.get("flash")
    if item:
        message, ok = item
        (st.success if ok else st.warning)(message)
        st.session_state.flash = None


def sidebar() -> bool:
    """사이드바를 그린다. BE에 연결되지 않으면 False."""
    api = get_api()
    with st.sidebar:
        st.markdown("### 📚 학습 노트 비서")
        try:
            notebooks = api.notebooks()
            health = api.health()
        except BeApiError as e:
            st.error(e.detail)
            st.code("uvicorn notes_api.main:app --port 8000", language="powershell")
            return False
        if not notebooks:
            st.warning("노트북이 없습니다.")
            return False
        ids = [nb["id"] for nb in notebooks]
        names = {nb["id"]: nb["name"] for nb in notebooks}
        if st.session_state.notebook_id not in ids:
            st.session_state.notebook_id = ids[0]
        st.selectbox("노트북", ids, format_func=lambda i: f"{names[i]} ({i})", key="notebook_id")
        st.date_input("기준일", key="base_date", help="복습 대상·통계를 계산하는 날짜")
        st.caption(f"노트 {health['notes']}개 · 청크 {health['chunks']}개 · Agent: {health['agent']}")
    return True
