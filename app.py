"""
🚀 MAIC 애플리케이션

⚠️ AI 어시스턴트 규칙:
1. 이 파일은 수정하지 마세요
2. 새 파일은 src/ 디렉토리에만 생성하세요
3. legacy/ 디렉토리는 건드리지 마세요
4. 루트에 app.py 외의 파일을 생성하지 마세요

📁 올바른 구조:
- UI 컴포넌트: src/ui/
- 비즈니스 로직: src/application/
- 도메인 모델: src/domain/
- 인프라: src/infrastructure/
"""

import streamlit as st
import os
import sys
from pathlib import Path
import importlib

# Render 배포 호환성을 위한 포트 설정
PORT = int(os.environ.get('PORT', 8501))

def main() -> None:
    """MAIC 메인 애플리케이션"""
    st.set_page_config(
        page_title="MAIC - My AI Teacher",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # src 모듈 경로 추가 후, src의 렌더러를 호출
    sys.path.insert(0, str(Path(__file__).parent / "src"))
    try:
        module = importlib.import_module("ui.components.html_app")
        render_fn = getattr(module, "render_neumorphism_html_file")
        render_fn()
    except Exception as e:
        st.error(f"UI 렌더러 호출 실패: {e}")

if __name__ == "__main__":
    main()
