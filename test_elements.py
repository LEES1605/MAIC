"""
streamlit-elements 테스트
"""
import streamlit as st
from streamlit_elements import elements, mui, html

st.title("🎨 streamlit-elements 테스트")

st.write("streamlit-elements 라이브러리로 Neumorphism 스타일 테스트")

with elements("neumorphism_test"):
    # Neumorphism 스타일의 카드
    mui.Card(
        mui.CardContent(
            mui.Typography("Neumorphism Card", variant="h5"),
            mui.Typography("이것은 streamlit-elements로 만든 카드입니다.", variant="body2"),
        ),
        sx={
            "background": "linear-gradient(135deg, #2c2f48 0%, #1a1d2e 100%)",
            "borderRadius": "20px",
            "boxShadow": "8px 8px 16px rgba(0, 0, 0, 0.3), -8px -8px 16px rgba(255, 255, 255, 0.1)",
            "color": "#c1c3e0",
            "padding": "20px",
            "margin": "20px",
        }
    )
    
    # Neumorphism 스타일의 버튼
    mui.Button(
        "Neumorphism Button",
        variant="contained",
        sx={
            "background": "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
            "borderRadius": "20px",
            "boxShadow": "8px 8px 16px rgba(0, 0, 0, 0.3), -8px -8px 16px rgba(255, 255, 255, 0.1)",
            "color": "white",
            "fontWeight": "600",
            "padding": "12px 24px",
            "margin": "20px",
            "&:hover": {
                "transform": "translateY(-2px)",
                "boxShadow": "12px 12px 24px rgba(0, 0, 0, 0.4), -12px -12px 24px rgba(255, 255, 255, 0.15)",
            }
        }
    )

