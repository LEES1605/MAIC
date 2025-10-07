"""
초간단 테스트
"""
import streamlit as st

st.set_page_config(
    page_title="Ultra Simple",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.title("🎉 이것이 보이나요?")

st.markdown("""
<div style="background: linear-gradient(135deg, #2c2f48 0%, #1a1d2e 100%); 
            padding: 20px; 
            border-radius: 20px; 
            color: white; 
            font-family: 'Arial', sans-serif;">
    <h2>Neumorphism 테스트</h2>
    <p>이 텍스트가 보이면 Streamlit이 정상 작동하는 것입니다!</p>
    <button onclick="alert('버튼 클릭!')" style="background: #6366f1; color: white; border: none; padding: 10px 20px; border-radius: 10px; cursor: pointer;">
        클릭해보세요!
    </button>
</div>
""", unsafe_allow_html=True)

st.button("Streamlit 버튼 테스트")

