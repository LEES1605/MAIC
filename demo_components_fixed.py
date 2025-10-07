#!/usr/bin/env python3
"""
Linear 컴포넌트 데모 페이지 실행 스크립트 (수정된 버전)
"""

import streamlit as st
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def main():
    """메인 함수"""
    try:
        from src.ui.components.component_demo_fixed import render_component_demo
        render_component_demo()
    except Exception as e:
        st.error(f"데모 페이지 로드 오류: {e}")
        st.write("프로젝트 구조를 확인해주세요.")

if __name__ == "__main__":
    main()


