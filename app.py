# =============================== [01] future import ===============================
from __future__ import annotations

# =============================== [02] module imports ==============================
import os
import json
import time
import traceback
import importlib
import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import streamlit as st  # Streamlit 환경이 아닐 수도 있으므로 try
except Exception:
    st = None


# =========================== [03] CORE: Persist Resolver ==========================
def _effective_persist_dir() -> Path:
    """앱 전역 Persist 경로 해석기(단일 소스).
    우선순위:
      1) 세션 스탬프: st.session_state['_PERSIST_DIR']
      2) 인덱서 기본값: src.rag.index_build.PERSIST_DIR
      3) ENV/Secrets: MAIC_PERSIST_DIR
      4) 기본값: ~/.maic/persist
    """
    # 세션 고정값
    try:
        if "st" in globals() and st is not None:
            p = st.session_state.get("_PERSIST_DIR")
            if p:
                return Path(str(p)).expanduser()
    except Exception:
        pass

    # 인덱서 기본값
    try:
        from src.rag.index_build import PERSIST_DIR as _pp
        return Path(str(_pp)).expanduser()
    except Exception:
        pass

    # 환경/시크릿
    envp = os.getenv("MAIC_PERSIST_DIR", "")
    if envp:
        return Path(envp).expanduser()

    # 기본
    return Path.home() / ".maic" / "persist"


# ================== [04] secrets → env 승격 & 페이지 설정(안정 옵션) =================
def _from_secrets(name: str, default: Optional[str] = None) -> Optional[str]:
    """Streamlit secrets 우선, 없으면 os.environ. dict/list는 JSON 문자열화."""
    try:
        if st is None or not hasattr(st, "secrets"):
            return os.getenv(name, default)
        val = st.secrets.get(name, None)
        if val is None:
            return os.getenv(name, default)
        if isinstance(val, str):
            return val
        return json.dumps(val, ensure_ascii=False)
    except Exception:
        return os.getenv(name, default)


def _bootstrap_env() -> None:
    """필요 시 secrets 값을 환경변수로 승격 + 서버 안정화 옵션."""
    keys = [
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "GH_TOKEN",
        "GH_REPO",
        "GH_BRANCH",
        "GH_PROMPTS_PATH",
        "GDRIVE_PREPARED_FOLDER_ID",
        "GDRIVE_BACKUP_FOLDER_ID",
        "APP_MODE",
        "AUTO_START_MODE",
        "LOCK_MODE_FOR_STUDENTS",
        "APP_ADMIN_PASSWORD",
        "DISABLE_BG",
        "MAIC_PERSIST_DIR",
        "GITHUB_TOKEN",
        "GITHUB_OWNER",
        "GITHUB_REPO_NAME",
        "GITHUB_REPO",
        "GH_OWNER",
        "GH_REPO",
    ]
    for k in keys:
        v = _from_secrets(k)
        if v and not os.getenv(k):
            os.environ[k] = str(v)

    # Streamlit 안정화
    os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")
    os.environ.setdefault("STREAMLIT_RUN_ON_SAVE", "false")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault(
        "STREAMLIT_SERVER_ENABLE_WEBSOCKET_COMPRESSION", "false"
    )


_bootstrap_env()

if st:
    try:
        st.set_page_config(page_title="LEES AI Teacher", layout="wide")
    except Exception:
        pass

# ======================= [05] 경로/상태 & 에러 로거 — START =======================
# NOTE:
# - 이 구획은 SSOT(코어)만 참조하도록 단순화했습니다.
# - 기존 함수명(_mark_ready/_is_brain_ready/_get_brain_status)은 유지합니다.

from pathlib import Path
import traceback

# SSOT: persist / status
from src.core.persist import effective_persist_dir, share_persist_dir_to_session, PERSIST_DIR as CORE_PERSIST_DIR
from src.core.index_probe import probe_index_health, mark_ready as core_mark_ready, is_brain_ready as core_is_ready, get_brain_status as core_status

# 1) Persist 경로 상수: 코어 결정값 사용
PERSIST_DIR: Path = effective_persist_dir()
try:
    PERSIST_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

# 세션에도 공유(있을 때만)
try:
    share_persist_dir_to_session(PERSIST_DIR)
except Exception:
    pass


def _errlog(msg: str, where: str = "", exc: Exception | None = None) -> None:
    """표준 에러 로깅(콘솔 + Streamlit 노출). 민감정보 금지, 실패 무해화."""
    try:
        prefix = f"{where} " if where else ""
        print(f"[ERR] {prefix}{msg}")
        if exc:
            traceback.print_exception(exc)
        if st is not None:
            try:
                with st.expander("자세한 오류 로그", expanded=False):
                    detail = ""
                    if exc:
                        try:
                            detail = "".join(
                                traceback.format_exception(type(exc), exc, exc.__traceback__)
                            )
                        except Exception:
                            detail = "traceback 사용 불가"
                    st.code(f"{prefix}{msg}\n{detail}")
            except Exception:
                pass
    except Exception:
        pass


def _mark_ready() -> None:
    """준비 신호 파일(.ready) 생성 — 코어 위임."""
    try:
        core_mark_ready(PERSIST_DIR)
    except Exception:
        pass


def _is_brain_ready() -> bool:
    """코어 기준으로 인덱스 준비 여부."""
    try:
        return bool(core_is_ready(PERSIST_DIR))
    except Exception:
        return False


def _get_brain_status() -> Dict[str, str]:
    """앱 전역 상위 상태(SSOT). 세션 오버라이드가 있으면 코어 결과를 덮지 않음."""
    try:
        if st is not None:
            ss = st.session_state
            code = ss.get("brain_status_code")
            msg = ss.get("brain_status_msg")
            if code and msg:
                return {"code": str(code), "msg": str(msg)}
        return core_status(PERSIST_DIR)
    except Exception as e:
        _errlog("상태 계산 실패", where="[05]_get_brain_status", exc=e)
        return {"code": "MISSING", "msg": "상태 계산 실패"}
# ======================= [05] 경로/상태 & 에러 로거 — END =========================


# ========================= [06] ACCESS: Admin Gate ============================
def _is_admin_view() -> bool:
    """관리자 패널 표시 여부(학생 화면 완전 차단).
    - 오직 세션 로그인 플래그로만 허용: admin_mode | is_admin
    """
    if st is None:
        return False
    try:
        ss = st.session_state
        return bool(ss.get("admin_mode") or ss.get("is_admin"))
    except Exception:
        return False

# ======================= [07] RERUN GUARD utils ==============================
def _safe_rerun(tag: str, ttl: int = 1) -> None:
    """Streamlit rerun을 '태그별 최대 ttl회'로 제한."""
    st_mod = globals().get("st", None)
    if st_mod is None:
        return
    try:
        ss = getattr(st_mod, "session_state", None)
        if not isinstance(ss, dict):
            return
        key = "__rerun_counts__"
        counts = ss.get(key)
        if not isinstance(counts, dict):
            counts = {}
        cnt = int(counts.get(tag, 0))
        if cnt >= int(ttl):
            return
        counts[tag] = cnt + 1
        ss[key] = counts
        st_mod.rerun()
    except Exception:
        pass


# ================= [08] 헤더(배지·타이틀·로그인/아웃) — START ==============
def _header() -> None:
    """모듈화된 헤더 호출 래퍼(호환용)."""
    try:
        from src.ui.header import render as _render_header  # lazy import
        _render_header()
    except Exception as e:
        # fallback: 최소 타이틀
        if st is not None:
            st.markdown("### LEES AI Teacher")
# ================= [08] 헤더(배지·타이틀·로그인/아웃) — END ===============

