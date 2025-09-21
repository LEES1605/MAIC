# =============================== [01] future import — START ===========================
from __future__ import annotations
# ================================ [01] future import — END ============================

# =============================== [02] module imports — START ==========================
from typing import Optional, Callable
import sys
# Streamlit이 없는 환경에서도 import 자체는 통과되어야 하므로 지연 참조만 사용합니다.
# ================================ [02] module imports — END ===========================

# ======================= [03] helper(resolver) — START ================================
def _resolve_app_attr(name: str) -> Optional[Callable[..., object]]:
    """
    __main__ 모듈(app.py로 실행된 현재 앱)에서 이름에 해당하는 호출체를 찾아 반환합니다.
    - 순환 import를 피하기 위해 'import app'을 사용하지 않고 __main__ 레퍼런스를 사용합니다.
    - 함수가 없거나 호출 불가하면 None.
    """
    try:
        app_mod = sys.modules.get("__main__")
        fn = getattr(app_mod, name, None)
        return fn if callable(fn) else None
    except Exception:
        return None
# ======================== [03] helper(resolver) — END =================================

# =================== [04] public API (admin panels) — START ===========================
def render_orchestrator_header() -> None:
    """🧪 인덱스 오케스트레이터 헤더 섹션을 렌더링합니다."""
    fn = _resolve_app_attr("_render_index_orchestrator_header")
    if fn:
        fn()


def render_prepared_scan_panel() -> None:
    """🔍 prepared 스캔 패널을 렌더링합니다."""
    fn = _resolve_app_attr("_render_admin_prepared_scan_panel")
    if fn:
        fn()


def render_index_panel() -> None:
    """🔧 관리자 인덱싱 패널(재인덱싱/ZIP 업로드 등)을 렌더링합니다."""
    fn = _resolve_app_attr("_render_admin_index_panel")
    if fn:
        fn()


def render_indexed_sources_panel() -> None:
    """📄 인덱싱된 파일 목록(읽기 전용) 패널을 렌더링합니다."""
    fn = _resolve_app_attr("_render_admin_indexed_sources_panel")
    if fn:
        fn()
# ==================== [04] public API (admin panels) — END ============================
