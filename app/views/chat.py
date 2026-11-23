"""채팅 화면: 질문 → BE → Agent(SSE) → 답·근거·실행 흔적·버튼."""

from __future__ import annotations

from typing import Any

import streamlit as st

from common import PAGES, base_date, flash, get_api, notebook_id, show_flash
from notes_ui.actions import handle_action
from notes_ui.view import ReplyView, turn_view

EXAMPLES = [
    "체크포인터가 뭐야?",
    "StateGraph 기초 요약해줘",
    "그 노트로 퀴즈 내줘",
    "오늘 뭐 복습해?",
    "공부 현황 어때?",
    "앞으로 요약은 짧게 해줘",
]

api = get_api()
nb = notebook_id()
log: list[dict[str, Any]] = st.session_state.chat_log.setdefault(nb, [])
if nb not in st.session_state.threads:
    st.session_state.threads[nb] = api.new_thread()
thread_id = st.session_state.threads[nb]

st.title("채팅")
current = st.session_state.current_note_id
cols = st.columns([4, 1])
cols[0].caption(
    f"보고 있는 노트: **{current}** — '이 노트'라고 물으면 이 노트를 씁니다"
    if current
    else "노트 화면에서 노트를 고르면 '이 노트'로 물을 수 있습니다"
)
if cols[1].button("새 대화", use_container_width=True):
    st.session_state.threads[nb] = api.new_thread()
    st.session_state.chat_log[nb] = []
    st.rerun()
show_flash()


def render_reply(rv: ReplyView, key: str) -> None:
    st.markdown(f"**{rv.label}** · :gray[{rv.badge}]")
    st.markdown(rv.text.replace("\n", "  \n"))
    if rv.table:
        st.dataframe(rv.table, hide_index=True, use_container_width=True)
    if rv.citations:
        with st.expander(f"근거 {len(rv.citations)}개"):
            for c in rv.citations:
                st.markdown(f"- **{c.get('title')}** — {c.get('location', '')}")
    if rv.trace:
        with st.expander("Agent 실행 흔적 (ReAct)"):
            for s in rv.trace:
                st.markdown(f"**{s.get('step')}단계** `{s.get('tool')}` {s.get('args')}")
                st.caption(str(s.get("observation", ""))[:200])
    if rv.actions:
        bcols = st.columns(len(rv.actions))
        for k, action in enumerate(rv.actions):
            primary = action.get("kind") == "save_proposal"
            if bcols[k].button(
                action.get("label", "버튼"), key=f"{key}-{k}", type="primary" if primary else "secondary"
            ):
                outcome = handle_action(api, rv.raw, action, base_date())
                if outcome.kind == "ask" and outcome.ask_text:
                    st.session_state.pending_ask = outcome.ask_text
                elif outcome.kind == "navigate" and outcome.page in PAGES:
                    st.switch_page(PAGES[outcome.page])
                elif outcome.message:
                    flash(outcome.message, outcome.ok)
                st.rerun()


for i, entry in enumerate(log):
    if entry["role"] == "user":
        with st.chat_message("user"):
            st.write(entry["text"])
        continue
    turn = turn_view(entry["events"])
    with st.chat_message("assistant"):
        if turn.header:
            st.caption(turn.header)
        for err in turn.errors:
            st.error(err)
        for j, rv in enumerate(turn.replies):
            if j:
                st.divider()
            render_reply(rv, f"act-{nb}-{i}-{j}")

if not log:
    st.markdown("무엇이든 물어보세요. 예시:")
    ecols = st.columns(3)
    for n, example in enumerate(EXAMPLES):
        if ecols[n % 3].button(example, key=f"ex-{n}", use_container_width=True):
            st.session_state.pending_ask = example
            st.rerun()

typed = st.chat_input("노트에 대해 물어보세요")
text = typed or st.session_state.pending_ask
if text:
    st.session_state.pending_ask = None
    log.append({"role": "user", "text": text})
    screen: dict[str, Any] = {"base_date": base_date()}
    if current:
        screen["note_id"] = current
    with st.spinner("Agent가 답하는 중…"):
        events = list(api.stream_chat(thread_id, text, nb, screen))
    log.append({"role": "assistant", "events": events})
    st.rerun()