# ======================= [09] 배경(비활성: No-Op) ===========================
def _inject_modern_bg_lib() -> None:
    """배경 라이브러리 주입을 완전 비활성(No-Op)."""
    try:
        s = globals().get("st", None)
        if s is not None and hasattr(s, "session_state"):
            s.session_state["__bg_lib_injected__"] = False
    except Exception:
        pass


def _mount_background(
    *,
    theme: str = "light",
    accent: str = "#5B8CFF",
    density: int = 3,
    interactive: bool = True,
    animate: bool = True,
    gradient: str = "radial",
    grid: bool = True,
    grain: bool = False,
    blur: int = 0,
    seed: int = 1234,
    readability_veil: bool = True,
) -> None:
    """배경 렌더 OFF(호출 시 즉시 return)."""
    return

# =================== [10] 부팅 훅: 인덱스 자동 복원 =======================
def _boot_auto_restore_index() -> None:
    """부팅 시 인덱스 자동 복원(한 세션 1회).
    - 조건: chunks.jsonl==0B 또는 미존재, 또는 .ready 미존재
    - 동작: GH Releases에서 최신 index_*.zip 받아서 복원
    - SSOT: persist는 core.persist.effective_persist_dir()만 사용
    """
    try:
        if "st" in globals() and st is not None:
            if st.session_state.get("_BOOT_RESTORE_DONE"):
                return
    except Exception:
        pass

    p = effective_persist_dir()
    cj = p / "chunks.jsonl"
    ready = (p / ".ready").exists()
    if cj.exists() and cj.stat().st_size > 0 and ready:
        try:
            if "st" in globals() and st is not None:
                st.session_state["_BOOT_RESTORE_DONE"] = True
        except Exception:
            pass
        return

    # ---- 시크릿/ENV 로더 (SSOT) ----
    def _secret(name: str, default: str = "") -> str:
        try:
            if "st" in globals() and st is not None and hasattr(st, "secrets"):
                v = st.secrets.get(name)
                if isinstance(v, str) and v:
                    return v
        except Exception:
            pass
        return os.getenv(name, default)

    def _resolve_owner_repo() -> tuple[str, str]:
        # 우선순위: GH_OWNER/GH_REPO → GITHUB_REPO(=owner/repo) → GITHUB_OWNER/GITHUB_REPO_NAME
        owner = _secret("GH_OWNER") or _secret("GITHUB_OWNER")
        repo = _secret("GH_REPO") or _secret("GITHUB_REPO_NAME")
        combo = _secret("GITHUB_REPO")
        if (not owner or not repo) and combo and "/" in combo:
            o, r = combo.split("/", 1)
            owner, repo = o.strip(), r.strip()
        return owner or "", repo or ""

    token = _secret("GH_TOKEN") or _secret("GITHUB_TOKEN")
    owner, repo = _resolve_owner_repo()
    if not (token and owner and repo):
        return  # 복원 불가(시크릿 미설정)

    # ---- 최신 릴리스의 index_*.zip 다운로드 ----
    from urllib import request as _rq, error as _er, parse as _ps
    import zipfile
    import time
    import json as _json

    api_latest = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    try:
        req = _rq.Request(
            api_latest,
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
            },
        )
        with _rq.urlopen(req, timeout=20) as resp:
            data = _json.loads(resp.read().decode("utf-8", "ignore"))
    except Exception:
        return

    asset = None
    for a in data.get("assets") or []:
        n = str(a.get("name") or "")
        if n.startswith("index_") and n.endswith(".zip"):
            asset = a
            break
    if not asset:
        return

    dl = asset.get("browser_download_url")
    if not dl:
        return

    # ---- 저장 후 압축 해제 ----
    try:
        p.mkdir(parents=True, exist_ok=True)
        tmp = p / f"__restore_{int(time.time())}.zip"
        _rq.urlretrieve(dl, tmp)
        with zipfile.ZipFile(tmp, "r") as zf:
            zf.extractall(p)
        try:
            tmp.unlink()
        except Exception:
            pass

        # SSOT: 코어로 ready 마킹
        try:
            core_mark_ready(p)
        except Exception:
            try:
                (p / ".ready").write_text("ok", encoding="utf-8")
            except Exception:
                pass

        # 세션 플래그/경로 공유
        try:
            if "st" in globals() and st is not None:
                st.session_state["_PERSIST_DIR"] = p.resolve()
                st.session_state["_BOOT_RESTORE_DONE"] = True
        except Exception:
            pass
    except Exception:
        return
# =================== [10] 부팅 훅: 인덱스 자동 복원 — END =====================

# =================== [11] 부팅 오토플로우 & 자동 복원 모드 ==================
def _boot_autoflow_hook() -> None:
    """앱 부팅 시 1회 오토 플로우 실행(관리자=대화형, 학생=자동)."""
    try:
        mod = None
        for name in ("src.ui_orchestrator", "ui_orchestrator"):
            try:
                mod = importlib.import_module(name)
                break
            except Exception:
                mod = None
        if mod and hasattr(mod, "autoflow_boot_check"):
            mod.autoflow_boot_check(interactive=_is_admin_view())
    except Exception as e:
        _errlog(f"boot_autoflow_hook: {e}", where="[boot_hook]", exc=e)


def _set_brain_status(
    code: str, msg: str, source: str = "", attached: bool = False
) -> None:
    if st is None:
        return
    ss = st.session_state
    ss["brain_status_code"] = code
    ss["brain_status_msg"] = msg
    ss["brain_source"] = source
    ss["brain_attached"] = bool(attached)
    ss["restore_recommend"] = code in ("MISSING", "ERROR")
    ss.setdefault("index_decision_needed", False)
    ss.setdefault("index_change_stats", {})


def _auto_start_once() -> None:
    """AUTO_START_MODE에 따른 1회성 자동 복원.
    - restore|on 이면 최신 Release에서 인덱스 복구 시도
    - 성공 시 READY로 상태 업데이트 및 1회 rerun
    """
    try:
        if st is None or not hasattr(st, "session_state"):
            return
        if st.session_state.get("_auto_start_done"):
            return
        st.session_state["_auto_start_done"] = True
    except Exception:
        return

    mode = (
        os.getenv("AUTO_START_MODE")
        or _from_secrets("AUTO_START_MODE", "off")
        or "off"
    ).lower()
    if mode not in ("restore", "on"):
        return

    # releases 모듈이 있으면 사용하고, 없으면 [10] 훅 로직으로 폴백
    try:
        rel = importlib.import_module("src.backup.github_release")
        fn = getattr(rel, "restore_latest", None)
    except Exception:
        fn = None

    used_persist = effective_persist_dir()
    ok = False
    if callable(fn):
        try:
            ok = bool(fn(dest_dir=used_persist))
        except Exception as e:
            _errlog(f"restore_latest failed: {e}", where="[auto_start]", exc=e)
            ok = False
    else:
        # 폴백: [10] 훅을 직접 실행
        try:
            _boot_auto_restore_index()
            ok = core_is_ready(used_persist)
        except Exception:
            ok = False

    if ok:
        try:
            core_mark_ready(used_persist)
        except Exception:
            pass
        if hasattr(st, "toast"):
            st.toast("자동 복원 완료", icon="✅")
        else:
            st.success("자동 복원 완료")
        _set_brain_status("READY", "자동 복원 완료", "release", attached=True)
        _safe_rerun("auto_start", ttl=1)


