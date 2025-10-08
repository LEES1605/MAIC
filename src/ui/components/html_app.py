# HTML 컴포넌트 기반 MAIC 앱
"""
HTML 컴포넌트를 사용한 완전한 MAIC 앱 UI
Streamlit의 CSS 제약을 우회하여 완전한 Neumorphism 디자인 구현
"""

from __future__ import annotations
import streamlit as st
from pathlib import Path


def render_html_app() -> None:
    """(Deprecated) 기존 경로는 사용하지 않고 정본 UI만 렌더링"""
    render_neumorphism_html_file()


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


def render_neumorphism_html_file() -> None:
    """src/ui/neumorphism_app.html 파일을 렌더링 (순수 HTML UI)"""
    # html 파일 경로를 모듈 상대경로로 안전하게 계산
    html_file = (Path(__file__).parent.parent / "neumorphism_app.html").resolve()

    if not html_file.exists():
        st.error(f"UI 파일을 찾을 수 없습니다: {html_file}")
        _render_fallback_ui()
        return

    try:
        html_content = html_file.read_text(encoding="utf-8")
        st.components.v1.html(html_content, height=1000, scrolling=True)
    except Exception as e:
        st.error(f"HTML 로드 실패: {e}")
        _render_fallback_ui()
