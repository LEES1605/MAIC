# Streamlit 네이티브 컴포넌트만 사용하는 관리자 패널
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import streamlit as st
except Exception:
    st = None

# 내부 함수들 import
try:
    from src.services.index_actions import run_admin_index_job
    from src.core.persist import effective_persist_dir
    from src.runtime.backup import make_index_backup_zip, upload_index_backup
    from src.runtime.ready import is_ready_text
except Exception:
    # 폴백
    def run_admin_index_job(params): pass
    def effective_persist_dir(): return Path.home() / ".maic" / "persist"
    def make_index_backup_zip(path): return None
    def upload_index_backup(zip_file, tag): return "업로드 완료"
    def is_ready_text(text): return "ready" in str(text).lower()

# 공통 유틸리티 함수 import
from src.common.utils import persist_dir_safe as _persist_dir_safe


def render_admin_indexing_panel() -> None:
    """관리자 모드 인덱싱 패널 - Streamlit 네이티브 컴포넌트만 사용"""
    if st is None:
        return
    
    # 시스템 상태 확인
    chunks_path = _persist_dir_safe() / "chunks.jsonl"
    chunks_ready_path = _persist_dir_safe() / "chunks.jsonl.ready"
    
    # 기본 상태값들
    local_ready = chunks_ready_path.exists()
    total_files_count = 0
    boot_scan_done = True
    has_new_files = False
    new_files_count = 0
    is_latest = True
    
    # 파일 수 확인
    try:
        if chunks_path.exists():
            with open(chunks_path, 'r', encoding='utf-8') as f:
                total_files_count = sum(1 for _ in f)
    except Exception:
        pass
    
    # 새 파일 확인 (간단한 로직)
    try:
        if chunks_ready_path.exists():
            with open(chunks_ready_path, 'r', encoding='utf-8') as f:
                ready_content = f.read().strip()
                if "new" in ready_content.lower():
                    has_new_files = True
                    new_files_count = 1  # 간단한 예시
    except Exception:
        pass
    
    # 메인 컨테이너
    with st.container():
        # 시스템 상태 섹션
        st.markdown("### 시스템 상태")
        
        # 상태 그리드 (3열)
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # 인덱스 상태
            st.markdown("**인덱스 상태**")
            if local_ready and is_latest:
                st.success("● 준비완료")
                st.caption("최신 릴리스")
            elif local_ready:
                st.warning("○ 로컬사용")
                st.caption("복원 필요")
            else:
                st.error("○ 복원필요")
                st.caption("인덱스 없음")
        
        with col2:
            # 스캔 상태
            st.markdown("**스캔 상태**")
            if boot_scan_done:
                if has_new_files:
                    st.info(f"○ 새파일 {new_files_count}개")
                    st.caption("업데이트 필요")
                else:
                    st.success("● 최신")
                    st.caption("동기화 완료")
            else:
                st.warning("◐ 스캔중")
                st.caption("처리 중")
        
        with col3:
            # 파일 수
            st.markdown("**파일 수**")
            st.metric("총 파일", f"{total_files_count}개")
        
        st.divider()
        
        # 주요 작업 섹션
        st.markdown("### 주요 작업")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔍 인덱싱 및 업로드", key="index_and_upload", use_container_width=True):
                # 인덱싱 작업 실행
                try:
                    with st.spinner("인덱싱 중..."):
                        result = run_admin_index_job({})
                        if result:
                            st.success("인덱싱 완료!")
                        else:
                            st.error("인덱싱 실패")
                except Exception as e:
                    st.error(f"오류: {e}")
        
        with col2:
            if st.button("📤 Release 업로드", key="release_upload", use_container_width=True):
                # 릴리스 업로드 작업
                try:
                    with st.spinner("업로드 중..."):
                        backup_path = make_index_backup_zip(_persist_dir_safe())
                        if backup_path:
                            result = upload_index_backup(backup_path, "manual-upload")
                            st.success(f"업로드 완료: {result}")
                        else:
                            st.error("백업 파일 생성 실패")
                except Exception as e:
                    st.error(f"오류: {e}")
        
        st.divider()
        
        # 관리 도구 섹션
        st.markdown("### 관리 도구")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 인덱스 복원", key="restore_index", use_container_width=True):
                st.info("인덱스 복원 기능은 개발 중입니다.")
        
        with col2:
            if st.button("📊 통계 보기", key="view_stats", use_container_width=True):
                st.info("통계 보기 기능은 개발 중입니다.")


def render_orchestrator_header() -> None:
    """오케스트레이터 헤더 (호환성을 위한 래퍼)"""
    render_admin_indexing_panel()


__all__ = ["render_admin_indexing_panel", "render_orchestrator_header"]