# =================== [12C] DIAG: Ready Probe — START ====================
-def _probe_index_health(p: Path) -> Dict[str, Any]:
-    """인덱스 준비상태를 경량 검증한다.
-    체크 항목:
-      - chunks.jsonl 존재/크기
-      - .ready 존재
-      - JSON 샘플 파싱(최대 200줄) 오류율
-    """
-    res: Dict[str, Any] = {"persist": str(p)}
-    try:
-        cj = p / "chunks.jsonl"
-        res["chunks_exists"] = cj.exists()
-        res["chunks_size"] = cj.stat().st_size if cj.exists() else 0
-        res["ready_exists"] = (p / ".ready").exists()
-        res["mtime"] = int(cj.stat().st_mtime) if cj.exists() else 0
-    except Exception:
-        res["chunks_exists"] = False
-        res["chunks_size"] = 0
-        res["ready_exists"] = False
-        res["mtime"] = 0
-
-    # JSON 샘플 검사(최대 200줄)
-    sample = 0
-    malformed = 0
-    try:
-        cj = p / "chunks.jsonl"
-        if cj.exists() and cj.stat().st_size > 0:
-            with cj.open("r", encoding="utf-8") as rf:
-                for i, line in enumerate(rf):
-                    if i >= 200:
-                        break
-                    s = line.strip()
-                    if not s:
-                        continue
-                    sample += 1
-                    try:
-                        json.loads(s)
-                    except Exception:
-                        malformed += 1
-
-        res["json_sample"] = sample
-        res["json_malformed"] = malformed
-        json_ok = (sample == 0) or (malformed == 0)
-        res["ok"] = bool(res["ready_exists"] and res["chunks_exists"] and (res["chunks_size"] > 0) and json_ok)
-        return res
-    except Exception:
-        return {
-            "persist": str(p),
-            "chunks_exists": False,
-            "chunks_size": 0,
-            "ready_exists": False,
-            "json_sample": 0,
-            "json_malformed": 0,
-            "ok": False,
-        }
-
-def _render_ready_probe() -> None:
-    """READY 여부를 미니멀 Pill로 시각화 + 상세는 expander."""
-    if st is None:
-        return
-
-    p = _effective_persist_dir()
-    info = _probe_index_health(p)
-    size = int(info.get("chunks_size", 0) or 0)
-    ready = bool(info.get("ready_exists"))
-    json_ok = bool((int(info.get("json_sample", 0) or 0) > 0) and int(info.get("json_malformed", 0) or 0) == 0)
-    ok = bool(ready and bool(info.get("chunks_exists")) and size > 0 and json_ok)
-
-    level = "HIGH" if ok else ("MID" if (size > 0 and json_ok) else "LOW")
-    badge = "🟢" if ok else ("🟡" if (size > 0 or ready or json_ok) else "🔴")
-
-    st.markdown(
-        """
-        <style>
-          .probe-pill{
-            display:inline-flex; align-items:center; gap:8px;
-            padding:6px 10px; border-radius:14px;
-            border:1px solid #dbeafe; background:#eff6ff;
-            font-weight:700; color:#0a2540;
-          }
-          .dot{ width:8px; height:8px; border-radius:50%;
-                background:#16a34a; box-shadow:0 0 0 0 rgba(22,163,74,.7);
-                animation:pulse 1.5s infinite; }
-          .dot.warn{ background:#f59e0b; box-shadow:0 0 0 0 rgba(245,158,11,.6); }
-          .dot.err{ background:#ef4444; box-shadow:0 0 0 0 rgba(239,68,68,.6); }
-          @keyframes pulse{
-            0%{ box-shadow:0 0 0 0 rgba(22,163,74,.7); }
-            70%{ box-shadow:0 0 0 10px rgba(22,163,74,0); }
-            100%{ box-shadow:0 0 0 0 rgba(22,163,74,0); }
-          }
-        </style>
-        """,
-        unsafe_allow_html=True,
-    )
-    dot_class = "dot" if level == "HIGH" else ("dot warn" if level == "MID" else "dot err")
-    pill_html = (
-        f'<span class="probe-pill">{badge} Ready Probe '
-        f'<span class="{dot_class}"></span><span>{level}</span></span>'
-    )
-    st.markdown(pill_html, unsafe_allow_html=True)
-
-    with st.expander("세부 상태 보기", expanded=False):
-        rows = [
-            ("Persist", str(info.get("persist"))),
-            ("chunks.jsonl", "OK" if info.get("chunks_exists") else "Missing"),
-            ("size", f"{int(info.get('chunks_size',0)): ,} bytes"),
-            (".ready", "OK" if info.get("ready_exists") else "Missing"),
-            ("JSON 샘플", f"{int(info.get('json_sample',0))} lines · malformed {int(info.get('json_malformed',0))}"),
-        ]
-        data = [{"항목": k, "상태": v} for k, v in rows]
-        st.dataframe(data, hide_index=True, use_container_width=True)
+def _render_ready_probe() -> None:
+    """READY 여부를 미니멀 Pill로 시각화 + 상세는 expander.
+    SSOT: src.core.index_probe.probe_index_health(IndexHealth)
+    - 코어 호출 실패 시, 존재/크기만 간소 폴백
+    """
+    if st is None:
+        return
+
+    p = _effective_persist_dir()
+
+    # --- SSOT 호출 시도 ---
+    info = None
+    try:
+        from src.core.index_probe import IndexHealth, probe_index_health  # lazy import
+        info = probe_index_health(persist=p)
+        size = int(getattr(info, "chunks_size", 0) or 0)
+        ready = bool(getattr(info, "ready_exists", False))
+        json_ok = bool(
+            (int(getattr(info, "json_sample", 0) or 0) > 0)
+            and int(getattr(info, "json_malformed", 0) or 0) == 0
+        )
+        ok = bool(ready and bool(getattr(info, "chunks_exists", False)) and size > 0 and json_ok)
+    except Exception:
+        # --- 폴백: 존재/크기만 점검 ---
+        cj = p / "chunks.jsonl"
+        size = cj.stat().st_size if cj.exists() else 0
+        ready = (p / ".ready").exists()
+        json_ok = True  # 샘플 검증 불가 시 보수적 True
+        ok = bool(ready and size > 0)
+
+    level = "HIGH" if ok else ("MID" if (size > 0 and json_ok) else "LOW")
+    badge = "🟢" if ok else ("🟡" if (size > 0 or ready or json_ok) else "🔴")
+
+    # CSS (펄스 점 포함)
+    st.markdown(
+        """
+        <style>
+          .probe-pill{
+            display:inline-flex; align-items:center; gap:8px;
+            padding:6px 10px; border-radius:14px;
+            border:1px solid #dbeafe; background:#eff6ff;
+            font-weight:700; color:#0a2540;
+          }
+          .dot{ width:8px; height:8px; border-radius:50%;
+                background:#16a34a; box-shadow:0 0 0 0 rgba(22,163,74,.7);
+                animation:pulse 1.5s infinite; }
+          .dot.warn{ background:#f59e0b; box-shadow:0 0 0 0 rgba(245,158,11,.6); }
+          .dot.err{ background:#ef4444; box-shadow:0 0 0 0 rgba(239,68,68,.6); }
+          @keyframes pulse{
+            0%{ box-shadow:0 0 0 0 rgba(22,163,74,.7); }
+            70%{ box-shadow:0 0 0 10px rgba(22,163,74,0); }
+            100%{ box-shadow:0 0 0 0 rgba(22,163,74,0); }
+          }
+        </style>
+        """,
+        unsafe_allow_html=True,
+    )
+    dot_class = "dot" if level == "HIGH" else ("dot warn" if level == "MID" else "dot err")
+    pill_html = (
+        f'<span class="probe-pill">{badge} Ready Probe '
+        f'<span class="{dot_class}"></span><span>{level}</span></span>'
+    )
+    st.markdown(pill_html, unsafe_allow_html=True)
+
+    # 상세 표(SSOT 사용 시 풍부)
+    with st.expander("세부 상태 보기", expanded=False):
+        if info is not None:
+            rows = [
+                ("Persist", str(getattr(info, "persist", p))),
+                ("chunks.jsonl", "OK" if getattr(info, "chunks_exists", False) else "Missing"),
+                ("size", f"{int(getattr(info, 'chunks_size', 0)): ,} bytes"),
+                (".ready", "OK" if getattr(info, "ready_exists", False) else "Missing"),
+                ("JSON 샘플", f"{int(getattr(info, 'json_sample', 0))} lines · malformed {int(getattr(info, 'json_malformed', 0))}"),
+            ]
+        else:
+            rows = [
+                ("Persist", str(p)),
+                ("chunks.jsonl", "OK" if (p / "chunks.jsonl").exists() else "Missing"),
+                ("size", f"{size: ,} bytes"),
+                (".ready", "OK" if (p / ".ready").exists() else "Missing"),
+            ]
+        data = [{"항목": k, "상태": v} for k, v in rows]
+        st.dataframe(data, hide_index=True, use_container_width=True)
 # =================== [12C] DIAG: Ready Probe — END ====================



