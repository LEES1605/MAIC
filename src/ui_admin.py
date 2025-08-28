# ===== [UA-01] ADMIN CONTROLS MODULE — START ================================
from __future__ import annotations
import os
import json
from pathlib import Path
import importlib
import streamlit as st

# ── [UA-01A] PIN 소스 --------------------------------------------------------
def get_admin_pin() -> str:
    """
    우선순위:
      st.secrets['APP_ADMIN_PASSWORD'] → st.secrets['ADMIN_PIN']
      → os.environ['APP_ADMIN_PASSWORD'] → os.environ['ADMIN_PIN'] → '0000'
    """
    try:
        pin = st.secrets.get("APP_ADMIN_PASSWORD") or st.secrets.get("ADMIN_PIN")  # type: ignore[attr-defined]
    except Exception:
        pin = None
    return str(
        pin
        or os.environ.get("APP_ADMIN_PASSWORD")
        or os.environ.get("ADMIN_PIN")
        or "0000"
    )

# ── [UA-01B] 세션 키 보증 -----------------------------------------------------
def ensure_admin_session_keys() -> None:
    if "is_admin" not in st.session_state:
        st.session_state["is_admin"] = False
    if "_admin_auth_open" not in st.session_state:
        st.session_state["_admin_auth_open"] = False

# ── 내부 공용: 경로 해석(모두 config 기준) ------------------------------------
def _config_paths() -> tuple[Path, Path]:
    """
    PERSIST, BACKUP 경로를 src.config 기준으로 가져온다.
    """
    try:
        from src.config import PERSIST_DIR as _PD, APP_DATA_DIR as _AD
        persist = Path(_PD).expanduser()
        backup  = (Path(_AD) / "backup").expanduser()
    except Exception:
        base = Path.home() / ".maic"
        persist = base / "persist"
        backup  = base / "backup"
    persist.mkdir(parents=True, exist_ok=True)
    backup.mkdir(parents=True, exist_ok=True)
    return persist, backup

# ── 내부 공용: 백업 실행(엔진 우선) ------------------------------------------
def _backup_now() -> dict:
    """
    1순위: 엔진의 `_make_and_upload_backup_zip()` 사용(정책·보관 규칙 일치)
    2순위: 로컬 zip만 생성(Drive 업로드 시도 X)
    """
    PERSIST_DIR, BACKUP_DIR = _config_paths()

    # 1) 엔진 함수 우선
    try:
        m = importlib.import_module("src.rag.index_build")
        fn = getattr(m, "_make_and_upload_backup_zip", None)
        if callable(fn):
            r = fn() or {}
            return {"ok": bool(r.get("ok")), "detail": r}
    except Exception as e:
        return {"ok": False, "error": f"engine_backup_error: {type(e).__name__}: {e}"}

    # 2) 폴백: 로컬 zip만 생성
    from datetime import datetime
    import zipfile
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = BACKUP_DIR / f"backup_{ts}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for p in PERSIST_DIR.rglob("*"):
                if p.is_file():
                    z.write(p, arcname=p.relative_to(PERSIST_DIR))
            z.writestr(".backup_info.txt", f"created_at={ts}\n")
        return {"ok": True, "path": str(zip_path)}
    except Exception as e:
        return {"ok": False, "error": f"local_zip_error: {type(e).__name__}: {e}"}

