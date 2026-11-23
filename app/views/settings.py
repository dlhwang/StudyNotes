"""설정 화면: 학습자 프로필(장기 메모리), 약한 노트, 검색 색인 다시 적재."""

from __future__ import annotations

import streamlit as st

from common import base_date, flash, get_api, show_flash

LENGTHS = {"short": "짧게(3줄)", "normal": "보통(4줄)", "long": "자세히(5줄)"}
LEVELS = {"easy": "쉽게", "normal": "보통", "hard": "어렵게"}

api = get_api()
st.title("설정")
show_flash()

profile = api.profile(base_date())
st.subheader("학습자 프로필 (장기 메모리)")
st.caption("Agent가 요약 길이·퀴즈 난이도를 정할 때 읽습니다. 채팅에서 '앞으로 요약은 짧게 해줘'라고 해도 바뀝니다.")
with st.form("profile"):
    length = st.radio(
        "요약 길이",
        list(LENGTHS),
        index=list(LENGTHS).index(profile["summary_length"]),
        format_func=LENGTHS.get,
        horizontal=True,
    )
    level = st.radio(
        "퀴즈 난이도",
        list(LEVELS),
        index=list(LEVELS).index(profile["quiz_difficulty"]),
        format_func=LEVELS.get,
        horizontal=True,
    )
    if st.form_submit_button("저장", type="primary"):
        api.set_profile(length, level)
        flash("프로필을 저장했습니다.")
        st.rerun()

st.subheader("약한 노트")
st.caption("최근 2주 복습에서 '다시'가 2번 이상 나온 노트 (BE가 계산)")
if profile["weak_notes"]:
    st.dataframe(
        [
            {"노트": w["title"], "ID": w["note_id"], "최근 2주 다시": w["again_count_14d"]}
            for w in profile["weak_notes"]
        ],
        hide_index=True,
    )
else:
    st.write("없습니다.")

st.subheader("검색 색인")
health = api.health()
st.write(f"노트 {health['notes']}개 · 청크 {health['chunks']}개 · Agent 실행: {health['agent']}")
if st.button("전체 다시 적재"):
    flash(f"청크 {api.reindex()}개를 다시 적재했습니다.")
    st.rerun()
