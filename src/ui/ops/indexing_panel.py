"""
MAIC 관리자 패널 - 심플하고 모던한 디자인

관리자 모드에서 필요한 핵심 기능만 제공합니다.
Linear 컴포넌트 시스템을 사용합니다.
"""

from typing import Any, Dict, List, Optional

# Linear 컴포넌트 import
try:
    from src.ui.components.linear_components import linear_button, linear_card, linear_alert
    from src.ui.components.linear_theme import apply_theme
except ImportError:
    # 폴백: 기본 Streamlit 사용
    linear_button = None  # type: ignore
    linear_card = None  # type: ignore
    linear_alert = None  # type: ignore
    apply_theme = None  # type: ignore


class AdminIndexingPanel:
    """관리자 인덱싱 패널 - 심플 버전"""
    
    def __init__(self):
        self._st = None
        self._initialize_streamlit()
    
    def _initialize_streamlit(self) -> None:
        """Streamlit 초기화"""
        try:
            import streamlit as st
            self._st = st
        except ImportError:
            self._st = None
    
    def render_admin_panel(self) -> None:
        """관리자 패널 렌더링 - Linear 컴포넌트 사용"""
        if self._st is None:
            return
        
        try:
            # Linear 테마 적용
            if apply_theme:
                apply_theme()
            
            # 심플한 관리자 패널 CSS
            self._inject_admin_css()
            
            # 시스템 상태
            self._render_system_status()
            
            # 인덱싱 단계 (펄스 표시)
            self._render_indexing_steps()
            
            # 핵심 관리 도구
            self._render_essential_tools()
            
        except Exception as e:
            error_msg = f"관리자 패널 렌더링 오류: {e}"
            if linear_alert:
                linear_alert(error_msg, variant="error")
            else:
                self._st.error(error_msg)
    
    def _inject_admin_css(self) -> None:
        """관리자 패널 CSS 주입"""
        css = """
        <style>
        .admin-panel {
            background: var(--linear-bg-primary);
            border-radius: 12px;
            padding: 1.5rem;
            margin: 1rem 0;
            border: 1px solid var(--linear-border);
        }
        
        .status-card {
            background: var(--linear-bg-secondary);
            border-radius: 8px;
            padding: 1rem;
            margin: 0.5rem 0;
            border: 1px solid var(--linear-border);
        }
        
        .status-indicator {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 500;
        }
        
        .status-ready {
            background: rgba(94, 106, 210, 0.1);
            color: var(--linear-brand);
            border: 1px solid rgba(94, 106, 210, 0.2);
        }
        
        .status-warning {
            background: rgba(252, 120, 64, 0.1);
            color: #fc7840;
            border: 1px solid rgba(252, 120, 64, 0.2);
        }
        
        .status-error {
            background: rgba(235, 87, 87, 0.1);
            color: #eb5757;
            border: 1px solid rgba(235, 87, 87, 0.2);
        }
        
        .step-pulse {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 0.75rem;
            animation: pulseDot 1.8s infinite;
        }
        
        .step-pulse.completed {
            background: var(--linear-brand);
            box-shadow: 0 0 0 0 rgba(94, 106, 210, 0.8);
            animation: pulseReady 2s infinite;
        }
        
        .step-pulse.running {
            background: #fc7840;
            box-shadow: 0 0 0 0 rgba(252, 120, 64, 0.55);
        }
        
        .step-pulse.failed {
            background: #eb5757;
            box-shadow: 0 0 0 0 rgba(235, 87, 87, 0.55);
        }
        
        @keyframes pulseReady {
            0%, 100% {
                box-shadow: 0 0 0 0 rgba(94, 106, 210, 0.8);
                transform: scale(1);
            }
            50% {
                box-shadow: 0 0 0 8px rgba(94, 106, 210, 0.2);
                transform: scale(1.02);
            }
        }
        
        @keyframes pulseDot {
            0% { box-shadow: 0 0 0 0 rgba(0,0,0,0.18); }
            70% { box-shadow: 0 0 0 16px rgba(0,0,0,0); }
            100% { box-shadow: 0 0 0 0 rgba(0,0,0,0); }
        }
        
        .step-item {
            display: flex;
            align-items: center;
            padding: 0.75rem 0;
            border-bottom: 1px solid var(--linear-border);
        }
        
        .step-item:last-child {
            border-bottom: none;
        }
        
        .step-name {
            font-weight: 500;
            color: var(--linear-text-primary);
            margin-right: 1rem;
            min-width: 120px;
        }
        
        .step-description {
            color: var(--linear-text-secondary);
            font-size: 0.875rem;
        }
        
        .tool-button {
            background: var(--linear-bg-secondary);
            border: 1px solid var(--linear-border);
            color: var(--linear-text-primary);
            border-radius: 8px;
            padding: 0.75rem 1rem;
            font-weight: 500;
            transition: all 0.2s ease;
        }
        
        .tool-button:hover {
            background: var(--linear-brand);
            color: white;
            border-color: var(--linear-brand);
        }
        </style>
        """
        
        self._st.markdown(css, unsafe_allow_html=True)
    
    def _render_system_status(self) -> None:
        """시스템 상태 표시"""
        try:
            self._st.markdown("### 시스템 상태")
            
            # 상태 정보 수집
            local_ready = self._st.session_state.get("_INDEX_LOCAL_READY", False)
            is_latest = self._st.session_state.get("_INDEX_IS_LATEST", False)
            
            # 상태 표시
            if local_ready and is_latest:
                status_class = "status-ready"
                status_text = "준비완료"
                status_icon = "●"
            elif local_ready:
                status_class = "status-warning"
                status_text = "업데이트 필요"
                status_icon = "●"
            else:
                status_class = "status-error"
                status_text = "복원 필요"
                status_icon = "●"
            
            self._st.markdown(f"""
            <div class="status-card">
                <div class="status-indicator {status_class}">
                    <span>{status_icon}</span>
                    <span>{status_text}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
                
        except Exception as e:
            self._st.error(f"시스템 상태 렌더링 오류: {e}")
    
    def _render_indexing_steps(self) -> None:
        """인덱싱 단계 표시 - 펄스 표시로 통일"""
        try:
            self._st.markdown("### 인덱싱 단계")
            
            # 단계별 상태
            steps = [
                {"name": "데이터 수집", "status": "completed", "description": "소스 파일 수집 완료"},
                {"name": "전처리", "status": "completed", "description": "텍스트 전처리 완료"},
                {"name": "인덱싱", "status": "completed", "description": "벡터 인덱싱 완료"},
                {"name": "검증", "status": "completed", "description": "인덱스 검증 완료"},
                {"name": "배포", "status": "completed", "description": "배포 완료"}
            ]
            
            for step in steps:
                pulse_class = f"step-pulse {step['status']}"
                self._st.markdown(f"""
                <div class="step-item">
                    <span class="{pulse_class}"></span>
                    <span class="step-name">{step['name']}</span>
                    <span class="step-description">{step['description']}</span>
                </div>
                """, unsafe_allow_html=True)
                
        except Exception as e:
            self._st.error(f"인덱싱 단계 렌더링 오류: {e}")
    
    def _render_essential_tools(self) -> None:
        """핵심 관리 도구만 표시 - Linear 컴포넌트 사용"""
        try:
            self._st.markdown("### 관리 도구")
            
            col1, col2 = self._st.columns(2)
            
            with col1:
                # 인덱스 복원 버튼
                if linear_button:
                    if linear_button("인덱스 복원", key="admin_restore_index", variant="primary", size="medium"):
                        self._handle_restore_index()
                else:
                    # 폴백: 기본 Streamlit 버튼
                    if self._st.button("인덱스 복원", key="admin_restore_index", help="최신 인덱스 복원"):
                        self._handle_restore_index()
            
            with col2:
                # 상태 새로고침 버튼
                if linear_button:
                    if linear_button("상태 새로고침", key="admin_refresh", variant="secondary", size="medium"):
                        self._handle_refresh_status()
                else:
                    # 폴백: 기본 Streamlit 버튼
                    if self._st.button("상태 새로고침", key="admin_refresh", help="시스템 상태 새로고침"):
                        self._handle_refresh_status()
                    
        except Exception as e:
            error_msg = f"관리 도구 렌더링 오류: {e}"
            if linear_alert:
                linear_alert(error_msg, variant="error")
            else:
                self._st.error(error_msg)
    
    def _handle_restore_index(self) -> None:
        """인덱스 복원 처리"""
        try:
            # 진행 상태 표시
            if linear_alert:
                linear_alert("인덱스 복원을 시작합니다...", variant="info")
            else:
                self._st.info("인덱스 복원을 시작합니다...")
            
            # 세션 상태 설정
            self._st.session_state["_FORCE_RESTORE"] = True
            
            # 복원 실행
            from src.services.restore_service import _boot_auto_restore_index
            _boot_auto_restore_index()
            
            # 성공 메시지
            if linear_alert:
                linear_alert("인덱스 복원이 완료되었습니다!", variant="success")
            else:
                self._st.success("인덱스 복원이 완료되었습니다!")
            
            # 페이지 새로고침
            self._st.rerun()
            
        except Exception as e:
            error_msg = f"인덱스 복원 실패: {e}"
            if linear_alert:
                linear_alert(error_msg, variant="error")
            else:
                self._st.error(error_msg)
    
    def _handle_refresh_status(self) -> None:
        """상태 새로고침 처리"""
        try:
            # 진행 상태 표시
            if linear_alert:
                linear_alert("상태를 새로고침합니다...", variant="info")
            else:
                self._st.info("상태를 새로고침합니다...")
            
            # 페이지 새로고침
            self._st.rerun()
            
        except Exception as e:
            error_msg = f"상태 새로고침 실패: {e}"
            if linear_alert:
                linear_alert(error_msg, variant="error")
            else:
                self._st.error(error_msg)


def render_admin_panel() -> None:
    """관리자 패널 렌더링 함수"""
    panel = AdminIndexingPanel()
    panel.render_admin_panel()