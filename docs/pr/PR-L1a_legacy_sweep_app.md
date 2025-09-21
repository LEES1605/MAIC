# PR-L1a — Legacy Removal Sweep (app.py only)

**Branch:** `refactor/PR-L1a-legacy-sweep-app`  
**Target file:** `app.py`

---

## 1) 원인 분석
- **[09] background** 구획은 dead code이며 호출은 [19] 본문 내 한 줄 뿐입니다. 기능 영향 없이 제거 가능합니다. (구획: L369–L381, 호출: L1573).  
- **[14] admin legacy** 구획은 자리표시자(항상 `return None`)로 미사용입니다. 안전하게 제거 가능합니다. (구획: L1133–L1137).  
- [19] 본문에서 `_mount_background()` 호출은 no-op 이므로 제거해도 UI/기능 변화가 없습니다. (호출: L1573).

## 2) 수정 목표
- 기능 변화 없이 **레거시 제거**로 `app.py`를 슬림화하고, 후속 모듈 분리를 수월하게 만든다.

## 3) 변경 내역 (숫자 구획 단위, START/END 전체 기준)

### A) [09] background — **삭제 (DELETE whole section)** — `app.py:L369–L381`
**Before (구획 전체):**
```python
# =============================== [09] background — START ===============================
def _inject_modern_bg_lib() -> None:
    try:
        s = globals().get("st", None)
        if s is not None and hasattr(s, "session_state"):
            s.session_state["__bg_lib_injected__"] = False
    except Exception:
        pass


def _mount_background(**_kw) -> None:
    return
# ================================= [09] background — END ===============================
```
**After:** _(구획 전체 삭제)_

---

### B) [14] admin legacy — **삭제 (DELETE whole section)** — `app.py:L1133–L1137`
**Before (구획 전체):**
```python
# =============================== [14] admin legacy — START ============================
def _render_admin_panels() -> None:
    # legacy 자리표시자(문법 안정 목적). 현재는 사용하지 않습니다.
    return None
# ================================= [14] admin legacy — END ============================
```
**After:** _(구획 전체 삭제)_

---

