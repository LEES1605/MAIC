# HTML 컴포넌트 기반 MAIC 앱
"""
HTML 컴포넌트를 사용한 완전한 MAIC 앱 UI
Streamlit의 CSS 제약을 우회하여 완전한 Neumorphism 디자인 구현
"""

from __future__ import annotations
import streamlit as st
from pathlib import Path


def render_html_app() -> None:
    """HTML 컴포넌트로 전체 MAIC 앱 렌더링"""
    if st is None:
        return
    
    # Streamlit 기본 사이드바 숨기기
    st.markdown("""
    <style>
    .css-1d391kg, .css-1cypcdb {
        display: none !important;
    }
    
    .main .block-container {
        padding-top: 1rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    
    .stApp > div {
        padding-top: 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # HTML 파일 경로
    html_file = Path("static/maic_app.html")
    
    if not html_file.exists():
        st.error("HTML 앱 파일을 찾을 수 없습니다.")
        return
    
    try:
        # HTML 파일 읽기
        with open(html_file, "r", encoding="utf-8") as f:
            html_content = f.read()
        
        # HTML 컴포넌트로 렌더링
        st.components.v1.html(
            html_content, 
            height=1000, 
            scrolling=True
        )
        
    except Exception as e:
        st.error(f"HTML 컴포넌트 로드 실패: {e}")
        # 폴백으로 기본 UI 표시
        _render_fallback_ui()


def _render_fallback_ui() -> None:
    """HTML 컴포넌트 실패 시 폴백 UI"""
    st.title("🎨 MAIC - AI Teacher")
    st.markdown("HTML 컴포넌트를 로드할 수 없습니다. 기본 UI를 표시합니다.")
    
    # 기본 기능들
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 문법")
        if st.button("문법 학습 시작", key="grammar"):
            st.info("문법 모드로 전환되었습니다.")
    
    with col2:
        st.markdown("### 독해")
        if st.button("독해 학습 시작", key="reading"):
            st.info("독해 모드로 전환되었습니다.")
    
    with col3:
        st.markdown("### 작문")
        if st.button("작문 학습 시작", key="writing"):
            st.info("작문 모드로 전환되었습니다.")
    
    # 질문 입력
    question = st.text_input("질문을 입력하세요:", placeholder="예: 현재완료시제에 대해 설명해주세요")
    if st.button("질문 제출"):
        if question:
            st.success(f"질문이 제출되었습니다: {question}")
        else:
            st.warning("질문을 입력해주세요.")
