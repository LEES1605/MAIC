"""
MAIC 관리자 패널 - 인덱싱 패널

관리자 모드에서 인덱싱 관련 기능을 제공합니다.
"""

from typing import Any, Dict, List, Optional


class AdminIndexingPanel:
    """관리자 인덱싱 패널"""
    
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
    
    def render_admin_panel(self) -> None:
        """관리자 패널 렌더링"""
        if self._st is None:
            return
        
        try:
            # 관리자 헤더
            self._render_admin_header()
            
            # 인덱싱 상태 표시
            self._render_indexing_status()
            
            # 관리 도구
            self._render_admin_tools()
            
            # 인덱싱 단계 표시
            self._render_indexing_steps()
            
            # 로그 표시
            self._render_logs()
            
        except Exception as e:
            self._st.error(f"관리자 패널 렌더링 오류: {e}")
    
    def _render_admin_header(self) -> None:
        """관리자 헤더 렌더링"""
        try:
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
    
    def _render_indexing_status(self) -> None:
        """인덱싱 상태 표시"""
        try:
            self._st.markdown("### 📊 인덱싱 상태")
            
            # 상태 정보 수집
            persist_dir = self._st.session_state.get("_PERSIST_DIR", "Unknown")
            local_ready = self._st.session_state.get("_INDEX_LOCAL_READY", False)
            is_latest = self._st.session_state.get("_INDEX_IS_LATEST", False)
            
            # 상태 표시
            if local_ready and is_latest:
                self._st.success("✅ 인덱스 준비 완료 (최신 버전)")
            elif local_ready:
                self._st.warning("⚠️ 인덱스 준비 완료 (이전 버전)")
            else:
                self._st.error("❌ 인덱스 준비 필요")
            
            # 상세 정보
            with self._st.expander("상세 정보"):
                self._st.json({
                    "persist_dir": str(persist_dir),
                    "local_ready": local_ready,
                    "is_latest": is_latest,
                    "latest_release_tag": self._st.session_state.get("_LATEST_RELEASE_TAG"),
                    "latest_release_id": self._st.session_state.get("_LATEST_RELEASE_ID")
                })
                
        except Exception as e:
            self._st.error(f"인덱싱 상태 렌더링 오류: {e}")
    
    def _render_admin_tools(self) -> None:
        """관리 도구 렌더링"""
        try:
            self._st.markdown("### 🛠️ 관리 도구")
            
            col1, col2, col3 = self._st.columns(3)
            
            with col1:
                if self._st.button("🔄 인덱스 복원", key="admin_restore_index"):
                    self._st.session_state["_FORCE_RESTORE"] = True
                    from src.services.restore_service import _boot_auto_restore_index
                    _boot_auto_restore_index()
                    self._st.success("복원 완료!")
                    self._st.rerun()
            
            with col2:
                if self._st.button("📊 통계 보기", key="admin_stats"):
                    self._render_statistics()
            
            with col3:
                if self._st.button("🧹 로그 정리", key="admin_clear_logs"):
                    self._st.session_state["indexing_logs"] = []
                    self._st.success("로그 정리 완료!")
                    self._st.rerun()
                    
        except Exception as e:
            self._st.error(f"관리 도구 렌더링 오류: {e}")
    
    def _render_statistics(self) -> None:
        """통계 표시"""
        try:
            self._st.markdown("#### 📈 통계 정보")
            
            # 기본 통계
            stats = {
                "총 로그 수": len(self._st.session_state.get("indexing_logs", [])),
                "인덱싱 단계 수": len(self._st.session_state.get("indexing_steps", {})),
                "세션 시작 시간": self._st.session_state.get("_APP_INITIALIZED", "Unknown"),
                "복원 시도 횟수": self._st.session_state.get("_RESTORE_ATTEMPTS", 0)
            }
            
            self._st.json(stats)
            
        except Exception as e:
            self._st.error(f"통계 렌더링 오류: {e}")
    
    def _render_indexing_steps(self) -> None:
        """인덱싱 단계 표시"""
        try:
            self._st.markdown("### 📋 인덱싱 단계")
            
            steps = self._st.session_state.get("indexing_steps", {})
            
            if not steps:
                self._st.info("인덱싱 단계 정보가 없습니다.")
                return
            
            for step_id, step_info in sorted(steps.items()):
                status = step_info.get("status", "unknown")
                message = step_info.get("message", "No message")
                
                if status == "ok":
                    self._st.success(f"✅ {message}")
                elif status == "run":
                    self._st.info(f"🔄 {message}")
                elif status == "wait":
                    self._st.warning(f"⏳ {message}")
                elif status == "err":
                    self._st.error(f"❌ {message}")
                else:
                    self._st.text(f"❓ {message}")
                    
        except Exception as e:
            self._st.error(f"인덱싱 단계 렌더링 오류: {e}")
    
    def _render_logs(self) -> None:
        """로그 표시"""
        try:
            self._st.markdown("### 📝 로그")
            
            logs = self._st.session_state.get("indexing_logs", [])
            
            if not logs:
                self._st.info("로그가 없습니다.")
                return
            
            # 최근 20개 로그만 표시
            recent_logs = logs[-20:]
            
            for log_entry in reversed(recent_logs):
                level = log_entry.get("level", "info")
                message = log_entry.get("message", "No message")
                timestamp = log_entry.get("timestamp", 0)
                
                # 타임스탬프 포맷팅
                import datetime
                dt = datetime.datetime.fromtimestamp(timestamp)
                time_str = dt.strftime("%H:%M:%S")
                
                if level == "error":
                    self._st.error(f"[{time_str}] {message}")
                elif level == "warn":
                    self._st.warning(f"[{time_str}] {message}")
                else:
                    self._st.text(f"[{time_str}] {message}")
                    
        except Exception as e:
            self._st.error(f"로그 렌더링 오류: {e}")


# 전역 인스턴스
admin_indexing_panel = AdminIndexingPanel()


# 편의 함수
def render_admin_panel() -> None:
    """관리자 패널 렌더링"""
    admin_indexing_panel.render_admin_panel()