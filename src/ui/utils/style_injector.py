# 스타일 주입 유틸리티
from __future__ import annotations
import streamlit as st
from typing import Dict, Any

class StyleInjector:
    """스타일 주입을 위한 유틸리티 클래스"""
    
    @staticmethod
    def inject_css(css: str) -> None:
        """CSS 스타일을 주입합니다."""
        if st is None:
            return
        
        try:
            st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"CSS 주입 오류: {e}")
    
    @staticmethod
    def inject_js(js: str) -> None:
        """JavaScript를 주입합니다."""
        if st is None:
            return
        
        try:
            st.markdown(f"<script>{js}</script>", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"JavaScript 주입 오류: {e}")
    
    @staticmethod
    def inject_html(html: str) -> None:
        """HTML을 주입합니다."""
        if st is None:
            return
        
        try:
            st.markdown(html, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"HTML 주입 오류: {e}")


