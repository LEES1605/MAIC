import streamlit as st
from src.ui.header_component import HeaderComponent

st.set_page_config(
    page_title="Header Test",
    page_icon="🧪",
    layout="wide"
)

# HeaderComponent 테스트
header = HeaderComponent()
header.render()

st.write("HeaderComponent가 렌더링되었습니다!")

