"""
최소 기능 테스트 - streamlit-shadcn-ui
"""
import streamlit as st
from streamlit_shadcn_ui import button

st.title("🎯 최소 기능 테스트")

st.write("streamlit-shadcn-ui 라이브러리 테스트")

if button("테스트 버튼", key="test_btn"):
    st.success("✅ 성공! 라이브러리가 정상 작동합니다!")
else:
    st.info("버튼을 클릭해보세요.")

