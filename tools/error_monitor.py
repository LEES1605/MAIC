#!/usr/bin/env python3
"""
MAIC Error Monitoring Integration

이 모듈은 기존 코드에 에러 추적 기능을 쉽게 통합할 수 있도록
데코레이터와 컨텍스트 매니저를 제공합니다.
"""

import functools
import sys
import traceback
from typing import Any, Callable, Optional
from .error_tracker import ErrorTracker

class ErrorMonitor:
    """에러 모니터링 통합 클래스"""
    
    def __init__(self, project_root: str = "."):
        self.tracker = ErrorTracker(project_root)
    
    def monitor_function(self, max_retries: int = 3, auto_retry: bool = True):
        """함수 실행을 모니터링하는 데코레이터"""
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                retry_count = 0
                last_error = None
                
                while retry_count <= max_retries:
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        last_error = e
                        retry_count += 1
                        
                        # 에러 로그 기록
                        error_message = f"{func.__name__}: {str(e)}"
                        error_id = self.tracker.log_error(
                            error_message,
                            {
                                "function": func.__name__,
                                "args": str(args)[:100],
                                "kwargs": str(kwargs)[:100],
                                "retry_count": retry_count,
                                "traceback": traceback.format_exc()
                            }
                        )
                        
                        print(f"🚨 에러 발생 ({retry_count}/{max_retries}): {error_message}")
                        
                        if retry_count > max_retries:
                            print(f"❌ 최대 재시도 횟수 초과: {func.__name__}")
                            break
                        
                        if not auto_retry:
                            break
                        
                        print(f"🔄 재시도 중... ({retry_count}/{max_retries})")
                
                # 최종 실패 시 예외 재발생
                if last_error:
                    raise last_error
                    
            return wrapper
        return decorator
    
    def monitor_imports(self):
        """Import 에러를 모니터링하는 컨텍스트 매니저"""
        return ImportMonitor(self.tracker)
    
    def monitor_streamlit(self):
        """Streamlit 에러를 모니터링하는 컨텍스트 매니저"""
        return StreamlitMonitor(self.tracker)


class ImportMonitor:
    """Import 에러 모니터링 컨텍스트 매니저"""
    
    def __init__(self, tracker: ErrorTracker):
        self.tracker = tracker
        self.original_import = __builtins__.__import__
    
    def __enter__(self):
        # Import 함수를 래핑
        def wrapped_import(name, *args, **kwargs):
            try:
                return self.original_import(name, *args, **kwargs)
            except ImportError as e:
                error_message = f"ImportError: {str(e)}"
                self.tracker.log_error(
                    error_message,
                    {
                        "module_name": name,
                        "error_type": "ImportError"
                    }
                )
                raise
        
        __builtins__.__import__ = wrapped_import
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # 원래 import 함수 복원
        __builtins__.__import__ = self.original_import


class StreamlitMonitor:
    """Streamlit 에러 모니터링 컨텍스트 매니저"""
    
    def __init__(self, tracker: ErrorTracker):
        self.tracker = tracker
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            error_message = f"Streamlit Error: {str(exc_val)}"
            self.tracker.log_error(
                error_message,
                {
                    "error_type": "StreamlitError",
                    "exception_type": str(exc_type),
                    "traceback": traceback.format_exc()
                }
            )


# 전역 에러 모니터 인스턴스
error_monitor = ErrorMonitor()


# 편의 함수들
def monitor_function(max_retries: int = 3, auto_retry: bool = True):
    """함수 모니터링 데코레이터"""
    return error_monitor.monitor_function(max_retries, auto_retry)


def monitor_imports():
    """Import 모니터링 컨텍스트 매니저"""
    return error_monitor.monitor_imports()


def monitor_streamlit():
    """Streamlit 모니터링 컨텍스트 매니저"""
    return error_monitor.monitor_streamlit()


# 자동 에러 추적을 위한 예외 훅
def setup_global_error_tracking():
    """전역 에러 추적 설정"""
    def exception_handler(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # KeyboardInterrupt는 무시
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        # 에러 로그 기록
        error_message = f"Unhandled Exception: {exc_type.__name__}: {exc_value}"
        error_monitor.tracker.log_error(
            error_message,
            {
                "exception_type": str(exc_type),
                "traceback": traceback.format_exc(),
                "unhandled": True
            }
        )
        
        # 원래 예외 훅 호출
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
    
    sys.excepthook = exception_handler


# Streamlit 앱에서 사용할 수 있는 헬퍼 함수들
def setup_streamlit_error_tracking():
    """Streamlit 앱에서 에러 추적 설정"""
    try:
        import streamlit as st
        
        # Streamlit 에러 핸들러 설정
        def streamlit_error_handler(e):
            error_message = f"Streamlit Error: {str(e)}"
            error_monitor.tracker.log_error(
                error_message,
                {
                    "error_type": "StreamlitError",
                    "session_state": dict(st.session_state) if hasattr(st, 'session_state') else {}
                }
            )
        
        # Streamlit 컴포넌트 래핑
        original_button = st.button
        original_container = st.container
        
        def monitored_button(*args, **kwargs):
            try:
                return original_button(*args, **kwargs)
            except Exception as e:
                streamlit_error_handler(e)
                raise
        
        def monitored_container(*args, **kwargs):
            try:
                return original_container(*args, **kwargs)
            except Exception as e:
                streamlit_error_handler(e)
                raise
        
        # Streamlit 함수들 교체
        st.button = monitored_button
        st.container = monitored_container
        
        print("✅ Streamlit 에러 추적 설정 완료")
        
    except ImportError:
        print("⚠️ Streamlit이 설치되지 않았습니다.")


if __name__ == "__main__":
    # 전역 에러 추적 설정
    setup_global_error_tracking()
    setup_streamlit_error_tracking()
    
    print("🤖 MAIC 에러 추적 시스템 활성화됨")
    print("📝 3회 이상 반복되는 에러는 자동으로 DEVELOPMENT_HISTORY.md에 기록됩니다.")