# ── [UA-01C] 관리자 버튼/인증 패널 -------------------------------------------
def render_admin_controls() -> None:
    """
    상단 우측 컨트롤:
      - 학생 모드: [🔒 관리자] + [🔎 진단 열기/닫기] + [📦 지금 백업]
      - 관리자 모드: [🔓 관리자 종료] + [🔎 진단 열기/닫기] + [📦 지금 백업]
    (백업은 엔진 함수 우선, 실패 시 로컬 zip만 생성)
    """
    with st.container():
        _, right = st.columns([0.65, 0.35])
        with right:
            if st.session_state.get("is_admin", False):
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
                        r = _backup_now()
                        if r.get("ok"):
                            st.success("백업 완료(엔진 규칙).")
                        else:
                            st.error(f"백업 실패: {r.get('error') or r.get('detail')}")
            else:
                c1, c2, c3 = st.columns([0.34, 0.33, 0.33])
                with c1:
                    if st.button("🔒 관리자", key="btn_open_admin", use_container_width=True):
                        st.session_state["_admin_auth_open"] = True
                        st.rerun()
                with c2:
                    label = "🔎 진단 닫기" if st.session_state.get("_diag_quick_open", False) else "🔎 진단 열기"
                    if st.button(label, key="btn_toggle_diag_quick", use_container_width=True):
                        st.session_state["_diag_quick_open"] = not st.session_state.get("_diag_quick_open", False)
                        st.rerun()
                with c3:
                    if st.button("📦 지금 백업", key="btn_backup_now_student", use_container_width=True):
                        r = _backup_now()
                        if r.get("ok"):
                            st.success("백업 완료(엔진 규칙).")
                        else:
                            st.error(f"백업 실패: {r.get('error') or r.get('detail')}")

    # 인증 폼
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
                st.session_state["_prepared_prompt_done"] = False
                try: st.cache_data.clear()
                except Exception: pass
                try: st.toast("관리자 모드 진입 ✅ 새 자료 점검을 시작합니다")
                except Exception: pass
                st.rerun()
            else:
                st.error("PIN이 틀렸습니다. 다시 입력해 주세요.")

    # 퀵 진단
    if st.session_state.get("_diag_quick_open", False):
        try:
            render_quick_diagnostics_anyrole()
        except Exception as e:
            st.caption(f"진단 렌더 오류: {type(e).__name__}: {e}")

# ── [UA-01D] 역할 캡션 --------------------------------------------------------
def render_role_caption() -> None:
    if st.session_state.get("is_admin", False):
        st.caption("역할: **관리자** — 상단 버튼으로 종료 가능")
    else:
        st.caption("역할: **학생** — 질문/답변에 집중할 수 있게 단순화했어요.")

# ── [UA-01E] 퀵 진단 렌더러(역할 무관) ---------------------------------------
def render_quick_diagnostics_anyrole() -> None:
    """
    config 기준 경로만 사용하여 혼선을 제거.
    """
    import datetime as _dt

    PERSIST_DIR, BACKUP_DIR = _config_paths()
    chunks = PERSIST_DIR / "chunks.jsonl"
    ready  = PERSIST_DIR / ".ready"

    auto = st.session_state.get("_auto_restore_last", {}) or {}
    step = str(auto.get("step", "—"))

    def _b(label, val):
        return f"✅ {label}" if val is True else (f"❌ {label}" if val is False else f"— {label}")

    with st.container(border=True):
        st.markdown("### 진단(퀵패널)")
        st.markdown(f"- 단계: **{step}**")
        st.markdown("- " + " · ".join([
            _b("로컬부착",  auto.get("local_attach")),
            _b("드라이브복구", auto.get("drive_restore")),
            _b("재빌드",     auto.get("rebuild")),
            _b("최종부착",   auto.get("final_attach")),
        ]))
        st.markdown(f"- **로컬 인덱스 파일**: {'✅ 있음' if chunks.exists() else '❌ 없음'}  (`{chunks.as_posix()}`)")
        st.markdown(f"- **.ready 마커**: {'✅ 있음' if ready.exists() else '❌ 없음'}  (`{ready.as_posix()}`)")
        st.markdown(f"- **로컬 백업 경로**: `{BACKUP_DIR.as_posix()}`")

        try:
            zips = sorted(BACKUP_DIR.glob('*.zip'), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
            if zips:
                st.caption("최근 로컬 백업 (최신 5)")
                for zp in zips:
                    ts = _dt.datetime.utcfromtimestamp(zp.stat().st_mtime).isoformat() + "Z"
                    size_mb = zp.stat().st_size / (1024*1024)
                    st.write(f"• {zp.name} ({size_mb:.1f} MB) — {ts}")
            else:
                st.caption("최근 로컬 백업: 없음")
        except Exception:
            st.caption("로컬 백업 요약을 불러오는 중 문제가 발생했습니다.")
# ===== [UA-01] ADMIN CONTROLS MODULE — END ==================================
