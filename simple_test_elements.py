"""
streamlit-elements 간단 테스트
"""
import streamlit as st
from streamlit_elements import elements, mui

st.set_page_config(
    page_title="Simple Test",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.title("Simple Elements Test")

with elements("test"):
    mui.Box(
        mui.Typography("Hello World!", variant="h3"),
        sx={
            "background": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            "color": "white",
            "padding": "20px",
            "borderRadius": "10px",
            "textAlign": "center"
        }
    )