# =================== [13] ADMIN: Index Panel (prepared 전용) ==============
def _render_admin_index_panel() -> None:
    if "st" not in globals() or st is None or not _is_admin_view():
        return

    from typing import List, Dict, Any, Optional, Tuple
    import importlib as _imp

    st.markdown("<h3>🧭 인덱싱(관리자: prepared 전용)</h3>", unsafe_allow_html=True)

    # ---------- 공용 헬퍼 ----------
    def _persist_dir_safe() -> Path:
        try:
            return _effective_persist_dir()
        except Exception:
            return Path.home() / ".maic" / "persist"

    def _stamp_persist(p: Path) -> None:
        try:
            st.session_state["_PERSIST_DIR"] = p.resolve()
        except Exception:
            pass

    # ---------- 스텝/로그 ----------
    if "_IDX_PH_STEPS" not in st.session_state:
        st.session_state["_IDX_PH_STEPS"] = st.empty()
    if "_IDX_PH_STATUS" not in st.session_state:
        st.session_state["_IDX_PH_STATUS"] = st.empty()
    if "_IDX_PH_BAR" not in st.session_state:
        st.session_state["_IDX_PH_BAR"] = st.empty()
    if "_IDX_PH_LOG" not in st.session_state:
        st.session_state["_IDX_PH_LOG"] = st.empty()
    if "_IDX_PH_S6" not in st.session_state:
        st.session_state["_IDX_PH_S6"] = st.empty()

    step_names: List[str] = ["스캔", "Persist확정", "인덱싱", "prepared소비", "요약/배지", "ZIP/Release"]
    stall_threshold_sec = 60

    def _step_reset(names: List[str]) -> None:
        st.session_state["_IDX_STEPS"] = [{"name": n, "state": "idle", "note": ""} for n in names]
        st.session_state["_IDX_LOG"] = []
        st.session_state["_IDX_PROG"] = 0.0
        st.session_state["_IDX_START_TS"] = time.time()
        st.session_state["_IDX_LAST_TS"] = time.time()
        st.session_state["_IDX_PH_S6"].empty()
        st.session_state["_IDX_S6_BAR"] = None

    def _steps() -> List[Dict[str, str]]:
        if "_IDX_STEPS" not in st.session_state:
            _step_reset(step_names)
        return list(st.session_state["_IDX_STEPS"])

    def _icon(state: str) -> str:
        return {"idle": "⚪", "run": "🔵", "ok": "🟢", "fail": "🔴", "skip": "⚪"}.get(state, "⚪")

    def _render_stepper() -> None:
        lines: List[str] = []
        for i, s in enumerate(_steps(), start=1):
            note = f" — {s.get('note','')}" if s.get("note") else ""
            lines.append(f"{_icon(s['state'])} {i}. {s['name']}{note}")
        st.session_state["_IDX_PH_STEPS"].markdown("\n".join(f"- {ln}" for ln in lines))

    def _update_progress() -> None:
        steps = _steps()
        done = sum(1 for s in steps if s["state"] in ("ok", "skip"))
        prog = done / len(steps)
        bar = st.session_state.get("_IDX_BAR")
        if bar is None:
            st.session_state["_IDX_BAR"] = st.session_state["_IDX_PH_BAR"].progress(prog, text="진행률")
        else:
            try:
                bar.progress(prog)
            except Exception:
                st.session_state["_IDX_BAR"] = st.session_state["_IDX_PH_BAR"].progress(prog, text="진행률")

    def _render_status() -> None:
        now = time.time()
        last = float(st.session_state.get("_IDX_LAST_TS", now))
        start = float(st.session_state.get("_IDX_START_TS", now))
        since_last = int(now - last)
        since_start = int(now - start)
        running = any(s["state"] == "run" for s in _steps())
        stalled = running and since_last >= stall_threshold_sec
        if stalled:
            text = f"🟥 **STALLED** · 마지막 업데이트 {since_last}s 전 · 총 경과 {since_start}s"
        elif running:
            text = f"🟦 RUNNING · 마지막 업데이트 {since_last}s 전 · 총 경과 {since_start}s"
        else:
            text = f"🟩 IDLE/COMPLETE · 총 경과 {since_start}s"
        st.session_state["_IDX_PH_STATUS"].markdown(text)

    def _step_set(idx: int, state: str, note: str = "") -> None:
        steps = _steps()
        if 0 <= idx < len(steps):
            steps[idx]["state"] = state
            if note:
                steps[idx]["note"] = note
            st.session_state["_IDX_STEPS"] = steps
            st.session_state["_IDX_LAST_TS"] = time.time()
            _render_stepper()
            _update_progress()
            _render_status()

    def _log(msg: str, level: str = "info") -> None:
        buf: List[str] = st.session_state.get("_IDX_LOG", [])
        prefix = {"info": "•", "warn": "⚠", "err": "✖"}.get(level, "•")
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {prefix} {msg}"
        buf.append(line)
        if len(buf) > 200:
            buf = buf[-200:]
        st.session_state["_IDX_LOG"] = buf
        st.session_state["_IDX_PH_LOG"].text("\n".join(buf))
        st.session_state["_IDX_LAST_TS"] = time.time()
        _render_status()

    # ---- 6단계 미니 진행 표시 ----
    def _s6_progress(label: str, cur: int, total: int) -> None:
        total = max(total, 1)
        frac = min(max(cur / total, 0.0), 1.0)
        bar = st.session_state.get("_IDX_S6_BAR")
        if bar is None:
            ph = st.session_state["_IDX_PH_S6"]
            bar = ph.progress(0.0, text="6단계 진행")
            st.session_state["_IDX_S6_BAR"] = bar
        try:
            bar.progress(frac)
        except Exception:
            ph = st.session_state["_IDX_PH_S6"]
            st.session_state["_IDX_S6_BAR"] = ph.progress(frac, text="6단계 진행")
        st.session_state["_IDX_LAST_TS"] = time.time()
        st.session_state["_IDX_PH_S6"].markdown(
            f"**6. {label}** — {cur:,} / {total:,} ({int(frac * 100)}%)"
        )

    # ---------- prepared 목록 스캔 ----------
    st.caption("※ 이 패널은 Drive의 prepared만을 입력원으로 사용합니다.")

    def _load_prepared_lister():
        tried = []

        def _try(modname: str):
            try:
                m = _imp.import_module(modname)
                fn = getattr(m, "list_prepared_files", None)
                if callable(fn):
                    tried.append(f"ok: {modname}")
                    return fn
                tried.append(f"miss func: {modname}")
                return None
            except Exception as e:
                tried.append(f"fail: {modname} ({e})")
                return None

        for name in ("src.integrations.gdrive", "gdrive"):
            fn = _try(name)
            if fn:
                return fn, tried
        return None, tried

    files_list: List[Dict[str, Any]] = []
    lister, dbg1 = _load_prepared_lister()
    if lister:
        try:
            files_list = lister() or []
        except Exception as e:
            _log(f"prepared list failed: {e}", "err")
    else:
        for m in dbg1:
            _log("• " + m, "warn")
    prepared_count = len(files_list)
    _step_set(0, "ok", f"{prepared_count}건")

    with st.expander("이번에 인덱싱할 prepared 파일(예상)", expanded=False):
        st.write(f"총 {prepared_count}건 (표시는 최대 400건)")
        if prepared_count:
            rows = []
            for rec in files_list[:400]:
                name = str(rec.get("name") or rec.get("path") or rec.get("file") or "")
                fid = str(rec.get("id") or rec.get("fileId") or "")
                rows.append({"name": name, "id": fid})
            st.dataframe(rows, hide_index=True, use_container_width=True)
        else:
            st.caption("일치하는 파일이 없습니다.")

    # ---------- 실행 컨트롤 ----------
    with st.form("idx_actions_form", clear_on_submit=False):
        c1, c2, c3, c4 = st.columns([1, 2, 2, 1])
        submit_reindex = c1.form_submit_button(
            "🔁 강제 재인덱싱(HQ, prepared)", use_container_width=True
        )
        show_after = c2.toggle("인덱싱 결과 표시", key="IDX_SHOW_AFTER", value=True)
        auto_up = c3.toggle(
            "인덱싱 후 자동 ZIP 업로드",
            key="IDX_AUTO_UP",
            value=False,
            help="GH/GITHUB 시크릿이 모두 있으면 켜짐",
        )
        reset_view = c4.form_submit_button("🧹 화면 초기화")

        if reset_view:
            _step_reset(step_names)
            st.session_state["_IDX_BAR"] = None
            st.session_state["_IDX_PH_BAR"].empty()
            st.session_state["_IDX_PH_LOG"].empty()
            _log("화면 상태를 초기화했습니다.")

        if submit_reindex:
            st.session_state["_IDX_REQ"] = {
                "ts": time.time(),
                "auto_up": auto_up,
                "show_after": show_after,
            }
            _log("인덱싱 요청 접수")
            st.rerun()

    # ---------- 인덱싱 실행 ----------
    req = st.session_state.pop("_IDX_REQ", None)
    if req:
        used_persist = _persist_dir_safe()
        _step_reset(step_names)
        _render_stepper()
        _render_status()
        st.session_state["_IDX_PH_BAR"].empty()
        st.session_state["_IDX_BAR"] = None
        _log("인덱싱 시작")
        try:
            from src.rag import index_build as _idx  # 내부 인덱서

            _step_set(1, "run", "persist 확인 중")
            try:
                from src.rag.index_build import PERSIST_DIR as _pp
                used_persist = Path(str(_pp)).expanduser()
            except Exception:
                pass
            _step_set(1, "ok", str(used_persist))
            _log(f"persist={used_persist}")

            _step_set(2, "run", "HQ 인덱싱 중")
            os.environ["MAIC_INDEX_MODE"] = "HQ"
            os.environ["MAIC_USE_PREPARED_ONLY"] = "1"
            _idx.rebuild_index()
            _step_set(2, "ok", "완료")
            _log("인덱싱 완료")

            # 산출물 확인 및 보정(하위 폴더 자동 채택)
            cj = used_persist / "chunks.jsonl"
            if not (cj.exists() and cj.stat().st_size > 0):
                try:
                    cand = next(used_persist.glob("**/chunks.jsonl"))
                    used_persist = cand.parent
                    cj = cand
                    _log(f"산출물 위치 자동조정: {used_persist}")
                except StopIteration:
                    pass
            if cj.exists() and cj.stat().st_size > 0:
                try:
                    (used_persist / ".ready").write_text("ok", encoding="utf-8")
                except Exception:
                    pass
                _stamp_persist(used_persist)

            # prepared 소비
            _step_set(3, "run", "prepared 소비 중")
            try:
                def _load_prepared_api():
                    tried2 = []

                    def _try(modname: str):
                        try:
                            m = _imp.import_module(modname)
                            chk_fn = getattr(m, "check_prepared_updates", None)
                            mark_fn = getattr(m, "mark_prepared_consumed", None)
                            if callable(chk_fn) and callable(mark_fn):
                                tried2.append(f"ok: {modname}")
                                return chk_fn, mark_fn
                            tried2.append(f"miss attrs: {modname}")
                            return None, None
                        except Exception as e:
                            tried2.append(f"fail: {modname} ({e})")
                            return None, None

                    for name in ("prepared", "gdrive"):
                        chk, mark = _try(name)
                        if chk and mark:
                            return chk, mark, tried2
                    for name in ("src.prepared", "src.drive.prepared", "src.integrations.gdrive"):
                        chk, mark = _try(name)
                        if chk and mark:
                            return chk, mark, tried2
                    return None, None, tried2

                chk, mark, dbg2 = _load_prepared_api()
                persist_for_seen = used_persist
                info: Dict[str, Any] = {}
                new_files: List[str] = []
                if callable(chk):
                    try:
                        info = chk(persist_for_seen, files_list) or {}
                    except TypeError:
                        info = chk(persist_for_seen) or {}
                    new_files = list(info.get("files") or [])
                else:
                    for m in dbg2:
                        _log("• " + m, "warn")
                if new_files and callable(mark):
                    try:
                        mark(persist_for_seen, new_files)
                    except TypeError:
                        mark(new_files)
                    _log(f"소비(seen) {len(new_files)}건")
                _step_set(3, "ok", f"{len(new_files)}건")
            except Exception as e:
                _step_set(3, "fail", "소비 실패")
                _log(f"prepared 소비 실패: {e}", "err")

            # 요약
            _step_set(4, "run", "요약 계산")
            try:
                from src.rag.index_status import get_index_summary
                s2 = get_index_summary(used_persist)
                _step_set(4, "ok", f"files={s2.total_files}, chunks={s2.total_chunks}")
                _log(f"요약 files={s2.total_files}, chunks={s2.total_chunks}")
            except Exception:
                _step_set(4, "ok", "요약 모듈 없음")
                _log("요약 모듈 없음", "warn")

            # ZIP/Release
            if req.get("auto_up"):
                _step_set(5, "run", "ZIP/Release 업로드")

                def _secret(name: str, default: str = "") -> str:
                    try:
                        v = st.secrets.get(name)
                        if isinstance(v, str) and v:
                            return v
                    except Exception:
                        pass
                    return os.getenv(name, default)

                def _resolve_owner_repo() -> Tuple[str, str]:
                    owner = _secret("GH_OWNER")
                    repo = _secret("GH_REPO")
                    if owner and repo:
                        return owner, repo
                    combo = _secret("GITHUB_REPO")
                    if combo and "/" in combo:
                        o, r = combo.split("/", 1)
                        return o.strip(), r.strip()
                    owner = owner or _secret("GITHUB_OWNER")
                    repo = repo or _secret("GITHUB_REPO_NAME")
                    return owner or "", repo or ""

                tok = _secret("GH_TOKEN") or _secret("GITHUB_TOKEN")
                ow, rp = _resolve_owner_repo()
                if tok and ow and rp:
                    from urllib import request as _rq, error as _er, parse as _ps
                    import zipfile

                    def _gh_api(url: str, token_: str, data: Optional[bytes], method: str, ctype: str) -> Dict[str, Any]:
                        req = _rq.Request(url, data=data, method=method)
                        req.add_header("Authorization", f"token {token_}")
                        req.add_header("Accept", "application/vnd.github+json")
                        if ctype:
                            req.add_header("Content-Type", ctype)
                        try:
                            with _rq.urlopen(req, timeout=30) as resp:
                                txt = resp.read().decode("utf-8", "ignore")
                                try:
                                    return json.loads(txt)
                                except Exception:
                                    return {"_raw": txt}
                        except _er.HTTPError as e:
                            return {"_error": f"HTTP {e.code}", "detail": e.read().decode()}
                        except Exception:
                            return {"_error": "network_error"}

                    def _upload_release_zip(owner: str, repo: str, token: str, tag: str, zip_path: Path, name: Optional[str] = None, body: str = "") -> Dict[str, Any]:
                        api = "https://api.github.com"
                        get_url = f"{api}/repos/{owner}/{repo}/releases/tags/{_ps.quote(tag)}"
                        rel = _gh_api(get_url, token, None, "GET", "")
                        if "_error" in rel:
                            payload = json.dumps({"tag_name": tag, "name": name or tag, "body": body}).encode("utf-8")
                            rel = _gh_api(f"{api}/repos/{owner}/{repo}/releases", token, payload, "POST", "application/json")
                            if "_error" in rel:
                                return rel
                        rid = rel.get("id")
                        if not rid:
                            return {"_error": "no_release_id"}

                        up_url = f"https://uploads.github.com/repos/{owner}/{repo}/releases/{rid}/assets?name={_ps.quote(zip_path.name)}"
                        data = zip_path.read_bytes()
                        req = _rq.Request(up_url, data=data, method="POST")
                        req.add_header("Authorization", f"token {token}")
                        req.add_header("Content-Type", "application/zip")
                        req.add_header("Accept", "application/vnd.github+json")
                        with _rq.urlopen(req, timeout=180) as resp:
                            txt = resp.read().decode("utf-8", "ignore")
                            try:
                                return json.loads(txt)
                            except Exception:
                                return {"_raw": txt}

                    backup_dir = used_persist / "backups"
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    z = backup_dir / f"index_{int(time.time())}.zip"
                    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
                        for root, _d, _f in os.walk(str(used_persist)):
                            for fn in _f:
                                pth = Path(root) / fn
                                zf.write(str(pth), arcname=str(pth.relative_to(used_persist)))

                    tag = f"index-{int(time.time())}"
                    res = _upload_release_zip(ow, rp, tok, tag, z, name=tag, body="MAIC index")
                    if "_error" in res:
                        _step_set(5, "fail", res.get("_error", "error"))
                    else:
                        _step_set(5, "ok", "업로드 완료")
                else:
                    _step_set(5, "skip", "시크릿 없음")

            st.success("강제 재인덱싱 완료 (prepared 전용)")
        except Exception as e:
            _step_set(2, "fail", "인덱싱 실패")
            _log(f"인덱싱 실패: {e}", "err")

    # ---------- 인덱싱 후 요약/경로 ----------
    if bool(st.session_state.get("IDX_SHOW_AFTER", True)):
        idx_persist = _persist_dir_safe()
        glb_persist = _persist_dir_safe()
        st.write(f"**Persist(Indexer):** `{str(idx_persist)}`")
        st.write(f"**Persist(Global):** `{str(glb_persist)}`")
        try:
            from src.rag.index_status import get_index_summary
            s = get_index_summary(idx_persist)
            ready_txt = "Yes" if s.ready else "No"
            st.caption(f"요약: ready={ready_txt} · files={s.total_files} · chunks={s.total_chunks}")
            if s.sample_files:
                with st.expander("샘플 파일(최대 3개)", expanded=False):
                    rows = [{"path": x} for x in s.sample_files]
                    st.dataframe(rows, hide_index=True, use_container_width=True)
        except Exception:
            cj = idx_persist / "chunks.jsonl"
            if cj.exists():
                st.caption("요약 모듈 없음: chunks.jsonl 존재")
                if not (idx_persist / ".ready").exists():
                    st.info(".ready 파일이 없어 준비 상태가 미완성입니다.")
            else:
                st.info("`chunks.jsonl`이 아직 없어 결과를 표시할 수 없습니다.")

    with st.expander("실시간 로그 (최근 200줄)", expanded=False):
        buf = st.session_state.get("_IDX_LOG", [])
        if buf:
            st.text("\n".join(buf))
        else:
            st.caption("표시할 로그가 없습니다.")


