"""학습 노트 비서 화면 (Streamlit).

    streamlit run app/streamlit_app.py

BE(``uvicorn notes_api.main:app --port 8000``)가 먼저 떠 있어야 한다. 화면은 BE 공개 API만 부른다.
"""

from __future__ import annotations

import streamlit as st

from common import PAGES, init_state, sidebar

st.set_page_config(page_title="학습 노트 비서", page_icon="📚", layout="wide")

PAGES.update(
    {
        "chat": st.Page("views/chat.py", title="채팅", icon=":material/chat:", url_path="chat", default=True),
        "notes": st.Page("views/notes.py", title="노트", icon=":material/description:", url_path="notes"),
        "review": st.Page("views/review.py", title="복습", icon=":material/style:", url_path="review"),
        "settings": st.Page("views/settings.py", title="설정", icon=":material/tune:", url_path="settings"),
    }
)

init_state()
page = st.navigation(list(PAGES.values()))
if sidebar():
    page.run()
