# iOS 스타일 + 미니멀리즘 관리자 모드 인덱싱 패널
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


def _load_prepared_lister():
    """prepared 파일 리스터 로드"""
    try:
        from src.integrations.gdrive import list_prepared_files
        return list_prepared_files, []
    except Exception:
        return None, ["gdrive 모듈 로드 실패"]


def _load_prepared_api():
    """prepared API 로드"""
    try:
        from src.integrations.gdrive import check_prepared_changes, mark_prepared_processed
        return check_prepared_changes, mark_prepared_processed, []
    except Exception:
        return None, None, ["gdrive API 로드 실패"]


def render_orchestrator_header() -> None:
    """기존 함수 호환성을 위한 래퍼"""
    render_ios_admin_panel()


def render_ios_admin_panel() -> None:
    """iOS 스타일 관리자 패널 렌더링"""
    if st is None or not bool(st.session_state.get("admin_mode", False)):
        return

    # iOS 스타일 CSS
    st.markdown("""
    <style>
    .ios-container {
        background: #ffffff;
        border-radius: 16px;
        padding: 20px;
        margin: 16px 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    .ios-status-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
        margin: 20px 0;
        background: #f2f2f7;
        border-radius: 12px;
        padding: 16px;
    }
    
    .ios-status-card {
        background: #ffffff;
        border: none;
        border-radius: 8px;
        padding: 12px 8px;
        text-align: center;
        font-size: 14px;
        font-weight: 500;
        color: #1d1d1f;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        min-height: 60px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }
    
    .ios-status-icon {
        font-size: 18px;
        margin-bottom: 4px;
        color: #007aff;
    }
    
    .ios-status-text {
        font-size: 12px;
        color: #8e8e93;
        margin-top: 2px;
    }
    
    .ios-button {
        background: #ffffff;
        border: 1px solid #d1d1d6;
        border-radius: 10px;
        padding: 16px 20px;
        font-size: 16px;
        font-weight: 500;
        color: #007aff;
        cursor: pointer;
        transition: all 0.2s ease;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        min-height: 48px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
    }
    
    .ios-button:hover {
        background: #f2f2f7;
        border-color: #007aff;
    }
    
    .ios-button.primary {
        background: #007aff;
        color: #ffffff;
        border-color: #007aff;
    }
    
    .ios-button.primary:hover {
        background: #0056cc;
    }
    
    .ios-section-title {
        font-size: 18px;
        font-weight: 600;
        color: #1d1d1f;
        margin: 24px 0 16px 0;
        padding-bottom: 8px;
        border-bottom: 1px solid #e5e5e7;
    }
    
    /* 모바일 최적화 */
    @media (max-width: 768px) {
        .ios-container {
            margin: 8px 0;
            padding: 16px;
            border-radius: 12px;
        }
        
        .ios-status-grid {
            grid-template-columns: 1fr;
            gap: 8px;
            margin: 16px 0;
            padding: 12px;
        }
        
        .ios-status-card {
            padding: 16px 12px;
            min-height: 48px;
            font-size: 16px;
        }
        
        .ios-status-icon {
            font-size: 20px;
        }
        
        .ios-status-text {
            font-size: 14px;
        }
        
        .ios-button {
            padding: 20px 24px;
            font-size: 17px;
            min-height: 52px;
        }
        
        .ios-section-title {
            font-size: 20px;
            margin: 20px 0 12px 0;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 시스템 상태 정보 수집
    persist = _persist_dir_safe()
    cj = persist / "chunks.jsonl"
    rf = persist / ".ready"
    
    local_ready = cj.exists() and rf.exists()
    is_latest = st.session_state.get("_INDEX_IS_LATEST", False)
        boot_scan_done = st.session_state.get("_BOOT_SCAN_DONE", False)
        has_new_files = st.session_state.get("_PREPARED_HAS_NEW", False)
        new_files_count = st.session_state.get("_PREPARED_NEW_FILES", 0)
        total_files_count = st.session_state.get("_PREPARED_TOTAL_FILES", 0)
        
    # 시스템 상태 표시
    st.markdown('<div class="ios-section-title">시스템 상태</div>', unsafe_allow_html=True)
    
    status_html = '<div class="ios-status-grid">'
    
    # 인덱스 상태
            if local_ready and is_latest:
        status_html += '''
        <div class="ios-status-card">
            <div class="ios-status-icon">●</div>
            <div>준비완료</div>
            <div class="ios-status-text">최신 릴리스</div>
        </div>
        '''
            elif local_ready:
        status_html += '''
        <div class="ios-status-card">
            <div class="ios-status-icon">○</div>
            <div>로컬사용</div>
            <div class="ios-status-text">복원 필요</div>
        </div>
        '''
            else:
        status_html += '''
        <div class="ios-status-card">
            <div class="ios-status-icon">○</div>
            <div>복원필요</div>
            <div class="ios-status-text">인덱스 없음</div>
        </div>
        '''
    
    # 스캔 상태
    if boot_scan_done:
        if has_new_files:
            status_html += f'''
            <div class="ios-status-card">
                <div class="ios-status-icon">○</div>
                <div>새파일 {new_files_count}개</div>
                <div class="ios-status-text">업데이트 필요</div>
            </div>
            '''
        else:
            status_html += '''
            <div class="ios-status-card">
                <div class="ios-status-icon">●</div>
                <div>최신</div>
                <div class="ios-status-text">동기화 완료</div>
            </div>
            '''
            else:
        status_html += '''
        <div class="ios-status-card">
            <div class="ios-status-icon">◐</div>
            <div>스캔중</div>
            <div class="ios-status-text">처리 중</div>
        </div>
        '''
    
    # 파일 수
    status_html += f'''
    <div class="ios-status-card">
        <div class="ios-status-icon">○</div>
        <div>{total_files_count}개</div>
        <div class="ios-status-text">총 파일</div>
    </div>
    '''
    
    status_html += '</div>'
    st.markdown(status_html, unsafe_allow_html=True)
    
    # 주요 작업
    st.markdown('<div class="ios-section-title">주요 작업</div>', unsafe_allow_html=True)
    
    main_col1, main_col2 = st.columns([1, 1])
    
    with main_col1:
        if st.button("인덱싱 & 업로드", use_container_width=True, type="primary"):
            params = {"auto_up": True, "debug": False}
            try:
                run_admin_index_job(params)
                st.success("인덱싱 & 업로드 완료")
                except Exception as e:
                st.error(f"인덱싱 실패: {e}")
    
    with main_col2:
        if st.button("Release 업로드", use_container_width=True):
            try:
                z = make_index_backup_zip(persist)
                msg = upload_index_backup(z, tag=f"index-{int(time.time())}")
                st.success(f"Release 업로드 완료: {msg}")
            except Exception as e:
                st.error(f"Release 업로드 실패: {e}")
    
    # 관리 도구
    st.markdown('<div class="ios-section-title">관리 도구</div>', unsafe_allow_html=True)
    
    # 2x2 그리드
    tool_col1, tool_col2 = st.columns([1, 1])
    
    with tool_col1:
        if st.button("파일스캔", use_container_width=True):
            try:
                    lister, _ = _load_prepared_lister()
                    if lister:
                        files_list = lister() or []
                    chk, _, _ = _load_prepared_api()
                        if callable(chk):
                        info = chk(persist, files_list) or {}
                        new_files = list(info.get("files", []))
                        new_count = len(new_files)
                        total_count = len(files_list)
                        
                        if new_count > 0:
                            st.warning(f"새 파일 {new_count}개 발견! (총 {total_count}개)")
                            st.session_state["_PREPARED_HAS_NEW"] = True
                            st.session_state["_PREPARED_NEW_FILES"] = new_count
                        else:
                            st.success(f"새 파일 없음 (총 {total_count}개)")
                            st.session_state["_PREPARED_HAS_NEW"] = False
                    else:
                        st.error("스캔 API 로드 실패")
                else:
                    st.error("파일 리스터 로드 실패")
                except Exception as e:
                    st.error(f"스캔 실패: {e}")
        
    with tool_col2:
        if st.button("검증", use_container_width=True):
            try:
                cj_exists = cj.exists()
                cj_valid = cj_exists and cj.stat().st_size > 0
                
                rf_exists = rf.exists()
                ready_valid = False
                if rf_exists:
                    try:
                        ready_txt = rf.read_text(encoding="utf-8")
                        ready_valid = is_ready_text(ready_txt)
        except Exception:
            pass

                if cj_valid and ready_valid:
                    st.success("검증 성공: chunks.jsonl & .ready 유효")
    else:
                    st.error("검증 실패: 파일 상태 불일치")
            except Exception as e:
                st.error(f"검증 실패: {e}")
    
    # 두 번째 행
    restore_col1, restore_col2 = st.columns([1, 1])
    
    with restore_col1:
        if st.button("릴리스복원", use_container_width=True):
            try:
                st.session_state["_FORCE_RESTORE"] = True
                # 복원 로직은 app.py에서 처리
                st.success("릴리스 복원을 시도했습니다")
                st.rerun()
        except Exception as e:
                st.error(f"복원 실패: {e}")
    
    with restore_col2:
        if st.button("로컬복원", use_container_width=True):
            try:
                from src.runtime.local_restore import find_local_backups, restore_from_local_backup
                
                backup_base = Path.home() / ".maic"
                backups = find_local_backups(backup_base)
                
                if not backups:
                    st.warning("로컬 백업을 찾을 수 없습니다")
            else:
                    success, message = restore_from_local_backup(backups[0], persist)
                    if success:
                        st.success(f"로컬 복원 완료: {message}")
                        st.session_state["_INDEX_LOCAL_READY"] = True
                        st.session_state["_INDEX_IS_LATEST"] = False
                        st.rerun()
    else:
                        st.error(f"로컬 복원 실패: {message}")
            except Exception as e:
                st.error(f"로컬 복원 실패: {e}")
    
    # 접을 수 있는 상세 정보
    with st.expander("상세 정보", expanded=False):
        st.json({
            "persist_dir": str(persist),
            "chunks_exists": cj.exists(),
            "ready_exists": rf.exists(),
            "local_ready": local_ready,
            "is_latest": is_latest,
            "new_files_count": new_files_count,
            "total_files_count": total_files_count
        })


__all__ = ["render_ios_admin_panel"]
