"""복습 화면: 오늘 계획 만들기(예약 그래프) → 카드 넘기기 → 등급 매기기(BE가 다음 복습일 계산)."""

from __future__ import annotations

import streamlit as st

from common import base_date, flash, get_api, notebook_id, show_flash

GRADES = [("again", "다시", "다시 틀림 → 내일"), ("hard", "어려움", ""), ("good", "알맞음", ""), ("easy", "쉬움", "")]

api = get_api()
nb = notebook_id()
day = base_date()

st.title("복습")
show_flash()

stats = api.stats(nb, day)
m = st.columns(4)
m[0].metric("오늘 복습", stats["due_today"], help="다음 복습일이 기준일 이전·당일인 카드")
m[1].metric("밀린 카드", stats["overdue"])
rate = stats["correct_rate_7d_pct"]
m[2].metric("7일 정답률", f"{rate}%" if rate is not None else "-")
m[3].metric("연속 학습", f"{stats['streak_days']}일")

plan = api.daily_plan(nb, day)
if plan["plan"] is None:
    st.info("오늘 복습 계획이 없습니다. 복습 코치 Agent에게 계획을 만들어 달라고 할 수 있습니다.")
    if st.button("오늘 계획 만들기", type="primary"):
        saved = api.run_daily_review(day)
        mine = [p for p in saved if p["subject_id"] == nb]
        flash(mine[0]["title"] if mine else "오늘 복습할 카드가 없습니다.", bool(mine))
        st.rerun()
    st.stop()

cards = plan["cards"]
left = [c for c in cards if c["due_date"] <= day]
st.progress(1 - len(left) / len(cards) if cards else 1.0, text=f"{plan['plan']['title']} — 남은 카드 {len(left)}장")
if not left:
    st.success("오늘 계획을 모두 끝냈습니다. 수고했어요!")
    st.stop()

card = left[0]
with st.container(border=True):
    st.caption(f"{card['note_title']} · {card['id']}")
    st.markdown(f"### {card['question']}")
    if st.session_state.show_answer:
        st.markdown(f"**답:** {card['answer']}")
    elif st.button("답 보기"):
        st.session_state.show_answer = True
        st.rerun()

if st.session_state.show_answer:
    cols = st.columns(len(GRADES))
    for col, (grade, label, help_text) in zip(cols, GRADES, strict=True):
        if col.button(label, key=f"grade-{grade}", use_container_width=True, help=help_text or None):
            updated = api.review(card["id"], grade, day)
            st.session_state.show_answer = False
            flash(f"'{label}' — 다음 복습일 {updated['due_date']} ({updated['interval_days']}일 뒤)")
            st.rerun()