# ========== [13A] ADMIN: Panels (legacy aggregator, no-op) ==========
def _render_admin_panels() -> None:
    """과거 집계 렌더러 호환용(현재는 사용 안함)."""
    return None
# =================== [13B] ADMIN: Prepared Scan — START ====================
def _render_admin_prepared_scan_panel() -> None:
    """prepared 폴더의 '새 파일 유무'만 확인하는 경량 스캐너.
    - 인덱싱은 수행하지 않고, check_prepared_updates()만 호출
    - 결과: 새 파일 개수, 샘플 목록, 디버그 경로
    """
    if st is None or not _is_admin_view():
        return

    import importlib as _imp
    from typing import Any, Dict, List, Optional, Tuple

    st.markdown("<h4>🔍 새 파일 스캔(인덱싱 없이)</h4>", unsafe_allow_html=True)

    def _persist_dir_safe() -> Path:
        try:
            return _effective_persist_dir()
        except Exception:
            return Path.home() / ".maic" / "persist"

    # prepared 파일 나열 함수 로드
    def _load_prepared_lister():
        tried = []

        def _try(modname: str):
            try:
                m = _imp.import_module(modname)
                fn = getattr(m, "list_prepared_files", None)
                if callable(fn):
                    tried.append(f"ok: {modname}")
                    return fn
                tried.append(f"miss func: {modname}")
                return None
            except Exception as e:
                tried.append(f"fail: {modname} ({e})")
                return None

        for name in ("src.integrations.gdrive", "gdrive"):
            fn = _try(name)
            if fn:
                return fn, tried
        return None, tried

    # prepared 소비 API 로드(check/mark)
    def _load_prepared_api():
        tried2 = []

        def _try(modname: str):
            try:
                m = _imp.import_module(modname)
                chk_fn = getattr(m, "check_prepared_updates", None)
                mark_fn = getattr(m, "mark_prepared_consumed", None)
                if callable(chk_fn) and callable(mark_fn):
                    tried2.append(f"ok: {modname}")
                    return chk_fn, mark_fn
                tried2.append(f"miss attrs: {modname}")
                return None, None
            except Exception as e:
                tried2.append(f"fail: {modname} ({e})")
                return None, None

        for name in ("prepared", "gdrive"):
            chk, mark = _try(name)
            if chk and mark:
                return chk, mark, tried2
        for name in ("src.prepared", "src.drive.prepared", "src.integrations.gdrive"):
            chk, mark = _try(name)
            if chk and mark:
                return chk, mark, tried2
        return None, None, tried2

    # --- 실행 UI ---
    c1, c2, c3 = st.columns([1, 1, 2])
    act_scan = c1.button("🔍 스캔 실행", use_container_width=True)
    act_clear = c2.button("🧹 화면 지우기", use_container_width=True)

    if act_clear:
        st.session_state.pop("_PR_SCAN_RESULT", None)
        st.experimental_rerun()

    # 이전 결과 있으면 보여주기
    prev = st.session_state.get("_PR_SCAN_RESULT")
    if isinstance(prev, dict) and not act_scan:
        st.caption("이전에 실행한 스캔 결과:")
        st.json(prev)

    if not act_scan:
        return

    # --- 스캔 로직 ---
    idx_persist = _persist_dir_safe()

    lister, dbg1 = _load_prepared_lister()
    files_list: List[Dict[str, Any]] = []
    if lister:
        try:
            files_list = lister() or []
        except Exception as e:
            st.error(f"prepared 목록 조회 실패: {e}")
    else:
        with st.expander("디버그(파일 나열 함수 로드 경로)"):
            st.write("\n".join(dbg1) or "(정보 없음)")

    chk, _mark, dbg2 = _load_prepared_api()
    info: Dict[str, Any] = {}
    new_files: List[str] = []
    if callable(chk):
        try:
            # 새로운 인터페이스(파일목록 전달) 시도
            info = chk(idx_persist, files_list) or {}
        except TypeError:
            # 구버전(경로만 전달)
            info = chk(idx_persist) or {}
        except Exception as e:
            st.error(f"스캔 실행 실패: {e}")
            info = {}
        try:
            # 표준 키: 'files' (없으면 fallback)
            new_files = list(info.get("files") or info.get("new") or [])
        except Exception:
            new_files = []
    else:
        with st.expander("디버그(소비 API 로드 경로)"):
            st.write("\n".join(dbg2) or "(정보 없음)")

    # --- 결과 표시 ---
    total_prepared = len(files_list)
    total_new = len(new_files)
    st.success(f"스캔 완료 · prepared 총 {total_prepared}건 · **새 파일 {total_new}건**")

    if total_new:
        with st.expander("새 파일 미리보기(최대 50개)"):
            rows = []
            for rec in (new_files[:50] if isinstance(new_files, list) else []):
                # 항목이 문자열(경로/이름)일 수도 있고 dict일 수도 있으므로 방어적 처리
                if isinstance(rec, str):
                    rows.append({"name": rec})
                elif isinstance(rec, dict):
                    nm = str(rec.get("name") or rec.get("path") or rec.get("file") or "")
                    fid = str(rec.get("id") or rec.get("fileId") or "")
                    rows.append({"name": nm, "id": fid})
            if rows:
                st.dataframe(rows, hide_index=True, use_container_width=True)
            else:
                st.write("(표시할 항목이 없습니다.)")
    else:
        st.info("새 파일이 없습니다. 재인덱싱을 수행할 필요가 없습니다.")

    # 세션에 저장(새로고침해도 유지)
    st.session_state["_PR_SCAN_RESULT"] = {
        "persist": str(idx_persist),
        "prepared_total": total_prepared,
        "new_total": total_new,
        "timestamp": int(time.time()),
        "sample_new": new_files[:10] if isinstance(new_files, list) else [],
    }
