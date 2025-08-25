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
    상단 우측 컨트롤:
      - 학생 모드: [🔒 관리자] + [🔎 진단 열기/닫기] + [📦 지금 백업]
      - 관리자 모드: [🔓 관리자 종료] + [🔎 진단 열기/닫기] + [📦 지금 백업]
    """
    import streamlit as st
    from pathlib import Path
    from datetime import datetime
    import zipfile, importlib

    def _resolve_paths():
        PERSIST_DIR = Path.home()/".maic"/"persist"
        BACKUP_DIR  = Path.home()/".maic"/"backup"
        try:
            m = importlib.import_module("src.rag.index_build")
            PERSIST_DIR = getattr(m, "PERSIST_DIR", PERSIST_DIR)
            BACKUP_DIR  = getattr(m, "BACKUP_DIR", BACKUP_DIR)
        except Exception:
            pass
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        return PERSIST_DIR, BACKUP_DIR

    def _make_local_backup():
        try:
            PERSIST_DIR, BACKUP_DIR = _resolve_paths()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_path = BACKUP_DIR / f"backup_{ts}.zip"
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
                for p in PERSIST_DIR.rglob("*"):
                    if p.is_file():
                        z.write(p, arcname=p.relative_to(PERSIST_DIR))
                z.writestr(".backup_info.txt", f"created_at={ts}\n")
            return {"ok": True, "path": str(zip_path)}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def _upload_backup_to_drive(zip_path: Path):
        # 가능한 환경에서만 업로드 (없으면 건너뜀)
        try:
            m = importlib.import_module("src.rag.index_build")
            _drive_service = getattr(m, "_drive_service", None)
            _pick_backup_folder_id = getattr(m, "_pick_backup_folder_id", None)
            if not (callable(_drive_service) and callable(_pick_backup_folder_id)):
                return {"ok": False, "error": "drive_helper_missing"}
            try:
                from googleapiclient.http import MediaFileUpload  # type: ignore
            except Exception:
                return {"ok": False, "error": "media_upload_unavailable"}
            svc = _drive_service()
            folder_id = _pick_backup_folder_id(svc)
            if not (svc and folder_id):
                return {"ok": False, "error": "folder_id_unavailable"}
            media = MediaFileUpload(str(zip_path), mimetype="application/zip", resumable=False)
            meta = {"name": zip_path.name, "parents": [folder_id]}
            created = svc.files().create(
                body=meta, media_body=media, fields="id", supportsAllDrives=True
            ).execute()
            return {"ok": True, "file_id": created.get("id")}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def _fmt_size(n):
        try: n = int(n)
        except Exception: return "-"
        u=["B","KB","MB","GB","TB"]; i=0; f=float(n)
        while f>=1024 and i<len(u)-1: f/=1024.0; i+=1
        return (f"{int(f)} {u[i]}" if i==0 else f"{f:.1f} {u[i]}")

    with st.container():
        _, right = st.columns([0.65, 0.35])
        with right:
            if st.session_state.get("is_admin", False):
                # 관리자 모드
                c1, c2, c3 = st.columns([0.34, 0.33, 0.33])
                with c1:
                    if st.button("🔓 관리자 종료", key="btn_close_admin", use_container_width=True):
                        st.session_state["is_admin"] = False
                        st.session_state["_admin_auth_open"] = False
                        st.rerun()
                with c2:
                    label = "🔎 진단 닫기" if st.session_state.get("_diag_quick_open", False) else "🔎 진단 열기"
                    if st.button(label, key="btn_toggle_diag_quick_admin", use_container_width=True):
                        st.session_state["_diag_quick_open"] = not st.session_state.get("_diag_quick_open", False)
                        st.rerun()
                with c3:
                    if st.button("📦 지금 백업", key="btn_backup_now_admin", use_container_width=True):
                        res = _make_local_backup()
                        if res.get("ok"):
                            zp = Path(res["path"])
                            up = _upload_backup_to_drive(zp)
                            try: st.cache_data.clear()
                            except Exception: pass
                            size = _fmt_size(zp.stat().st_size) if zp.exists() else "-"
                            st.success(f"백업 완료: {zp.name} ({size})" + (" → Drive 업로드 성공" if up.get("ok") else " — Drive 업로드 건너뜀/실패"))
                        else:
                            st.error(f"백업 실패: {res.get('error')}")
            else:

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
