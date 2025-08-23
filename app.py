# ===== [01] APP BOOT & ENV ===================================================
from __future__ import annotations

import os
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
os.environ["STREAMLIT_RUN_ON_SAVE"] = "false"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["STREAMLIT_SERVER_ENABLE_WEBSOCKET_COMPRESSION"] = "false"

# ===== [02] IMPORTS ==========================================================
from pathlib import Path
from typing import Any, Optional, Callable, List, Dict, Tuple

import re
import time
import importlib
import streamlit as st

# RAG 엔진이 없어도 앱이 죽지 않게 try/except로 감쌈
try:
    from src.rag_engine import get_or_build_index, LocalIndexMissing
except Exception:
    get_or_build_index = None  # type: ignore
    class LocalIndexMissing(Exception):  # 안전 가드
        ...

# 인덱스 빌더/사전점검 (PREPARED→청크→리포트→ZIP 업로드)
precheck_build_needed = None  # type: ignore
build_index_with_checkpoint = None  # type: ignore
_import_errors: List[str] = []

def _bind_precheck(mod) -> Optional[Callable[..., Any]]:
    """
    index_build가 어떤 이름으로 내보내든(precheck_build_needed | quick_precheck)
    여기서 하나로 바인딩한다.
    """
    fn = getattr(mod, "precheck_build_needed", None) or getattr(mod, "quick_precheck", None)
    if fn is None:
        return None

    # 시그니처가 다를 수 있어, 인자 미스매치면 무인자 호출로 재시도
    def _call(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except TypeError:
            return fn()
    return _call

# 1차 경로: src.rag.index_build
try:
    _mod = importlib.import_module("src.rag.index_build")
    precheck_build_needed = _bind_precheck(_mod)
    build_index_with_checkpoint = getattr(_mod, "build_index_with_checkpoint", None)
except Exception as e:
    _import_errors.append(f"[src.rag.index_build] {type(e).__name__}: {e}")

# 2차 경로: rag.index_build (프로젝트 루트가 src일 때)
if precheck_build_needed is None or build_index_with_checkpoint is None:
    try:
        _mod2 = importlib.import_module("rag.index_build")
        precheck_build_needed = precheck_build_needed or _bind_precheck(_mod2)
        build_index_with_checkpoint = build_index_with_checkpoint or getattr(_mod2, "build_index_with_checkpoint", None)
    except Exception as e:
        _import_errors.append(f"[rag.index_build] {type(e).__name__}: {e}")

# 임포트 실패 시 원인 안내
if precheck_build_needed is None or build_index_with_checkpoint is None:
    st.warning(
        "사전점검/빌더 임포트에 실패했습니다.\n\n"
        + "\n".join(f"• {msg}" for msg in _import_errors)
        + "\n\n확인하세요:\n"
        + "1) 파일 존재: src/rag/index_build.py\n"
        + "2) 패키지 마커: src/__init__.py, src/rag/__init__.py\n"
        + "3) 함수 이름: precheck_build_needed **또는** quick_precheck 중 하나가 있어야 합니다.\n"
        + "4) import 철자: index_build(언더스코어), index.build(점) 아님"
    )

# ===== [03] SESSION & HELPERS ================================================
st.set_page_config(page_title="AI Teacher (Clean)", layout="wide")

# 인덱스 상태
if "rag_index" not in st.session_state:
    st.session_state["rag_index"] = None

# 모드/제출 플래그 (언어는 한국어 고정이므로 상태 저장하지 않음)
if "mode" not in st.session_state:
    st.session_state["mode"] = "Grammar"  # Grammar | Sentence | Passage
if "qa_submitted" not in st.session_state:
    st.session_state["qa_submitted"] = False

def _is_attached_session() -> bool:
    """세션에 실제로 두뇌가 붙었는지(여러 키 중 하나라도 있으면 True)."""
    ss = st.session_state
    return bool(
        ss.get("brain_attached") or
        ss.get("rag_index") or
        ss.get("retriever") or
        ss.get("vectorstore") or
        ss.get("rag")
    )

def _has_local_index_files() -> bool:
    """로컬 PERSIST_DIR 안에 .ready 또는 chunks.jsonl 이 있는지 신호만 확인."""
    import importlib
    from pathlib import Path as _P
    try:
        _mod = importlib.import_module("src.rag.index_build")
        _PERSIST_DIR = getattr(_mod, "PERSIST_DIR", _P.home() / ".maic" / "persist")
    except Exception:
        _PERSIST_DIR = _P.home() / ".maic" / "persist"
    chunks_ok = (_PERSIST_DIR / "chunks.jsonl").exists()
    ready_ok  = (_PERSIST_DIR / ".ready").exists()
    return bool(chunks_ok or ready_ok)

def get_index_status() -> str:
    """
    단일 기준의 인덱스 상태:
      - 'ready'   : 세션에 부착 완료
      - 'pending' : 세션 미부착, 로컬 파일 신호(.ready/chunks.jsonl)만 존재
      - 'missing' : 로컬 신호 없음
    """
    if _is_attached_session():
        return "ready"
    if _has_local_index_files():
        return "pending"
    return "missing"

def _attach_from_local() -> bool:
    if get_or_build_index is None:
        return False
    try:
        idx = get_or_build_index()
        st.session_state["rag_index"] = idx
        return True
    except LocalIndexMissing:
        return False
    except Exception:
        return False

def _auto_attach_or_restore_silently() -> bool:
    return _attach_from_local()


# ===== [04] HEADER ==========================================
def render_header():
    """
    헤더 UI는 [07] MAIN의 _render_title_with_status()가 전적으로 담당합니다.
    여기서는 중복 렌더링을 막기 위해 아무 것도 출력하지 않습니다.
    (요구사항: 'Index status: ...' 텍스트 및 중복 배지 제거)
    """
    return
# ===== [04] END =============================================

# ===== [04A] MODE & ADMIN BUTTON (콜백 제거: 즉시 갱신용 rerun) ================
import os as _os
import streamlit as st

# ── [04A-1] PIN 가져오기 ------------------------------------------------------
def _get_admin_pin() -> str:
    try:
        pin = st.secrets.get("ADMIN_PIN", None)  # type: ignore[attr-defined]
    except Exception:
        pin = None
    return str(pin or _os.environ.get("ADMIN_PIN") or "0000")
# ===== [04A-1] END ============================================================


# ── [04A-2] 세션키 초기화 ------------------------------------------------------
if "is_admin" not in st.session_state:
    st.session_state["is_admin"] = False
if "_admin_auth_open" not in st.session_state:
    st.session_state["_admin_auth_open"] = False
# ===== [04A-2] END ============================================================


# ── [04A-3] 상단 우측 관리자 버튼 & 인증 패널 (콜백 미사용) ----------------------
with st.container():
    _, right = st.columns([0.7, 0.3])
    with right:
        btn_slot = st.empty()

        if st.session_state["is_admin"]:
            # 관리자 모드일 때: 종료 버튼이 바로 보여야 함
            if btn_slot.button("🔓 관리자 종료", key="btn_close_admin", use_container_width=True):
                st.session_state["is_admin"] = False
                st.session_state["_admin_auth_open"] = False
                try: st.toast("관리자 모드 해제됨")
                except Exception: pass
                st.rerun()  # ← 콜백이 아닌 본문에서 rerun: 즉시 라벨 갱신
        else:
            # 학생 모드일 때: 관리자 버튼
            if btn_slot.button("🔒 관리자", key="btn_open_admin", use_container_width=True):
                st.session_state["_admin_auth_open"] = True
                st.rerun()  # 인증 패널을 즉시 표시

        # 인증 패널: 열림 상태이면 표시
        if st.session_state["_admin_auth_open"] and not st.session_state["is_admin"]:
            with st.container(border=True):
                st.markdown("**관리자 PIN 입력**")
                with st.form("admin_login_form", clear_on_submit=True, border=False):
                    pin_try = st.text_input("PIN", type="password")
                    c1, c2 = st.columns(2)
                    with c1:
                        ok = st.form_submit_button("입장")
                    with c2:
                        cancel = st.form_submit_button("취소")

                if cancel:
                    st.session_state["_admin_auth_open"] = False
                    st.rerun()
                if ok:
                    if pin_try == _get_admin_pin():
                        st.session_state["is_admin"] = True
                        st.session_state["_admin_auth_open"] = False
                        try: st.toast("관리자 모드 진입 ✅")
                        except Exception: pass
                        st.rerun()  # 입장 직후 즉시 라벨 "관리자 종료"로
                    else:
                        st.error("PIN이 올바르지 않습니다.")
# ===== [04A-3] END ============================================================


# ── [04A-4] 역할 캡션 ---------------------------------------------------------
if st.session_state.get("is_admin", False):
    st.caption("역할: **관리자** — 상단 버튼으로 종료 가능")
else:
    st.caption("역할: **학생** — 질문/답변에 집중할 수 있게 단순화했어요.")

st.divider()
# ===== [04A] END =============================================================
# ===== [04B] 관리자 설정 — 이유문법 ON/OFF (영속 저장 포함) ====================
import json as _json
from pathlib import Path as _Path
import streamlit as st

# ── [04B-1] 설정 파일 경로/기본값 ---------------------------------------------
def _config_path() -> _Path:
    base = _Path.home() / ".maic"
    try: base.mkdir(parents=True, exist_ok=True)
    except Exception: pass
    return base / "config.json"

_DEFAULT_CFG = {
    "reason_grammar_enabled": False,  # 기본값: OFF로 출시
}

# ── [04B-2] 설정 로드/저장 -----------------------------------------------------
def _load_cfg() -> dict:
    cfg_file = _config_path()
    if not cfg_file.exists():
        return dict(_DEFAULT_CFG)
    try:
        data = _json.loads(cfg_file.read_text(encoding="utf-8"))
        # 누락 키 보정
        for k, v in _DEFAULT_CFG.items():
            data.setdefault(k, v)
        return data
    except Exception:
        return dict(_DEFAULT_CFG)

def _save_cfg(data: dict) -> None:
    cfg_file = _config_path()
    try:
        cfg_file.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        st.warning(f"설정 저장 실패: {type(e).__name__}: {e}")

# ── [04B-3] 세션과 전역 접근자 -------------------------------------------------
def _cfg_get(key: str, default=None):
    st.session_state.setdefault("_app_cfg_cache", _load_cfg())
    return st.session_state["_app_cfg_cache"].get(key, default)

def _cfg_set(key: str, value) -> None:
    st.session_state.setdefault("_app_cfg_cache", _load_cfg())
    st.session_state["_app_cfg_cache"][key] = value
    _save_cfg(st.session_state["_app_cfg_cache"])

def is_reason_grammar_enabled() -> bool:
    """앱 어디서나 사용할 수 있는 읽기용 헬퍼"""
    return bool(_cfg_get("reason_grammar_enabled", False))

# ── [04B-4] 관리자 UI(체크박스) ------------------------------------------------
def render_admin_settings_panel():
    """관리자용 설정 카드: 이유문법 ON/OFF 토글"""
    if not st.session_state.get("is_admin", False):
        return  # 학생 화면엔 숨김

    with st.container(border=True):
        st.subheader("관리자 설정")
        st.caption("이유문법 기능은 자료 정리 후 단계적으로 활성화합니다. 출시 기본은 OFF입니다.")

        current = is_reason_grammar_enabled()
        new_val = st.checkbox("이유문법 설명 사용(실험적)", value=current, key="cfg_reason_grammar_checkbox")

        # 콜백 대신 본문에서 직접 감지 → 즉시 저장/재렌더
        if new_val != current:
            _cfg_set("reason_grammar_enabled", bool(new_val))
            try: st.toast("설정을 저장했어요. 화면을 새로고침합니다.")
            except Exception: pass
            st.rerun()

# ── [04B-5] 메인 플로우에 주입 -------------------------------------------------
# main() 안에서, 관리자 화면 렌더 직전에 아래 한 줄만 호출해 주세요.
#   render_admin_settings_panel()
#
# 예) [07] main()의 (H) 화면 섹션 근처:
#   if is_admin:
#       render_admin_settings_panel()   # ← 이 줄 추가
#       render_brain_prep_main()
#       st.divider()
#       render_tag_diagnostics()
#       st.divider()
#       render_simple_qa()
# ===== [04B] END ==============================================================


# ===== [05A] BRAIN PREP MAIN =======================================
def render_brain_prep_main():
    """
    관리자 준비 패널(다이어트 버전)
    - ready 상태: UI 완전 숨김(아무 것도 렌더하지 않음)
    - missing/pending: 최소 안내만, 버튼 없음
    - Advanced(고급)에서만 수동 조치(강제 복구 / 다시 최적화 / 품질 리포트 재생성)
    """
    import importlib
    from pathlib import Path
    import streamlit as st

    # 현재 인덱스 상태: 'ready' | 'pending' | 'missing'
    try:
        status = get_index_status()
    except Exception:
        status = "missing"

    # 1) ready면 패널 자체를 숨김(중복 UI 제거)
    if status == "ready":
        return

    # 2) 최소 안내(버튼 없음)
    with st.container(border=True):
        if status == "missing":
            st.warning(
                "로컬 인덱스가 없습니다. 상단 플로우에서 **백업 복구→자동 연결**을 먼저 시도합니다.\n"
                "필요 시 아래 **고급(Advanced)**에서 수동으로 복구/다시 최적화를 실행할 수 있습니다."
            )
        else:  # 'pending'
            st.info(
                "로컬 인덱스 신호(.ready/chunks.jsonl)는 있으나 세션 미연결 상태입니다.\n"
                "잠시 후 자동 연결되며, 필요 시 **고급(Advanced)**에서 수동 조치가 가능합니다."
            )

    # 3) Advanced(수동 조치 전용)
    with st.expander("고급(Advanced) — 문제가 있을 때만 사용", expanded=False):
        st.caption("아래 동작은 관리자 전용 수동 조치입니다.")

        # a) 최신 백업에서 강제 복구 → 연결
        if st.button("📦 최신 백업에서 강제 복구 → 연결", key="adv_force_restore"):
            try:
                mod = importlib.import_module("src.rag.index_build")
                restore_fn = getattr(mod, "restore_latest_backup_to_local", None)
                if not callable(restore_fn):
                    st.error("복구 함수를 찾지 못했습니다. (restore_latest_backup_to_local)")
                else:
                    with st.status("백업에서 로컬로 복구 중…", state="running") as s:
                        res = restore_fn()
                        if not (res and res.get("ok")):
                            s.update(label="복구 실패 ❌", state="error")
                            st.error(f"복구 실패: {res.get('error') if res else 'unknown'}")
                        else:
                            s.update(label="복구 완료 ✅", state="complete")
                            with st.status("두뇌 연결 중…", state="running") as s2:
                                ok = _auto_attach_or_restore_silently()
                                if ok:
                                    s2.update(label="두뇌 연결 완료 ✅", state="complete")
                                    st.rerun()
                                else:
                                    s2.update(label="두뇌 연결 실패 ❌", state="error")
            except Exception as e:
                st.error(f"강제 복구 중 오류: {type(e).__name__}: {e}")

        # b) 다시 최적화 실행 → 백업 업로드 → 복구 → 연결
        if st.button("🛠 다시 최적화 실행 → 백업 업로드 → 복구 → 연결", key="adv_rebuild_pipeline"):
            try:
                try:
                    mod = importlib.import_module("src.rag.index_build")
                except Exception as e:
                    st.error(f"인덱스 빌더 모듈 임포트 실패: {type(e).__name__}: {e}")
                    mod = None

                build_fn = getattr(mod, "build_index_with_checkpoint", None) if mod else None
                upload_zip_fn = getattr(mod, "_make_and_upload_backup_zip", None) if mod else None
                persist_dir = getattr(mod, "PERSIST_DIR", Path.home() / ".maic" / "persist") if mod else (Path.home() / ".maic" / "persist")
                restore_fn = getattr(mod, "restore_latest_backup_to_local", None) if mod else None

                if not callable(build_fn):
                    st.error("인덱스 빌더 함수를 찾지 못했습니다. (build_index_with_checkpoint)")
                else:
                    prog = st.progress(0); log = st.empty()
                    def _pct(v: int, msg: str | None = None):
                        try:
                            prog.progress(max(0, min(int(v), 100)))
                        except Exception:
                            pass
                        if msg: log.info(str(msg))
                    def _msg(s: str): log.write(f"• {s}")

                    with st.status("다시 최적화 실행 중…", state="running") as s:
                        res = build_fn(
                            update_pct=_pct, update_msg=_msg,
                            gdrive_folder_id="", gcp_creds={},
                            persist_dir=str(persist_dir), remote_manifest={}
                        )
                        prog.progress(100)
                        s.update(label="다시 최적화 완료 ✅", state="complete")
                    st.json(res)

                    # ZIP 업로드(있으면)
                    try:
                        if callable(upload_zip_fn):
                            _ = upload_zip_fn(None, None)
                    except Exception:
                        pass

                    # 최신 ZIP으로 복구 후 연결
                    if callable(restore_fn):
                        with st.status("백업에서 로컬로 복구 중…", state="running") as s2:
                            rr = restore_fn()
                            if not (rr and rr.get("ok")):
                                s2.update(label="복구 실패 ❌", state="error")
                                st.error(f"복구 실패: {rr.get('error') if rr else 'unknown'}")
                            else:
                                s2.update(label="복구 완료 ✅", state="complete")

                    with st.status("두뇌 연결 중…", state="running") as s3:
                        ok = _auto_attach_or_restore_silently()
                        if ok:
                            s3.update(label="두뇌 연결 완료 ✅", state="complete")
                            st.rerun()
                        else:
                            s3.update(label="두뇌 연결 실패 ❌", state="error")
            except Exception as e:
                st.error(f"재최적화 파이프라인 중 오류: {type(e).__name__}: {e}")

        # c) 품질 리포트 다시 생성(강제)
        if st.button("📊 품질 리포트 다시 생성(강제)", key="adv_regen_quality"):
            try:
                mod = importlib.import_module("src.rag.index_build")
                force_fn = getattr(mod, "_quality_report", None)
                auto_fn  = getattr(mod, "autorun_quality_scan_if_stale", None)
                if callable(force_fn):
                    with st.status("품질 리포트 생성 중…", state="running") as s:
                        r = force_fn(None, extra_counts=None, top_n=20)
                        s.update(label="생성 완료 ✅", state="complete")
                        st.success(f"저장 경로: {r.get('path', '~/.maic/quality_report.json')}")
                elif callable(auto_fn):
                    r = auto_fn(top_n=20)
                    if r.get("ok") and not r.get("skipped"):
                        st.success("품질 리포트 갱신 완료 ✅")
                    elif r.get("skipped"):
                        st.info("이미 최신입니다. (스킵됨)")
                    else:
                        st.error("품질 리포트 갱신 실패")
                else:
                    st.error("품질 리포트 함수를 찾지 못했습니다.")
            except Exception as e:
                st.error(f"품질 리포트 생성 중 오류: {type(e).__name__}: {e}")
# ===== [05A] END ===========================================


# ===== [05B] TAG DIAGNOSTICS (NEW) ==========================================
def render_tag_diagnostics():
    """
    태그/인덱스 진단 패널
    - quality_report.json 유무
    - 로컬 ZIP: backup_*.zip + restored_*.zip (최신 5개)
    - 드라이브 ZIP: backup_zip 폴더의 ZIP (최신 5개)
    - 로컬 인덱스 파일(.ready, chunks.jsonl) 표시
    """
    import importlib, traceback
    from pathlib import Path
    from datetime import datetime
    import streamlit as st

    # 기본 경로
    PERSIST_DIR = Path.home() / ".maic" / "persist"
    BACKUP_DIR = Path.home() / ".maic" / "backup"
    QUALITY_REPORT_PATH = Path.home() / ".maic" / "quality_report.json"

    # src.rag.index_build 값 우선
    try:
        _m = importlib.import_module("src.rag.index_build")
        PERSIST_DIR = getattr(_m, "PERSIST_DIR", PERSIST_DIR)
        BACKUP_DIR = getattr(_m, "BACKUP_DIR", BACKUP_DIR)
        QUALITY_REPORT_PATH = getattr(_m, "QUALITY_REPORT_PATH", QUALITY_REPORT_PATH)
    except Exception:
        _m = None

    def _fmt_size(n):
        try:
            n = int(n)
        except Exception:
            return "-"
        units = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        f = float(n)
        while f >= 1024 and i < len(units) - 1:
            f /= 1024.0
            i += 1
        if i == 0:
            return f"{int(f)} {units[i]}"
        return f"{f:.1f} {units[i]}"

    def _fmt_ts(ts):
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "-"

    st.subheader("진단(간단)", anchor=False)

    # ── 품질 리포트 존재 ─────────────────────────────────────────────────────────
    qr_exists = QUALITY_REPORT_PATH.exists()
    qr_badge = "✅ 있음" if qr_exists else "❌ 없음"
    st.markdown(f"- **품질 리포트(quality_report.json)**: {qr_badge}  (`{QUALITY_REPORT_PATH.as_posix()}`)")

    # ── 로컬 ZIP 목록: backup_* + restored_* (최신 5) ───────────────────────────
    local_rows = []
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        zips = list(BACKUP_DIR.glob("backup_*.zip")) + list(BACKUP_DIR.glob("restored_*.zip"))
        zips.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for p in zips[:5]:
            stt = p.stat()
            local_rows.append({"파일명": p.name, "크기": _fmt_size(stt.st_size), "수정시각": _fmt_ts(stt.st_mtime)})
    except Exception:
        pass

    # ── 드라이브 ZIP 목록(top5) ─────────────────────────────────────────────────
    drive_rows = []
    drive_msg = None
    try:
        _drive_service = getattr(_m, "_drive_service", None) if _m else None
        _pick_backup_folder_id = getattr(_m, "_pick_backup_folder_id", None) if _m else None
        svc = _drive_service() if callable(_drive_service) else None
        fid = _pick_backup_folder_id(svc) if callable(_pick_backup_folder_id) else None
        if svc and fid:
            resp = svc.files().list(
                q=f"'{fid}' in parents and trashed=false and mimeType!='application/vnd.google-apps.folder'",
                fields="files(id,name,modifiedTime,size,mimeType)",
                includeItemsFromAllDrives=True, supportsAllDrives=True, corpora="allDrives", pageSize=1000
            ).execute()
            files = [f for f in resp.get("files", []) if (f.get("name","").lower().endswith(".zip"))]
            files.sort(key=lambda x: x.get("modifiedTime") or "", reverse=True)
            for f in files[:5]:
                drive_rows.append({
                    "파일명": f.get("name",""),
                    "크기": _fmt_size(f.get("size") or 0),
                    "수정시각(UTC)": (f.get("modifiedTime","")[:16].replace("T"," ") if f.get("modifiedTime") else "-"),
                })
        else:
            drive_msg = "드라이브 연결/권한 또는 백업 폴더 ID가 없습니다."
    except Exception:
        drive_msg = "드라이브 목록 조회 중 오류가 발생했습니다."

    # ── 렌더링 ──────────────────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("### 백업 ZIP 현황", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.caption("로컬 백업 (최신 5)")
            if local_rows:
                st.dataframe(local_rows, use_container_width=True, hide_index=True)
            else:
                st.markdown("— 표시할 로컬 ZIP이 없습니다.")
                st.caption("※ 복구가 로컬 ZIP로 진행된 경우에는 `restored_*` 캐시가 남지 않을 수 있습니다.")
        with c2:
            st.caption("드라이브 backup_zip (최신 5)")
            if drive_rows:
                st.dataframe(drive_rows, use_container_width=True, hide_index=True)
            else:
                st.markdown("— 표시할 드라이브 ZIP이 없습니다.")
                if drive_msg:
                    st.caption(f"※ {drive_msg}")

    # ── 로컬 인덱스 파일 상태 ───────────────────────────────────────────────────
    try:
        chunks = (Path(PERSIST_DIR) / "chunks.jsonl")
        ready = (Path(PERSIST_DIR) / ".ready")
        st.markdown("- **로컬 인덱스 파일**: " + ("✅ 있음" if chunks.exists() else "❌ 없음") + f" (`{chunks.as_posix()}`)")
        st.markdown("- **.ready 마커**: " + ("✅ 있음" if ready.exists() else "❌ 없음") + f" (`{ready.as_posix()}`)")
    except Exception:
        pass

# ===== [06] SIMPLE QA DEMO (모바일 최적 + 빈 섹션 숨김 + ensure shim) ==========
from pathlib import Path
from typing import Any, Dict, List, Tuple
import time
import streamlit as st

# ── [06-A] 안전용 shim: _ensure_answer_cache 누락 시 즉시 정의 ─────────────────
try:
    _ensure_answer_cache  # type: ignore[name-defined]
except Exception:
    def _ensure_answer_cache():
        if "answer_cache" not in st.session_state:
            st.session_state["answer_cache"] = {}
        if "preview_norm" not in st.session_state:
            st.session_state["preview_norm"] = ""
        if "preview_open" not in st.session_state:
            st.session_state["preview_open"] = False
# ===== [06-A] END =============================================================


# ── [06-B] Quick fix / 렌더 보조 ──────────────────────────────────────────────
def _sentence_quick_fix(user_q: str) -> List[Tuple[str, str]]:
    tips: List[Tuple[str, str]] = []
    import re as _re
    if _re.search(r"\bI\s+seen\b", user_q, flags=_re.I):
        tips.append(("I seen", "I **saw** the movie / I **have seen** the movie"))
    if _re.search(r"\b(he|she|it)\s+don'?t\b", user_q, flags=_re.I):
        tips.append(("he/she/it don't", "**doesn't**"))
    if _re.search(r"\ba\s+[aeiouAEIOU]", user_q):
        tips.append(("a + 모음 시작 명사", "가능하면 **an** + 모음 시작 명사"))
    return tips

def _render_clean_answer(mode_label: str, answer_text: str, refs: List[Dict[str, str]]):
    st.markdown(f"**선택 모드:** `{mode_label}`")
    st.markdown("#### ✅ 요약/안내 (한국어)")
    with st.expander("원문 응답 보기(영문)"):
        st.write((answer_text or "").strip() or "—")
    if refs:
        with st.expander("근거 자료(상위 2개)"):
            for i, r in enumerate(refs[:2], start=1):
                name = r.get("doc_id") or r.get("source") or f"ref{i}"
                url = r.get("url") or r.get("source_url") or ""
                st.markdown(f"- {name}  " + (f"(<{url}>)" if url else ""))

def _on_q_enter():
    st.session_state["qa_submitted"] = True
    try: st.toast("✳️ 답변 준비 중…")
    except Exception: pass
# ===== [06-B] END =============================================================


# ── [06-C] 기록/랭킹(로컬 jsonl) ─────────────────────────────────────────────
def _history_path() -> Path:
    p = Path.home() / ".maic"
    try: p.mkdir(parents=True, exist_ok=True)
    except Exception: pass
    return p / "qa_history.jsonl"

def _sanitize_user(name: str | None) -> str:
    import re as _re
    s = (name or "").strip()
    s = _re.sub(r"\s+", " ", s)[:40]
    return s or "guest"

def _append_history(q: str, user: str | None = None):
    try:
        q = (q or "").strip()
        if not q: return
        user = _sanitize_user(user)
        if "qa_session_history" not in st.session_state:
            st.session_state["qa_session_history"] = []
        st.session_state["qa_session_history"].insert(0, {"ts": int(time.time()), "q": q, "user": user})
        import json as _json
        hp = _history_path()
        with hp.open("a", encoding="utf-8") as f:
            f.write(_json.dumps({"ts": int(time.time()), "q": q, "user": user}, ensure_ascii=False) + "\n")
    except Exception: pass

def _read_history_lines(max_lines: int = 5000) -> List[Dict[str, Any]]:
    import json as _json
    hp = _history_path()
    if not hp.exists(): return []
    rows: List[Dict[str, Any]] = []
    try:
        with hp.open("r", encoding="utf-8") as f:
            lines = f.readlines()[-max_lines:]
        for ln in lines:
            try:
                r = _json.loads(ln)
                if "user" not in r: r["user"] = "guest"
                rows.append(r)
            except Exception: continue
    except Exception: return []
    rows.reverse()
    return rows

def _normalize_question(s: str) -> str:
    import re as _re
    s = (s or "").strip().lower()
    s = _re.sub(r"[!?。．！?]+$", "", s)
    s = _re.sub(r"[^\w\sㄱ-ㅎ가-힣]", " ", s)
    s = _re.sub(r"\s+", " ", s).strip()
    return s

def _popular_questions(top_n: int = 10, days: int = 7) -> List[Tuple[str, int]]:
    from collections import Counter
    rows = _read_history_lines(max_lines=5000)
    if not rows: return []
    cutoff = int(time.time()) - days * 86400 if days and days > 0 else 0
    counter: Counter[str] = Counter()
    exemplar: Dict[str, str] = {}
    for r in rows:
        ts = int(r.get("ts") or 0)
        if cutoff and ts and ts < cutoff: continue
        q = (r.get("q") or "").strip()
        if not q: continue
        key = _normalize_question(q)
        if not key: continue
        counter[key] += 1
        if key not in exemplar or len(q) < len(exemplar[key]):
            exemplar[key] = q
    return [(exemplar[k], c) for k, c in counter.most_common(top_n)]

def _top3_users(days: int = 7) -> List[Tuple[str, int]]:
    from collections import Counter
    rows = _read_history_lines(max_lines=5000)
    if not rows: return []
    cutoff = int(time.time()) - days * 86400 if days and days > 0 else 0
    users: List[str] = []
    for r in rows:
        ts = int(r.get("ts") or 0)
        if cutoff and ts and ts < cutoff: continue
        if (r.get("q") or "").strip():
            users.append(_sanitize_user(r.get("user")))
    ctr = Counter(users)
    return ctr.most_common(3)

def _render_top3_badges(top3: List[Tuple[str, int]]):
    data = list(top3[:3])
    while len(data) < 3: data.append(("…", 0))
    medals = ["🥇", "🥈", "🥉"]
    parts = [f"<span class='pill pill-rank'>{medals[i]} {n} · {c}회</span>" for i,(n,c) in enumerate(data)]
    css = """
    <style>
      .sticky-top3 { position: sticky; top: 0; z-index: 999; padding: 6px; 
                     background: rgba(255,255,255,0.9); border-bottom: 1px solid #e5e7eb; }
      .pill-rank { margin-right:6px; padding:4px 8px; border-radius:999px; font-size:0.9rem;
                   background:#2563eb1a; color:#1d4ed8; border:1px solid #2563eb55;}
      .sec-title { font-weight:800; font-size:1.1rem; margin: 6px 0 2px 0;}
    </style>"""
    st.markdown(css + f"<div class='sticky-top3'>{' '.join(parts)}</div>", unsafe_allow_html=True)
# ===== [06-C] END =============================================================


# ── [06-D] 프리뷰 캐시 ───────────────────────────────────────────────────────
def _save_answer_preview(q: str, text: str):
    _ensure_answer_cache()
    norm = _normalize_question(q)
    preview = (text or "").strip()
    if len(preview) > 800: preview = preview[:800].rstrip() + " …"
    st.session_state["answer_cache"][norm] = {"preview": preview, "ts": int(time.time())}
    st.session_state["preview_norm"] = norm
    st.session_state["preview_open"] = True

def _load_and_preview(q: str):
    _ensure_answer_cache()
    st.session_state["qa_q"] = q
    st.session_state["qa_submitted"] = False
    st.session_state["preview_norm"] = _normalize_question(q)
    st.session_state["preview_open"] = True
    st.rerun()

def _close_preview(): st.session_state["preview_open"] = False
def _resubmit_from_preview(): st.session_state["qa_submitted"] = True; st.rerun()
# ===== [06-D] END =============================================================


# ── [06-E] 메인 Q&A UI ───────────────────────────────────────────────────────
from src.ui_components import render_section_title, render_item_row

def render_simple_qa():
    # 안전 보강: 혹시라도 누락되었을 경우 한 번 더 초기화
    _ensure_answer_cache()

    is_admin = st.session_state.get("is_admin", False)

    # (0) TOP3 — 학생만
    if not is_admin:
        _render_top3_badges(_top3_users())

    # (1) 질문 입력창 + 모드 선택 + 버튼 → 최상단
    st.markdown("### 💬 질문해 보세요")
    mode_choice = st.radio(
        "질문의 종류를 선택하세요",
        options=["문법설명(Grammar)", "문장분석(Sentence)", "지문분석(Passage)"],
        key="mode_radio",
        horizontal=True
    )
    if "문법" in mode_choice: mode_key, mode_label = "Grammar", "문법설명(Grammar)"
    elif "문장" in mode_choice: mode_key, mode_label = "Sentence", "문장분석(Sentence)"
    else: mode_key, mode_label = "Passage", "지문분석(Passage)"
    st.session_state["mode"] = mode_key

    if not is_admin:
        st.text_input("내 이름(임시)", key="student_name", placeholder="예: 지민 / 민수 / 유나")

    placeholder = (
        "예: 관계대명사 which 사용법을 알려줘" if mode_key == "Grammar"
        else "예: I seen the movie yesterday 문장 문제점 분석해줘" if mode_key == "Sentence"
        else "예: 이 지문 핵심 요약과 제목 3개, 주제 1개 제안해줘"
    )
    q = st.text_input("질문 입력", placeholder=placeholder, key="qa_q", on_change=_on_q_enter)
    k = st.slider("검색 결과 개수(top_k)", 1, 10, 5, key="qa_k") if is_admin else 5
    if st.button("🧑‍🏫 쌤에게 물어보기", key="qa_go"): st.session_state["qa_submitted"] = True

    # (2) 답변 영역
    answer_box = st.container()
    if st.session_state.get("qa_submitted", False) and q.strip():
        st.session_state["qa_submitted"] = False
        user = _sanitize_user(st.session_state.get("student_name") if not is_admin else "admin")
        _append_history(q, user)

        # _index_ready는 [07]에서 shim으로 주입됨(없으면 안전하게 안내)
        index_ready = False
        try:
            index_ready = bool(globals().get("_index_ready", lambda: False)())
        except Exception:
            index_ready = False

        if index_ready:
            try:
                with answer_box:
                    qe = st.session_state["rag_index"].as_query_engine(top_k=k)
                    r = qe.query(q)
                    raw = getattr(r, "response", "") or str(r)
                    refs: List[Dict[str, str]] = []
                    hits = getattr(r, "source_nodes", None) or getattr(r, "hits", None)
                    if hits:
                        for h in hits[:2]:
                            meta = getattr(h, "metadata", None) or getattr(h, "node", {}).get("metadata", {})
                            refs.append({
                                "doc_id": (meta or {}).get("doc_id") or (meta or {}).get("file_name", ""),
                                "url": (meta or {}).get("source") or (meta or {}).get("url", ""),
                            })
                    if mode_key == "Sentence":
                        for bad, good in _sentence_quick_fix(q):
                            st.markdown(f"- **{bad}** → {good}")
                    _render_clean_answer(mode_label, raw, refs)
                    _save_answer_preview(q, raw)
            except Exception as e:
                st.error(f"검색 실패: {type(e).__name__}: {e}")
        else:
            st.info("아직 두뇌가 준비되지 않았어요. 상단에서 **복구/연결** 또는 **다시 최적화**를 먼저 완료해 주세요.")

    # (3) 프리뷰 (답변 아래 확장)
    if st.session_state.get("preview_open", False):
        with st.expander("📎 미리보기", expanded=True):
            norm = st.session_state.get("preview_norm","")
            cache = st.session_state.get("answer_cache",{})
            preview = cache.get(norm,{}).get("preview","")
            st.write(preview or "미리보기가 없어요.")
            c1,c2 = st.columns(2)
            c1.button("🔄 다시 검색", on_click=_resubmit_from_preview)
            c2.button("❌ 닫기", on_click=_close_preview)

    # (4) 히스토리 & 인기 — 빈 섹션 자동 숨김 + 컴포넌트 사용
    sess_rows: List[Dict[str, Any]] = st.session_state.get("qa_session_history", [])[:10]
    ranked: List[Tuple[str, int]] = _popular_questions(top_n=10, days=7)

    if sess_rows:
        st.markdown("<div class='sec-title'>📒 나의 질문 히스토리</div>", unsafe_allow_html=True)
        for row in sess_rows:
            qtext = row.get("q","")
            render_item_row(
                qtext,
                right_btn=lambda q=qtext: st.button("👁️ 미리보기", key=f"hist_prev_{hash(q)}", on_click=_load_and_preview, args=(q,)),
            )

    if ranked:
        st.markdown("<div class='sec-title'>🔥 인기 질문 (최근 7일)</div>", unsafe_allow_html=True)
        for qtext, cnt in ranked:
            def _right():
                st.write(f"×{cnt}")
                st.button("👁️ 미리보기", key=f"pop_prev_{hash(qtext)}", on_click=_load_and_preview, args=(qtext,))
            render_item_row(qtext, right_btn=_right)
# ===== [06] END ==============================================================


# ===== [07] MAIN =============================================================
def main():
    # (A) 호환성 shim -----------------------------------------------------------
    def _index_ready() -> bool:
        try:
            return get_index_status() == "ready"
        except Exception:
            return False
    globals()['_index_ready'] = _index_ready

    # ── UI 컴포넌트 임포트 ────────────────────────────────────────────────────
    from src.ui_components import render_header, badge_ready

    # 로컬 인덱스 존재 여부(간단 폴백)
    from pathlib import Path as __Path
    def _has_local_index_files() -> bool:
        p = __Path.home() / ".maic" / "persist"
        return (p / "chunks.jsonl").exists() or (p / ".ready").exists()

    # (B) 타이틀+상태 배지 ------------------------------------------------------
    def _render_title_with_status():
        status = get_index_status()  # 'ready' | 'pending' | 'missing'
        is_admin = st.session_state.get("is_admin", False)

        # 학생: "LEES AI 쌤" + "🟢 답변 준비 완료"
        # 관리자: 기존 운영용 배지 유지
        if status == "ready":
            if is_admin:
                badge_html = "<span class='ui-pill ui-pill-green'>🟢 두뇌 준비됨</span>"
            else:
                badge_html = badge_ready("🟢 답변 준비 완료")
        elif status == "pending":
            badge_html = "<span class='ui-pill'>🟡 연결 대기</span>"
        else:
            badge_html = "<span class='ui-pill'>🔴 준비 안 됨</span>"

        # ← 여기서 한 줄로 제목과 배지를 인라인 표시
        render_header("LEES AI 쌤", badge_html)

    # 헤더는 이 렌더 사이클에서 **단 한 번만** 출력
    _render_title_with_status()

    # (C) 유틸: 품질스캐너 트리거 / 연결 / 복구 / 빌드 ----------------------------
    import importlib as _importlib
    from pathlib import Path as _Path

    def _trigger_quality_autoscan():
        try:
            m = _importlib.import_module("src.rag.index_build")
            fn = getattr(m, "autorun_quality_scan_if_stale", None)
        except Exception:
            fn = None
        if callable(fn):
            try:
                res = fn()
                if res.get("ok") and not res.get("skipped"):
                    st.toast("품질 리포트 갱신 완료 ✅", icon="✅")
            except Exception:
                if st.session_state.get("is_admin", False):
                    st.toast("품질 리포트 갱신 실패", icon="⚠️")

    def _auto_attach_or_restore_silently():
        return _attach_from_local()

    def _attach_with_status(label="두뇌 자동 연결 중…") -> bool:
        try:
            with st.status(label, state="running") as s:
                ok = _auto_attach_or_restore_silently()
                st.session_state["brain_attached"] = bool(ok)
                if ok:
                    s.update(label="두뇌 자동 연결 완료 ✅", state="complete")
                    _trigger_quality_autoscan()  # attach 후 품질스캔
                    if not st.session_state.get("_post_attach_rerun_done"):
                        st.session_state["_post_attach_rerun_done"] = True
                        st.rerun()
                else:
                    s.update(label="두뇌 자동 연결 실패 ❌", state="error")
                return bool(ok)
        except Exception:
            ok = _auto_attach_or_restore_silently()
            st.session_state["brain_attached"] = bool(ok)
            if ok:
                _trigger_quality_autoscan()
                if not st.session_state.get("_post_attach_rerun_done"):
                    st.session_state["_post_attach_rerun_done"] = True
                    st.rerun()
            else:
                if st.session_state.get("is_admin", False):
                    st.error("두뇌 자동 연결 실패")
            return bool(ok)

    def _restore_then_attach():
        try:
            _m = _importlib.import_module("src.rag.index_build")
        except Exception as e:
            st.error(f"복구 모듈 임포트 실패: {type(e).__name__}: {e}")
            return False

        _restore = getattr(_m, "restore_latest_backup_to_local", None)
        if not callable(_restore):
            st.error("복구 함수를 찾지 못했습니다. (restore_latest_backup_to_local)")
            return False

        with st.status("백업에서 로컬로 복구 중…", state="running") as s:
            try:
                r = _restore()
            except Exception as e:
                s.update(label="복구 실패 ❌", state="error")
                st.error(f"복구 실패: {type(e).__name__}: {e}")
                return False

            if not r or not r.get("ok"):
                s.update(label="복구 실패 ❌", state="error")
                st.error(f"복구 실패: {r.get('error') if r else 'unknown'}")
                return False

            s.update(label="복구 완료 ✅", state="complete")

        return _attach_with_status("복구 후 두뇌 연결 중…")

    def _build_then_backup_then_attach():
        try:
            _m = _importlib.import_module("src.rag.index_build")
        except Exception as e:
            st.error(f"인덱스 빌더 모듈 임포트 실패: {type(e).__name__}: {e}")
            return False

        build_index_with_checkpoint = getattr(_m, "build_index_with_checkpoint", None)
        _make_and_upload_backup_zip_fn = getattr(_m, "_make_and_upload_backup_zip", None)
        _PERSIST_DIR_OBJ = getattr(_m, "PERSIST_DIR", _Path.home() / ".maic" / "persist")

        if not callable(build_index_with_checkpoint):
            st.error("인덱스 빌더 함수를 찾지 못했습니다. (build_index_with_checkpoint)")
            return False

        prog = st.progress(0); log = st.empty()
        def _pct(v: int, msg: str | None = None):
            prog.progress(max(0, min(int(v), 100)))
            if msg: log.info(str(msg))
        def _msg(s: str): log.write(f"• {s}")

        try:
            with st.status("변경 반영을 위한 다시 최적화 실행 중…", state="running") as s:
                res = build_index_with_checkpoint(
                    update_pct=_pct, update_msg=_msg,
                    gdrive_folder_id="", gcp_creds={},
                    persist_dir=str(_PERSIST_DIR_OBJ), remote_manifest={},
                )
                prog.progress(100)
                s.update(label="다시 최적화 완료 ✅", state="complete")
            st.json(res)
            try:
                if callable(_make_and_upload_backup_zip_fn):
                    _ = _make_and_upload_backup_zip_fn(None, None)
            except Exception:
                pass
            if _restore_then_attach():
                return True
            ok = _attach_with_status("두뇌 연결 중…")
            return bool(ok)
        except Exception as e:
            st.error(f"다시 최적화 실패: {type(e).__name__}: {e}")
            return False

    # (E) 부팅: 로컬 인덱스 없으면 선복구
    local_ok = _has_local_index_files()
    if not local_ok and not _index_ready():
        if _restore_then_attach():
            st.rerun()
        else:
            st.info("백업을 찾지 못했거나 손상되었습니다. ‘업데이트(다시 최적화)’를 실행해 주세요.")
            btn = st.button("업데이트 (다시 최적화 실행)", type="primary", key="boot_build_when_local_missing")
            if btn:
                if _build_then_backup_then_attach():
                    st.rerun()
                else:
                    st.stop()
        st.stop()

    # (F) 사전점검(관리자 전용)
    is_admin = st.session_state.get("is_admin", False)
    import importlib as _importlib
    from pathlib import Path as _Path
    _mod = None
    _quick_precheck = None
    _PERSIST_DIR = _Path.home() / ".maic" / "persist"
    try:
        _mod = _importlib.import_module("src.rag.index_build")
        _quick_precheck = getattr(_mod, "quick_precheck", None)
        _PERSIST_DIR = getattr(_mod, "PERSIST_DIR", _PERSIST_DIR)
    except Exception:
        pass

    pre = {}
    if is_admin and callable(_quick_precheck):
        try:
            pre = _quick_precheck("")
        except Exception as e:
            st.warning(f"사전점검 실패: {type(e).__name__}: {e}")
            pre = {}

    changed_flag = bool(pre.get("changed")) if is_admin else False
    reasons_list = list(pre.get("reasons") or []) if is_admin else []

    if is_admin and changed_flag and not st.session_state.get("_admin_update_prompt_done"):
        with st.container(border=True):
            if "no_local_manifest" in reasons_list:
                st.info("📎 아직 인덱스가 없습니다. **최초 빌드가 필요**합니다.")
            else:
                st.info("📎 prepared 폴더에서 **새 자료(변경/신규)** 가 감지되었습니다.")
            c1, c2 = st.columns(2)
            with c1:
                do_update = st.button("업데이트 (다시 최적화 실행)", type="primary", key="admin_update_now")
            with c2:
                later = st.button("다음에 업데이트", key="admin_update_later")

        if do_update:
            st.session_state["_admin_update_prompt_done"] = True
            if _build_then_backup_then_attach():
                st.rerun()
            else:
                st.stop()

        if later:
            st.session_state["_admin_update_prompt_done"] = True
            if _restore_then_attach():
                st.rerun()
            else:
                st.info("백업을 찾지 못했거나 손상되었습니다. ‘업데이트(다시 최적화)’를 실행해 주세요.")
                st.stop()
        st.stop()

    # (G) 일반 플로우 — 디버그 로그는 관리자에만
    if is_admin:
        decision_log = st.empty()
        decision_log.info(
            "auto-boot(is_admin={}) admin_changed={} reasons={}".format(is_admin, changed_flag, reasons_list)
        )

    if not _index_ready():
        if _attach_with_status():
            st.rerun()
        else:
            if is_admin:
                st.info("두뇌 연결 실패. 필요 시 ‘업데이트(다시 최적화)’를 실행해 주세요.")

    # (H) 화면 섹션
    if is_admin:
        render_brain_prep_main()
        st.divider()
        render_tag_diagnostics()
        st.divider()
        render_simple_qa()
    else:
        render_simple_qa()

if __name__ == "__main__":
    main()
# ===== [07] END =============================================================