# =================== [13B] ADMIN: Prepared Scan — END ====================


# ============= [14] 인덱싱된 소스 목록(읽기 전용 대시보드) ==============
def _render_admin_indexed_sources_panel() -> None:
    """현재 인덱스(chunks.jsonl)를 읽어 문서 단위로 집계/표시."""
    if st is None or not _is_admin_view():
        return

    chunks_path = _effective_persist_dir() / "chunks.jsonl"
    with st.container(border=True):
        st.subheader("📄 인덱싱된 파일 목록 (읽기 전용)")
        st.caption(f"경로: `{str(chunks_path)}`")

        if not chunks_path.exists():
            st.info("아직 인덱스가 없습니다. 먼저 인덱싱을 수행해 주세요.")
            return

        docs: Dict[str, Dict[str, Any]] = {}
        total_lines: int = 0
        parse_errors: int = 0

        try:
            with chunks_path.open("r", encoding="utf-8") as rf:
                for line in rf:
                    s = line.strip()
                    if not s:
                        continue
                    total_lines += 1
                    try:
                        obj = json.loads(s)
                    except Exception:
                        parse_errors += 1
                        continue
                    doc_id = str(obj.get("doc_id") or obj.get("source") or "")
                    title = str(obj.get("title") or "")
                    source = str(obj.get("source") or "")
                    if not doc_id:
                        continue
                    row = docs.setdefault(
                        doc_id,
                        {"doc_id": doc_id, "title": title, "source": source, "chunks": 0},
                    )
                    row["chunks"] += 1
        except Exception as e:
            _errlog(
                f"read chunks.jsonl failed: {e}",
                where="[indexed-sources.read]",
                exc=e,
            )
            st.error("인덱스 파일을 읽는 중 오류가 발생했어요.")
            return

        table: List[Dict[str, Any]] = list(docs.values())
        st.caption(
            f"총 청크 수: **{total_lines}** · 문서 수: **{len(table)}** "
            f"(파싱오류 {parse_errors}건)"
        )
        rows2 = [
            {
                "title": r["title"],
                "path": r["source"],
                "doc_id": r["doc_id"],
                "chunks": r["chunks"],
            }
            for r in table
        ]
        st.dataframe(rows2, hide_index=True, use_container_width=True)


