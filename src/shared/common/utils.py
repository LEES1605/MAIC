# 공통 유틸리티 함수들
from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any, Optional

try:
    import streamlit as st
except Exception:
    st = None  # type: ignore


def errlog(msg: str, where: str = "", exc: Exception | None = None) -> None:
    """
    에러 로그 + 필요 시 Streamlit에 자세한 스택 표시.
    ErrorHandler 클래스를 사용하여 통합 에러 처리.
    
    Args:
        msg: 에러 메시지
        where: 에러 발생 위치
        exc: 예외 객체 (선택사항)
    """
    try:
        # ErrorHandler를 사용하여 에러 로깅
        from src.core.error_handler import get_error_handler, ErrorLevel
        
        source = where if where else "utils"
        if exc:
            get_error_handler().log_exception(exc, msg, source)
        else:
            get_error_handler().log_error(msg, source)
        
        # 기존 Streamlit UI 표시 유지
        try:
            if st is not None:
                with st.expander("자세한 오류 로그", expanded=False):
                    detail = ""
                    if exc:
                        try:
                            detail = "".join(
                                traceback.format_exception(type(exc), exc, exc.__traceback__)
                            )
                        except Exception:
                            detail = "traceback 사용 불가"
                    prefix = f"{where} " if where else ""
                    st.code(f"{prefix}{msg}\n{detail}")
        except Exception:
            pass
    except Exception:
        # 폴백: 기존 방식 사용
        try:
            prefix = f"{where} " if where else ""
            print(f"[ERR] {prefix}{msg}")
            if exc:
                traceback.print_exception(exc)
        except Exception:
            pass


# persist_dir_safe 함수는 src.services.index_actions._persist_dir_safe로 통합됨


def safe_import(module_name: str, fallback: Any = None) -> Any:
    """
    안전한 모듈 import.
    
    Args:
        module_name: import할 모듈 이름
        fallback: import 실패 시 반환할 기본값
    
    Returns:
        import된 모듈 또는 fallback 값
    """
    try:
        import importlib
        return importlib.import_module(module_name)
    except Exception:
        return fallback


def safe_getattr(obj: Any, attr_name: str, default: Any = None) -> Any:
    """
    안전한 속성 접근.
    
    Args:
        obj: 속성을 가져올 객체
        attr_name: 속성 이름
        default: 속성이 없을 때 반환할 기본값
    
    Returns:
        속성 값 또는 기본값
    """
    try:
        return getattr(obj, attr_name, default)
    except Exception:
        return default


__all__ = ["errlog", "persist_dir_safe", "safe_import", "safe_getattr"]
