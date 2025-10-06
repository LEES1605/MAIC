#!/usr/bin/env python3
"""간단한 Streamlit 테스트 앱"""

import streamlit as st

st.title("간단한 테스트 앱")
st.write("Streamlit이 정상적으로 작동하는지 테스트합니다.")

if st.button("테스트 버튼"):
    st.success("버튼이 정상적으로 작동합니다!")

st.write("현재 시간:", st.session_state.get("current_time", "알 수 없음"))