### C) [19] body & main — **교체 (REPLACE whole section)** — `app.py:L1551–L1629`
- 변경점: `_render_body()` 내부의 **`_mount_background()` 호출 1줄 제거** (기타 라인은 동일).
**Before (구획 전체):**
```python
# =============================== [19] body & main — START =============================
def _render_body() -> None:
    if st is None:
        return

    # 1) 부팅 훅
    if not st.session_state.get("_boot_checked"):
        try:
            _boot_auto_restore_index()
            _boot_autoflow_hook()
        except Exception as e:
            _errlog(f"boot check failed: {e}", where="[render_body.boot]", exc=e)
        finally:
            st.session_state["_boot_checked"] = True

    # 2) ✅ 상태 확정(자동 복원/READY 반영)을 헤더보다 먼저 수행
    try:
        _auto_start_once()
    except Exception as e:
        _errlog(f"auto_start_once failed: {e}", where="[render_body.autostart]", exc=e)

    # 3) 배경/헤더
    _mount_background()
    _header()

    # 4) 관리자 패널
    if _is_admin_view():
        _render_index_orchestrator_header()
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

    # 5) 채팅 메시지 영역
    _inject_chat_styles_once()
    with st.container():
        st.markdown('<div class="chatpane"><div class="messages">', unsafe_allow_html=True)
        try:
            _render_chat_panel()
        except Exception as e:
            _errlog(f"chat panel failed: {e}", where="[render_body.chat]", exc=e)
        st.markdown("</div></div>", unsafe_allow_html=True)

    # 6) 채팅 입력 폼
    with st.container(border=True, key="chatpane_container"):
        st.markdown('<div class="chatpane">', unsafe_allow_html=True)
        st.session_state["__mode"] = _render_mode_controls_pills() or st.session_state.get("__mode", "")
        submitted: bool = False
        with st.form("chat_form", clear_on_submit=False):
            q: str = st.text_input("질문", placeholder="질문을 입력하세요...", key="q_text")
            submitted = st.form_submit_button("➤")
        st.markdown("</div>", unsafe_allow_html=True)

    # 7) 전송 처리
    if submitted and isinstance(q, str) and q.strip():
        st.session_state["inpane_q"] = q.strip()
        _safe_rerun("chat_submit", ttl=1)
    else:
        st.session_state.setdefault("inpane_q", "")


def main() -> None:
    if st is None:
        print("Streamlit 환경이 아닙니다.")
        return
    _render_body()


if __name__ == "__main__":
    main()
# ================================= [19] body & main — END =============================
```
**After (구획 전체):**
```python
# =============================== [19] body & main — START =============================
def _render_body() -> None:
    if st is None:
        return

    # 1) 부팅 훅
    if not st.session_state.get("_boot_checked"):
        try:
            _boot_auto_restore_index()
            _boot_autoflow_hook()
        except Exception as e:
            _errlog(f"boot check failed: {e}", where="[render_body.boot]", exc=e)
        finally:
            st.session_state["_boot_checked"] = True

    # 2) ✅ 상태 확정(자동 복원/READY 반영)을 헤더보다 먼저 수행
    try:
        _auto_start_once()
    except Exception as e:
        _errlog(f"auto_start_once failed: {e}", where="[render_body.autostart]", exc=e)

    # 3) 배경/헤더
    _header()

    # 4) 관리자 패널
    if _is_admin_view():
        _render_index_orchestrator_header()
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

    # 5) 채팅 메시지 영역
    _inject_chat_styles_once()
    with st.container():
        st.markdown('<div class="chatpane"><div class="messages">', unsafe_allow_html=True)
        try:
            _render_chat_panel()
        except Exception as e:
            _errlog(f"chat panel failed: {e}", where="[render_body.chat]", exc=e)
        st.markdown("</div></div>", unsafe_allow_html=True)

    # 6) 채팅 입력 폼
    with st.container(border=True, key="chatpane_container"):
        st.markdown('<div class="chatpane">', unsafe_allow_html=True)
        st.session_state["__mode"] = _render_mode_controls_pills() or st.session_state.get("__mode", "")
        submitted: bool = False
        with st.form("chat_form", clear_on_submit=False):
            q: str = st.text_input("질문", placeholder="질문을 입력하세요...", key="q_text")
            submitted = st.form_submit_button("➤")
        st.markdown("</div>", unsafe_allow_html=True)

    # 7) 전송 처리
    if submitted and isinstance(q, str) and q.strip():
        st.session_state["inpane_q"] = q.strip()
        _safe_rerun("chat_submit", ttl=1)
    else:
        st.session_state.setdefault("inpane_q", "")


def main() -> None:
    if st is None:
        print("Streamlit 환경이 아닙니다.")
        return
    _render_body()


if __name__ == "__main__":
    main()
# ================================= [19] body & main — END =============================
```

## 4) 테스트 방법 (Actions-only)
1. **Import 스모크**: `pytest -q`  → Green  
2. **앱 부팅 확인**: Streamlit로 실행 → 헤더 배지/관리자 패널/챗 UI 정상 동작.  
3. **전역 검색**: `_mount_background`, `_inject_modern_bg_lib`, `_render_admin_panels` → “미존재”.

## 5) 롤백
- 해당 PR revert 또는 [19] 구획에 `_mount_background()` 한 줄 복구 + [09]/[14] 블록 복원.

## 6) 커밋 메시지 예시
```
refactor(app): remove dead admin bg stub & legacy panel; slim body (PR-L1a)

- delete [09] background section (dead code)
- delete [14] admin legacy placeholder (unused)
- remove _mount_background() call from [19] body
- no functional change
```