# ===================== [15] 채팅 UI(스타일/모드) ==========================
def _inject_chat_styles_once() -> None:
    """전역 CSS: 카톡형 입력, 말풍선/칩, 모드 pill."""
    if st is None:
        return
    if st.session_state.get("_chat_styles_injected_v2"):
        return
    st.session_state["_chat_styles_injected_v2"] = True

    st.markdown(
        """
    <style>
      .chatpane{
        position:relative; background:#EDF4FF; border:1px solid #D5E6FF; border-radius:18px;
        padding:10px; margin-top:12px;
      }
      .chatpane .messages{ max-height:60vh; overflow-y:auto; padding:8px; }
      .chatpane div[data-testid="stRadio"]{ background:#EDF4FF; padding:8px 10px 0 10px; margin:0; }
      .chatpane div[data-testid="stRadio"] > div[role="radiogroup"]{ display:flex; gap:10px; flex-wrap:wrap; }
      .chatpane div[data-testid="stRadio"] [role="radio"]{
        border:2px solid #bcdcff; border-radius:12px; padding:6px 12px; background:#fff; color:#0a2540;
        font-weight:700; font-size:14px; line-height:1;
      }
      .chatpane div[data-testid="stRadio"] [role="radio"][aria-checked="true"]{
        background:#eaf6ff; border-color:#9fd1ff; color:#0a2540;
      }
      .chatpane div[data-testid="stRadio"] svg{ display:none!important }

      form[data-testid="stForm"]:has(input[placeholder='질문을 입력하세요…']) {
        position:relative; background:#EDF4FF; padding:8px 10px 10px 10px; margin:0;
      }
      form[data-testid="stForm"]:has(input[placeholder='질문을 입력하세요…'])
      [data-testid="stTextInput"] input{
        background:#FFF8CC !important; border:1px solid #F2E4A2 !important;
        border-radius:999px !important; color:#333 !important; height:46px; padding-right:56px;
      }
      form[data-testid="stForm"]:has(input[placeholder='질문을 입력하세요…']) ::placeholder{ color:#8A7F4A !important; }

      form[data-testid="stForm"]:has(input[placeholder='질문을 입력하세요…']) .stButton,
      form[data-testid="stForm"]:has(input[placeholder='질문을 입력하세요…']) .row-widget.stButton{
        position:absolute; right:14px; top:50%; transform:translateY(-50%);
        z-index:2; margin:0!important; padding:0!important;
      }
      form[data-testid="stForm"]:has(input[placeholder='질문을 입력하세요…']) .stButton > button,
      form[data-testid="stForm"]:has(input[placeholder='질문을 입력하세요…']) .row-widget.stButton > button{
        width:38px; height:38px; border-radius:50%; border:0; background:#0a2540; color:#fff;
        font-size:18px; line-height:1; cursor:pointer; box-shadow:0 2px 6px rgba(0,0,0,.15);
        padding:0; min-height:0;
      }

      .msg-row{ display:flex; margin:8px 0; }
      .msg-row.left{ justify-content:flex-start; }
      .msg-row.right{ justify-content:flex-end; }
      .bubble{
        max-width:88%; padding:10px 12px; border-radius:16px; line-height:1.6; font-size:15px;
        box-shadow:0 1px 1px rgba(0,0,0,.05); white-space:pre-wrap; position:relative;
      }
      .bubble.user{ border-top-right-radius:8px; border:1px solid #F2E4A2; background:#FFF8CC; color:#333; }
      .bubble.ai  { border-top-left-radius:8px;  border:1px solid #BEE3FF; background:#EAF6FF; color:#0a2540; }

      .chip{
        display:inline-block; margin:-2px 0 6px 0; padding:2px 10px; border-radius:999px;
        font-size:12px; font-weight:700; color:#fff; line-height:1;
      }
      .chip.me{ background:#059669; }   /* 나 */
      .chip.pt{ background:#2563eb; }   /* 피티쌤 */
      .chip.mn{ background:#7c3aed; }   /* 미나쌤 */
      .chip-src{
        display:inline-block; margin-left:6px; padding:2px 8px; border-radius:10px;
        background:#eef2ff; color:#3730a3; font-size:12px; font-weight:600; line-height:1;
        border:1px solid #c7d2fe; max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
        vertical-align:middle;
      }

      @media (max-width:480px){
        .bubble{ max-width:96%; }
        .chip-src{ max-width:160px; }
      }
    </style>
    """,
        unsafe_allow_html=True,
    )


