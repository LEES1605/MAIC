# =============================== [01] future import ===============================
from __future__ import annotations

# =============================== [02] module imports ==============================
import os
import json
import time
import traceback
import importlib
from pathlib import Path
from src.core.secret import promote_env as _promote_env, get as _secret_get
from src.core.persist import effective_persist_dir, share_persist_dir_to_session
try:
    import streamlit as st
    _promote_env(keys=["OPENAI_API_KEY"])
except Exception:
    pass
# ================================ [03] import deprecations =========================
try:
    import streamlit as _st_mod  # E: streamlit may not be installed
except ModuleNotFoundError:
    _st_mod = None

# ================================ [04] mode config & secrets =======================
# Mode config (MVP: local JSON, 추후 gist or DB)
try:
    # ensure secrets exist as env vars
    for key, val in st.secrets.items():  # type: ignore[attr-defined]
        os.environ[key] = str(val)
except Exception:
    pass

# secrets: env 우선 → st.secrets → local file
PROMPT_SECRET_KEYS = [
    "OPENAI_API_KEY",  # OpenAI
    "SERPAPI_API_KEY",  # serpapi
    "BING_SUBSCRIPTION_KEY",  # bing web search
    "BING_CUSTOM_CONFIG_ID",  # bing custom search
    "NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET",  # Naver Web search
]
# secrets JSON in current directory (gitignore'd)
SECRET_FILE_CANDIDATES = ["./secrets.json", "./secret.json"]
for cand in SECRET_FILE_CANDIDATES:
    if os.path.exists(cand):
        try:
            with open(cand) as f:
                secret_obj = json.load(f)
            for k, v in secret_obj.items():
                if isinstance(v, (str, int, float)):
                    os.environ.setdefault(k, str(v))
        except Exception:
            pass
        break
_promote_env(keys=PROMPT_SECRET_KEYS, strict=False)  # 환경/Secrets → st.secrets 정규화

# ================================ [05] storage mount ==============================
try:
    PERSIST_DIR = effective_persist_dir()
except Exception as e:
    PERSIST_DIR = None
    print(f"[WARN] No persist directory: {e}")
try:
    # share base mount (if in Streamlit)
    share_persist_dir_to_session(PERSIST_DIR)
except Exception:
    pass

# ================================ [06] cached providers ===========================
# (If) use GPTCache or FAISS here...

# ================================ [07] page config (UI) ===========================
# (skipped for brevity) 

# ================================ [08] UI constants (CSS) =========================
# (skipped for brevity) 

# ================================ [09] UI Layout ==================================
# (skipped for brevity) 

# =================================== [10] util =====================================
def _errlog(msg: str, where: str = "", exc: Exception | None = None) -> None:
    """표준 에러 로깅(민감정보 금지, 실패 무해화)."""
    try:
        prefix = f"{where} " if where else ""
        print(f"[ERR] {prefix}{msg}")
        if exc:
            traceback.print_exception(exc, value=exc, tb=exc.__traceback__)
    except Exception:
        print(f"[ERR] {where} {msg}")

# ================================ [11] styling ====================================
# (skipped for brevity) 

# =============================== [12] background ==================================
# (skipped for brevity) 

# ================================ [13] header  ====================================
# (skipped for brevity) 

# =========================== [14] main panel (sidebar) ===========================
# (skipped for brevity) 

# ============================= [15A] mode select (UI) ============================
# (skipped for brevity: UI for mode selection) 

# ============================= [15B] mode select (logic) =========================
def _render_mode_controls_pills() -> Optional[str]:
    """모드 선택 Pills 제어 및 현재 선택 리턴."""
    if st is None:
        return None
    import streamlit as stc  # alias to avoid confusion
    from src.core.modes import enabled_modes

    labels = [m.label for m in enabled_modes]
    keys = [m.key for m in enabled_modes]
    # 기본 선택: index 0
    cur_idx = 0
    if "__mode" in st.session_state:
        try:
            cur_idx = keys.index(st.session_state["__mode"])
        except ValueError:
            cur_idx = 0
    sel_label = stc.radio(
        "",
        options=labels,
        index=cur_idx,
        horizontal=True,
        label_visibility="collapsed",
    )

    # 라벨→key 매핑(임포트 가능하면 사용, 아니면 키 매핑)
    try:
        _modes = importlib.import_module("src.core.modes")
        _find_mode_by_label = getattr(_modes, "find_mode_by_label", None)
        spec = _find_mode_by_label(sel_label) if callable(_find_mode_by_label) else None
    except Exception as e:
        _errlog(f"find_mode_by_label import/call failed: {e}", where="[mode_select]", exc=e)
        spec = None
    cur_key = spec.key if spec else keys[labels.index(sel_label)]

    st.session_state["qa_mode_radio"] = sel_label
    st.session_state["__mode"] = cur_key
    return cur_key
# [15B] END

# [16] START: 채팅 패널 (FULL REPLACEMENT)
def _render_chat_panel() -> None:
    """질문(오른쪽) → 피티쌤(스트리밍) → 미나쌤(스트리밍)."""
    import importlib as _imp
    import html
    import re
    from typing import Optional
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
        _make_chip = getattr(_label_mod, "make_source_chip", None)
    except Exception:
        _decide_label = None
        _search_hits = None
        _make_chip = None

    # ✅ whitelist guard (fallback signature identical to original)
    try:
        from modes.types import sanitize_source_label
    except Exception:
        def sanitize_source_label(label: Optional[str]) -> str:
            return "[AI지식]"

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

    # --- 검색 → 라벨 → 칩 문자열
    src_label = "[AI지식]"
    hits = []
    if callable(_search_hits):
        try:
            hits = _search_hits(question, top_k=5)
        except Exception:
            hits = []
    if callable(_decide_label):
        try:
            src_label = _decide_label(hits, default_if_none="[AI지식]")
        except Exception:
            src_label = "[AI지식]"
    # ✅ whitelist 강제: 3라벨 외 금지
    src_label = sanitize_source_label(src_label)
    chip_text = src_label
    if callable(_make_chip):
        try:
            chip_text = _make_chip(hits, src_label)
        except Exception:
            chip_text = src_label

    # --- 사용자 버블
    ph_user = st.empty()
    _emit_bubble(ph_user, "나", question, source=None, align_right=True)

    # --- 답변 스트리밍
    ph_ans = st.empty()
    acc_ans = ""
    def _on_emit_ans(chunk: str) -> None:
        nonlocal acc_ans
        acc_ans += str(chunk or "")
        _emit_bubble(ph_ans, "피티쌤", acc_ans, source=chip_text, align_right=False)
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

    # --- 평가 스트리밍
    ph_eval = st.empty()
    acc_eval = ""
    def _on_emit_eval(chunk: str) -> None:
        nonlocal acc_eval
        acc_eval += str(chunk or "")
        _emit_bubble(ph_eval, "미나쌤", acc_eval, source=chip_text, align_right=False)
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
# [16] END

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

    # 관리자만: 오케스트레이터/스캔/인덱싱/읽기전용 상세
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
