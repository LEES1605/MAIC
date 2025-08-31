# ======================= [10] 부팅/인덱스 준비 — START ========================
def _set_brain_status(code: str, msg: str, source: str = "", attached: bool = False):
    """세션 상태를 일관된 방식으로 세팅한다."""
    if st is None:
        return
    ss = st.session_state
    ss["brain_status_code"] = code
    ss["brain_status_msg"]  = msg
    ss["brain_source"]      = source
    ss["brain_attached"]    = bool(attached)
    ss["restore_recommend"] = (code in ("MISSING","ERROR"))
    ss.setdefault("index_decision_needed", False)
    ss.setdefault("index_change_stats", {})

def _quick_local_attach_only():
    """빠른 부팅: 네트워크 호출 없이 로컬 신호만 확인."""
    if st is None: return False
    ss = st.session_state
    man    = (PERSIST_DIR / "manifest.json")
    chunks = (PERSIST_DIR / "chunks.jsonl")
    ready  = (PERSIST_DIR / ".ready")

    if (chunks.exists() and chunks.stat().st_size > 0) or (man.exists() and man.stat().st_size > 0) or ready.exists():
        _set_brain_status("READY", "로컬 인덱스 연결됨(빠른 부팅)", "local", attached=True)
        return True
    else:
        _set_brain_status("MISSING", "인덱스 없음(관리자에서 '업데이트 점검' 필요)", "", attached=False)
        return False

def _run_deep_check_and_attach():
    """관리자 버튼 클릭 시 실행되는 네트워크 검사+복구."""
    if st is None: return
    ss = st.session_state
    idx = _try_import("src.rag.index_build", ["quick_precheck", "diff_with_manifest"])
    rel = _try_import("src.backup.github_release", ["restore_latest"])
    quick  = idx.get("quick_precheck")
    diff   = idx.get("diff_with_manifest")
    restore_latest = rel.get("restore_latest")

    # 0) 로컬 먼저
    if _is_brain_ready():
        stats = {}
        changed = False
        if callable(diff):
            try:
                d = diff() or {}
                stats = d.get("stats") or {}
                total = int(stats.get("added",0))+int(stats.get("changed",0))+int(stats.get("removed",0))
                changed = total > 0
            except Exception as e:
                _errlog(f"diff 실패: {e}", where="[deep_check]")
        msg = "로컬 인덱스 연결됨" + ("(신규/변경 감지)" if changed else "(변경 없음/판단 불가)")
        _set_brain_status("READY", msg, "local", attached=True)
        ss["index_decision_needed"] = changed
        ss["index_change_stats"] = stats
        return

    # 1) Drive precheck (선택적)
    if callable(quick):
        try: _ = quick() or {}
        except Exception as e: _errlog(f"precheck 예외: {e}", where="[deep_check]")

    # 2) GitHub Releases 복구
    restored = False
    if callable(restore_latest):
        try:
            # restore_latest가 (dest_dir: Path|str) 모두 수용하도록 사용
            restored = bool(restore_latest(PERSIST_DIR))
        except Exception as e:
            _errlog(f"restore 실패: {e}", where="[deep_check]")

    if restored and _is_brain_ready():
        stats = {}
        changed = False
        if callable(diff):
            try:
                d = diff() or {}
                stats = d.get("stats") or {}
                total = int(stats.get("added",0))+int(stats.get("changed",0))+int(stats.get("removed",0))
                changed = total > 0
            except Exception as e:
                _errlog(f"diff 실패(복구후): {e}", where="[deep_check]")
        msg = "Releases에서 복구·연결" + ("(신규/변경 감지)" if changed else "(변경 없음/판단 불가)")
        _set_brain_status("READY", msg, "release", attached=True)
        ss["index_decision_needed"] = changed
        ss["index_change_stats"] = stats
        return

    # 3) 실패
    _set_brain_status("MISSING", "업데이트 점검 실패(인덱스 없음). 관리자: 재빌드/복구 필요", "", attached=False)
    ss["index_decision_needed"] = False
    ss["index_change_stats"] = {}

def _auto_start_once():
    """AUTO_START_MODE에 따른 1회성 자동 복원."""
    if st is None or st.session_state.get("_auto_started"):
        return
    st.session_state["_auto_started"] = True

    if _is_brain_ready():
        return

    mode = (os.getenv("AUTO_START_MODE") or _from_secrets("AUTO_START_MODE", "off") or "off").lower()
    if mode in ("restore","on"):
        rel = _try_import("src.backup.github_release", ["restore_latest"])
        fn = rel.get("restore_latest")
        if not callable(fn): return
        try:
            if fn(dest_dir=PERSIST_DIR):
                _mark_ready()
                if hasattr(st, "toast"): st.toast("자동 복원 완료", icon="✅")
                else: st.success("자동 복원 완료")
                _set_brain_status("READY", "자동 복원 완료", "release", attached=True)
                if not st.session_state.get("_auto_rerun_done"):
                    st.session_state["_auto_rerun_done"] = True
                    st.rerun()
        except Exception as e:
            _errlog(f"auto restore failed: {e}", where="[auto_start]", exc=e)
# ======================== [10] 부팅/인덱스 준비 — END =========================
