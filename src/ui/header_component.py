"""
MAIC 헤더 컴포넌트 모듈

app.py에서 분리된 헤더 관련 로직을 담당합니다.
- 헤더 렌더링
- 상태 배지 표시
- 관리자 모드 헤더
"""

from pathlib import Path
from typing import Optional

from src.services.indexing_service import _persist_dir_safe


class HeaderComponent:
    """헤더 컴포넌트 클래스"""
    
    def __init__(self):
        self._st = None
        self._initialize_streamlit()
    
    def _initialize_streamlit(self):
        """Streamlit 초기화"""
        try:
            import streamlit as st
            self._st = st
        except ImportError:
            self._st = None
    
    def render(self) -> None:
        """
        H1: 상단 헤더에서 **최신 릴리스 복원 여부**를 3단계(🟩/🟨/🟧)로 항상 표기합니다.
        - 우선 tri-state 배지를 렌더(지연 import, 실패 시 무시)
        - 가능하면 외부 헤더(src.ui.header.render)도 이어서 렌더
        - 외부 헤더가 없을 때만 간단 폴백을 표시
        (H1 규칙은 MASTERPLAN vNext의 합의안을 준수합니다)
        """
        if self._st is None:
            return

        # 0) Tri-state readiness chip (관리자 모드에서만 표시)
        try:
            # 관리자 모드일 때만 readiness 헤더 표시
            if self._st.session_state.get("admin_mode", False):
                from src.ui.utils.readiness import render_readiness_header  # type: ignore
                render_readiness_header(compact=True)
        except Exception:
            # 배지 렌더 실패는 치명적이지 않으므로 조용히 계속 진행
            pass

        # 1) 외부 헤더가 정의되어 있으면 추가로 렌더
        try:
            from src.ui.header import render as _render_header
            _render_header()
            return
        except Exception:
            # 외부 헤더가 없으면 아래 폴백으로 이어감
            pass

        # 2) 폴백 헤더 (일관성 있는 상태 표시)
        self._render_fallback_header()
    
    def _render_fallback_header(self) -> None:
        """폴백 헤더 렌더링"""
        try:
            p = _persist_dir_safe()
            cj = p / "chunks.jsonl"
            rf = p / ".ready"
            
            # 실제 파일 상태 확인
            chunks_ready = cj.exists() and cj.stat().st_size > 0
            ready_file = rf.exists()
            
            # 세션 상태와 실제 파일 상태 일치 확인
            session_ready = self._st.session_state.get("_INDEX_LOCAL_READY", False)
            
            # 일관성 있는 상태 표시
            if chunks_ready and ready_file:
                badge = "🟢 준비완료"
                status_color = "green"
            elif chunks_ready or ready_file:
                badge = "🟡 부분준비"
                status_color = "orange"
            else:
                badge = "🔴 인덱스없음"
                status_color = "red"
                
            self._st.markdown(f"{badge} **LEES AI Teacher**")
            
            # 관리자 모드에서만 상세 정보 표시
            if self._st.session_state.get("admin_mode", False):
                with self._st.container():
                    self._st.caption("상태 정보")
                    self._st.json({
                        "chunks_ready": chunks_ready,
                        "ready_file": ready_file,
                        "session_ready": session_ready,
                        "persist_dir": str(p)
                    })
        except Exception as e:
            self._st.markdown("🔴 오류 **LEES AI Teacher**")
            if self._st.session_state.get("admin_mode", False):
                self._st.error(f"상태 확인 오류: {e}")
    
    def render_admin_header(self) -> None:
        """관리자 모드 헤더 렌더링"""
        if self._st is None:
            return
        
        try:
            # 관리자 모드 헤더를 맨 위로 이동
            with self._st.container():
                col1, col2 = self._st.columns([3, 1])
                
                with col1:
                    self._st.markdown("### 🔧 관리자 모드")
                
                with col2:
                    if self._st.button("로그아웃", key="admin_logout"):
                        self._st.session_state["admin_mode"] = False
                        self._st.session_state.pop("_admin_ok", None)
                        self._st.rerun()
                
                self._st.divider()
        except Exception as e:
            self._st.error(f"관리자 헤더 렌더링 오류: {e}")


# 전역 인스턴스
header_component = HeaderComponent()


# 편의 함수 (기존 app.py와의 호환성을 위해)
def _header() -> None:
    """헤더 렌더링"""
    header_component.render()