def _render_mode_controls_pills() -> str:
    """질문 모드 pill (ChatPane 상단). 반환: '문법'|'문장'|'지문'"""
    _inject_chat_styles_once()
    if st is None:
        return "문법"
    ss = st.session_state
    labels = ["문법", "문장", "지문"]
    cur = ss.get("qa_mode_radio") or "문법"
    idx = labels.index(cur) if cur in labels else 0
    sel = st.radio(
        "질문 모드",
        options=labels,
        index=idx,
        horizontal=True,
        label_visibility="collapsed",
    )
    ss["qa_mode_radio"] = sel
    return sel


# ========================== [16] 채팅 패널 ===============================
def _render_chat_panel() -> None:
    """질문(오른쪽) → 피티쌤(스트리밍) → 미나쌤(스트리밍)."""
    import importlib as _imp
    import html
    import re
    from src.agents.responder import answer_stream
    from src.agents.evaluator import evaluate_stream
    from src.llm.streaming import BufferOptions, make_stream_handler

    try:
        try:
            _label_mod = _imp.import_module("src.rag.label")
        except Exception:
            _label_mod = _imp.import_module("label")
        _decide_label = getattr(_label_mod, "decide_label", None)
        _search_hits = getattr(_label_mod, "search_hits", None)
    except Exception:
        _decide_label = None
        _search_hits = None

    def _esc(t: str) -> str:
        s = html.escape(t or "").replace("\n", "<br/>")
        return re.sub(r"  ", "&nbsp;&nbsp;", s)

    def _chip_html(who: str) -> str:
        klass = {"나": "me", "피티쌤": "pt", "미나쌤": "mn"}.get(who, "pt")
        return f'<span class="chip {klass}">{html.escape(who)}</span>'

    def _src_html(label: Optional[str]) -> str:
        if not label:
            return ""
        return f'<span class="chip-src">{html.escape(label)}</span>'

    def _emit_bubble(
        placeholder,
        who: str,
        acc_text: str,
        *,
        source: Optional[str],
        align_right: bool,
    ) -> None:
        side_cls = "right" if align_right else "left"
        klass = "user" if align_right else "ai"
        chips = _chip_html(who) + (_src_html(source) if not align_right else "")
        html_block = (
            f'<div class="msg-row {side_cls}">'
            f'  <div class="bubble {klass}">{chips}<br/>{_esc(acc_text)}</div>'
            f"</div>"
        )
        placeholder.markdown(html_block, unsafe_allow_html=True)

    if st is None:
        return
    ss = st.session_state
    question = str(ss.get("inpane_q", "") or "").strip()
    if not question:
        return

    src_label = "[AI지식]"
    if callable(_search_hits) and callable(_decide_label):
        try:
            hits = _search_hits(question, top_k=5)
            src_label = _decide_label(hits, default_if_none="[AI지식]")
        except Exception:
            src_label = "[AI지식]"

    ph_user = st.empty()
    _emit_bubble(ph_user, "나", question, source=None, align_right=True)

    ph_ans = st.empty()
    acc_ans = ""

    def _on_emit_ans(chunk: str) -> None:
        nonlocal acc_ans
        acc_ans += str(chunk or "")
        _emit_bubble(ph_ans, "피티쌤", acc_ans, source=src_label, align_right=False)

    emit_chunk_ans, close_stream_ans = make_stream_handler(
        on_emit=_on_emit_ans,
        opts=BufferOptions(
            min_emit_chars=8,
            soft_emit_chars=24,
            max_latency_ms=150,
            flush_on_strong_punct=True,
            flush_on_newline=True,
        ),
    )
    for piece in answer_stream(question=question, mode=ss.get("__mode", "")):
        emit_chunk_ans(str(piece or ""))
    close_stream_ans()
    full_answer = acc_ans.strip() or "(응답이 비어있어요)"

    ph_eval = st.empty()
    acc_eval = ""

    def _on_emit_eval(chunk: str) -> None:
        nonlocal acc_eval
        acc_eval += str(chunk or "")
        _emit_bubble(ph_eval, "미나쌤", acc_eval, source=src_label, align_right=False)

    emit_chunk_eval, close_stream_eval = make_stream_handler(
        on_emit=_on_emit_eval,
        opts=BufferOptions(
            min_emit_chars=8,
            soft_emit_chars=24,
            max_latency_ms=150,
            flush_on_strong_punct=True,
            flush_on_newline=True,
        ),
    )
    for piece in evaluate_stream(
        question=question, mode=ss.get("__mode", ""), answer=full_answer, ctx={"answer": full_answer}
    ):
        emit_chunk_eval(str(piece or ""))
    close_stream_eval()

    ss["last_q"] = question
    ss["inpane_q"] = ""


# ========================== [17] 본문 렌더 ===============================
def _render_body() -> None:
    if st is None:
        return

    if not st.session_state.get("_boot_checked"):
        try:
            _boot_auto_restore_index()
            _boot_autoflow_hook()
        except Exception as e:
            _errlog(f"boot check failed: {e}", where="[render_body.boot]", exc=e)
        finally:
            st.session_state["_boot_checked"] = True

    _mount_background(
        theme="light", accent="#5B8CFF", density=3, interactive=True, animate=True,
        gradient="radial", grid=True, grain=False, blur=0, seed=1234, readability_veil=True,
    )

    _header()

    # 관리자만: 오케스트레이터/스캔/인덱싱/읽기전용/Probe 상세
    if _is_admin_view():
        _render_index_orchestrator_header()
        try:
            # (선택) 기존 상세 Probe 함수가 있다면 호출
            _render_ready_probe()
        except Exception:
            pass
        try:
            _render_admin_prepared_scan_panel()
        except Exception:
            pass
        try:
            _render_admin_index_panel()
        except Exception:
            pass
        try:
            _render_admin_indexed_sources_panel()
        except Exception:
            pass

    _auto_start_once()

    _inject_chat_styles_once()
    with st.container():
        st.markdown('<div class="chatpane"><div class="messages">', unsafe_allow_html=True)
        try:
            _render_chat_panel()
        except Exception as e:
            _errlog(f"chat panel failed: {e}", where="[render_body.chat]", exc=e)
        st.markdown("</div></div>", unsafe_allow_html=True)

    with st.container(border=True, key="chatpane_container"):
        st.markdown('<div class="chatpane">', unsafe_allow_html=True)
        st.session_state["__mode"] = _render_mode_controls_pills() or st.session_state.get("__mode", "")
        with st.form("chat_form", clear_on_submit=False):
            q: str = st.text_input("질문", placeholder="질문을 입력하세요…", key="q_text")
            submitted: bool = st.form_submit_button("➤")
        st.markdown("</div>", unsafe_allow_html=True)

    if submitted and isinstance(q, str) and q.strip():
        st.session_state["inpane_q"] = q.strip()
        st.rerun()
    else:
        st.session_state.setdefault("inpane_q", "")


# =============================== [18] main =================================
def main() -> None:
    if st is None:
        print("Streamlit 환경이 아닙니다.")
        return
    _render_body()


if __name__ == "__main__":
    main()
