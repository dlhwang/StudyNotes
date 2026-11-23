"""노트 화면: 목록·검색, 보기, 쓰기·고치기·지우기. 저장하면 BE가 RAG 색인에 적재한다."""

from __future__ import annotations

import streamlit as st

from common import PAGES, flash, get_api, notebook_id, show_flash
from notes_ui.api import BeApiError

api = get_api()
nb = notebook_id()

st.title("노트")
show_flash()
left, right = st.columns([1, 2], gap="large")

with left:
    query = st.text_input("검색", placeholder="제목·태그·본문 키워드")
    notes = api.notes(nb, query or None)
    if not notes:
        st.info("노트가 없습니다.")
    ids = [n["id"] for n in notes]
    titles = {n["id"]: n["title"] for n in notes}
    current = st.session_state.current_note_id
    selected = st.radio(
        "노트 목록",
        ids,
        index=ids.index(current) if current in ids else None,
        format_func=lambda i: f"{titles[i]} ({i})",
        label_visibility="collapsed",
    )
    if selected and selected != current:
        st.session_state.current_note_id = selected
        st.rerun()
    with st.expander("새 노트 쓰기", expanded=not notes):
        with st.form("new-note", clear_on_submit=True):
            title = st.text_input("제목")
            tags = st.text_input("태그(쉼표로)")
            body = st.text_area("본문", height=220, placeholder="## 소제목\n내용…\n\n- 용어: 설명")
            if st.form_submit_button("저장", type="primary"):
                try:
                    created = api.create_note(nb, title, body, [t.strip() for t in tags.split(",") if t.strip()])
                    st.session_state.current_note_id = created["id"]
                    flash(f"저장했습니다. 검색 색인에 청크 {created['chunks']}개를 적재했습니다.")
                    st.rerun()
                except BeApiError as e:
                    st.error(e.detail)

with right:
    note_id = st.session_state.current_note_id
    if not note_id or note_id not in ids:
        st.caption("왼쪽에서 노트를 고르세요.")
    else:
        note = api.note(note_id)
        st.subheader(note["title"])
        st.caption(f"{note['id']} · 태그: {', '.join(note['tags']) or '없음'} · 수정 {note['updated_at']}")
        b1, b2, b3 = st.columns(3)
        if b1.button("이 노트로 채팅", use_container_width=True):
            st.session_state.pending_ask = f"{note['title']} 요약해줘"
            st.switch_page(PAGES["chat"])
        if b2.button("퀴즈 만들기", use_container_width=True):
            st.session_state.pending_ask = f"{note['title']} 퀴즈 내줘"
            st.switch_page(PAGES["chat"])
        if b3.button("지우기", use_container_width=True):
            api.delete_note(note_id)
            st.session_state.current_note_id = None
            flash("지웠습니다.")
            st.rerun()
        st.markdown(note["body"])
        cards = api.cards(nb, note_id)
        with st.expander(f"이 노트의 카드 {len(cards)}장"):
            if cards:
                st.dataframe(
                    [{"질문": c["question"], "답": c["answer"], "다음 복습": c["due_date"]} for c in cards],
                    hide_index=True,
                    use_container_width=True,
                )
        with st.expander("고치기"):
            with st.form(f"edit-{note_id}"):
                title = st.text_input("제목", note["title"])
                tags = st.text_input("태그(쉼표로)", ", ".join(note["tags"]))
                body = st.text_area("본문", note["body"], height=300)
                if st.form_submit_button("저장", type="primary"):
                    try:
                        saved = api.update_note(note_id, title, body, [t.strip() for t in tags.split(",") if t.strip()])
                        flash(f"고쳤습니다. 청크 {saved['chunks']}개로 다시 적재했습니다.")
                        st.rerun()
                    except BeApiError as e:
                        st.error(e.detail)
