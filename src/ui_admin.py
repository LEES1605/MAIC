# ===== [UA-01] ADMIN CONTROLS MODULE — START ================================
from __future__ import annotations
import os
import streamlit as st

# ── [UA-01A] PIN 소스 --------------------------------------------------------
def get_admin_pin() -> str:
    """
    우선순위: st.secrets['ADMIN_PIN'] → 환경변수 ADMIN_PIN → 기본 '0000'
    """
    try:
        pin = st.secrets.get("ADMIN_PIN", None)  # type: ignore[attr-defined]
    except Exception:
        pin = None
    return str(pin or os.environ.get("ADMIN_PIN") or "0000")

# ── [UA-01B] 세션 키 보증 -----------------------------------------------------
def ensure_admin_session_keys() -> None:
    """
    app.py 어디서든 호출해도 안전. 필요한 세션 키가 없으면 기본값 생성.
    """
    if "is_admin" not in st.session_state:
        st.session_state["is_admin"] = False
    if "_admin_auth_open" not in st.session_state:
        st.session_state["_admin_auth_open"] = False

# ── [UA-01C] 관리자 버튼/인증 패널 — START ------------------------------------
def render_admin_controls() -> None:
    """
    상단 우측 '관리자' 버튼과 PIN 인증 폼을 렌더링.
    + '🔎 진단'은 스크롤 대신 상단에 '진단(퀵패널)'을 즉시 펼쳐서 표시.
    """
    import streamlit as st
    from pathlib import Path
    from datetime import datetime
    import importlib

    # 내부 상태 플래그 준비
    if "_diag_quick_open" not in st.session_state:
        st.session_state["_diag_quick_open"] = False

    def _fmt_size(n):
        try:
            n = int(n)
        except Exception:
            return "-"
        units = ["B","KB","MB","GB","TB"]; i=0; f=float(n)
        while f>=1024 and i<len(units)-1:
            f/=1024.0; i+=1
        return (f"{int(f)} {units[i]}" if i==0 else f"{f:.1f} {units[i]}")

    def _fmt_ts(ts):
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "-"

    def _resolve_paths():
        PERSIST_DIR = Path.home() / ".maic" / "persist"
        BACKUP_DIR  = Path.home() / ".maic" / "backup"
        QUALITY_REPORT_PATH = Path.home() / ".maic" / "quality_report.json"
        try:
            m = importlib.import_module("src.rag.index_build")
            PERSIST_DIR = getattr(m, "PERSIST_DIR", PERSIST_DIR)
            BACKUP_DIR  = getattr(m, "BACKUP_DIR", BACKUP_DIR)
            QUALITY_REPORT_PATH = getattr(m, "QUALITY_REPORT_PATH", QUALITY_REPORT_PATH)
        except Exception:
            pass
        return PERSIST_DIR, BACKUP_DIR, QUALITY_REPORT_PATH

    with st.container():
        _, right = st.columns([0.7, 0.3])
        with right:
            c_admin, c_diag = st.columns([0.55, 0.45])

            # --- 관리자 진입/종료 버튼 ---
            if st.session_state.get("is_admin", False):
                with c_admin:
                    if st.button("🔓 관리자 종료", key="btn_close_admin", use_container_width=True):
                        st.session_state["is_admin"] = False
                        st.session_state["_admin_auth_open"] = False
                        try: st.toast("관리자 모드 해제됨")
                        except Exception: pass
                        st.rerun()
            else:
                with c_admin:
                    if st.button("🔒 관리자", key="btn_open_admin", use_container_width=True):
                        st.session_state["_admin_auth_open"] = True
                        st.rerun()

            # --- 진단 퀵패널 토글 버튼 (클릭 즉시 rerun으로 1회 클릭 반영) ---
            with c_diag:
                label = "🔎 진단 닫기" if st.session_state["_diag_quick_open"] else "🔎 진단 열기"
                if st.button(label, key="btn_toggle_diag_quick", use_container_width=True,
                             help="상단에서 바로 보는 진단(퀵패널)을 토글합니다."):
                    st.session_state["_diag_quick_open"] = not st.session_state["_diag_quick_open"]
                    st.rerun()  # ← 여기 추가: 즉시 재실행하여 버튼 라벨/패널 상태를 한 번에 반영

            # --- 인증 패널 ---
            if st.session_state.get("_admin_auth_open", False) and not st.session_state.get("is_admin", False):
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
                    if pin_try == get_admin_pin():
                        st.session_state["is_admin"] = True
                        st.session_state["_admin_auth_open"] = False
                        try: st.toast("관리자 모드 진입 ✅")
                        except Exception: pass
                        st.rerun()
                    else:
                        st.error("PIN이 올바르지 않습니다.")

    # ── 진단(퀵패널) -----------------------------------------------------------
    if st.session_state.get("_diag_quick_open", False):
        PERSIST_DIR, BACKUP_DIR, QUALITY_REPORT_PATH = _resolve_paths()

        # 로컬 인덱스 파일 상태
        chunks = (Path(PERSIST_DIR) / "chunks.jsonl")
        ready  = (Path(PERSIST_DIR) / ".ready")
        chunks_ok = chunks.exists()
        ready_ok  = ready.exists()

        # 로컬 백업 ZIP
        local_has = False
        local_rows = []
        try:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            zips = list(BACKUP_DIR.glob("backup_*.zip")) + list(BACKUP_DIR.glob("restored_*.zip"))
            zips.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            local_has = len(zips) > 0
            for p in zips[:5]:
                stt = p.stat()
                local_rows.append({"파일명": p.name, "크기": _fmt_size(stt.st_size), "수정시각": _fmt_ts(stt.st_mtime)})
        except Exception:
            pass

        # 드라이브 백업 ZIP (있으면 확인)
        drive_has = False
        drive_folder_id = None
        drive_msg = None
        try:
            m = importlib.import_module("src.rag.index_build")
            _drive_service = getattr(m, "_drive_service", None)
            _pick_backup_folder_id = getattr(m, "_pick_backup_folder_id", None)
            svc = _drive_service() if callable(_drive_service) else None
            drive_folder_id = _pick_backup_folder_id(svc) if (svc and callable(_pick_backup_folder_id)) else None
            if svc and drive_folder_id:
                resp = svc.files().list(
                    q=f"'{drive_folder_id}' in parents and trashed=false and mimeType!='application/vnd.google-apps.folder'",
                    fields="files(id,name)", includeItemsFromAllDrives=True, supportsAllDrives=True,
                    corpora="allDrives", pageSize=1
                ).execute()
                files = resp.get("files", [])
                drive_has = len(files) > 0
            else:
                drive_msg = "드라이브 연결/권한 또는 backup_zip 폴더 식별이 되지 않았습니다."
        except Exception:
            drive_msg = "드라이브 목록 조회 중 오류가 발생했습니다."

        # 자동 복구 상태
        auto_info = st.session_state.get("_auto_restore_last", {})
        step = str(auto_info.get("step", "—"))
        ok_local = auto_info.get("local_attach")
        ok_drive = auto_info.get("drive_restore")
        ok_build = auto_info.get("rebuild")
        ok_final = auto_info.get("final_attach")
        def _b(label, ok):
            return f"✅ {label}" if ok is True else (f"❌ {label}" if ok is False else f"— {label}")

        with st.container(border=True):
            st.markdown("### 진단(퀵패널)")
            st.markdown("- 단계: **" + step + "**")
            st.markdown("- " + " · ".join([
                _b("로컬부착", ok_local),
                _b("드라이브복구", ok_drive),
                _b("재빌드", ok_build),
                _b("최종부착", ok_final),
            ]))
            st.markdown(f"- **로컬 인덱스 파일**: {'✅ 있음' if chunks_ok else '❌ 없음'}  (`{chunks.as_posix()}`)")
            st.markdown(f"- **.ready 마커**: {'✅ 있음' if ready_ok else '❌ 없음'}  (`{ready.as_posix()}`)")
            st.markdown(f"- **로컬 백업 ZIP**: {'✅ 있음' if local_has else '❌ 없음'}  (`{BACKUP_DIR.as_posix()}`)")
            st.markdown(
                "- **드라이브 백업 ZIP**: "
                + ("✅ 있음" if drive_has else "❌ 없음")
                + (f"  (folder_id: `{drive_folder_id}`)" if drive_folder_id else "")
            )
            if drive_msg:
                st.caption(f"※ {drive_msg}")

            # (혼동 방지) 하단 전체 진단 섹션 링크 대신 안내 캡션으로 변경
            st.caption("전체 진단 세부는 페이지 하단의 **진단/로그(관리자 전용)** 섹션에서 확인할 수 있어요.")
# ── [UA-01C] 관리자 버튼/인증 패널 — END --------------------------------------




# ── [UA-01D] 역할 캡션 --------------------------------------------------------
def render_role_caption() -> None:
    """
    역할 안내 캡션(학생/관리자). 시각적 혼란을 줄이기 위해 한 줄 고정 문구.
    """
    if st.session_state.get("is_admin", False):
        st.caption("역할: **관리자** — 상단 버튼으로 종료 가능")
    else:
        st.caption("역할: **학생** — 질문/답변에 집중할 수 있게 단순화했어요.")
# ===== [UA-01] ADMIN CONTROLS MODULE — END ==================================
