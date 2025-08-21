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
import streamlit as st

# RAG 엔진이 없어도 앱이 죽지 않게 try/except로 감쌈
try:
    from src.rag_engine import get_or_build_index, LocalIndexMissing
except Exception:
    get_or_build_index = None  # type: ignore
    class LocalIndexMissing(Exception):  # 안전 가드
        ...

# 인덱스 빌더/사전점검 (PREPARED→청크→리포트→ZIP 업로드)
try:
    from src.rag.index_build import precheck_build_needed, build_index_with_checkpoint
except Exception:
    precheck_build_needed = None  # type: ignore
    build_index_with_checkpoint = None  # type: ignore

# ===== [03] SESSION & HELPERS ================================================
st.set_page_config(page_title="AI Teacher (Clean)", layout="wide")

# 인덱스 상태
if "rag_index" not in st.session_state:
    st.session_state["rag_index"] = None

# 모드/언어/제출 플래그
if "mode" not in st.session_state:
    st.session_state["mode"] = "Grammar"  # Grammar | Sentence | Passage
if "lang" not in st.session_state:
    st.session_state["lang"] = "한국어"     # 한국어 | English
if "qa_submitted" not in st.session_state:
    st.session_state["qa_submitted"] = False

def _index_ready() -> bool:
    return st.session_state.get("rag_index") is not None

def _index_status_badge() -> None:
    if _index_ready():
        st.caption("Index status: ✅ ready")
    else:
        st.caption("Index status: ❌ missing (빌드 또는 복구 필요)")

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

# ===== [04] HEADER ===========================================================
st.title("🧑‍🏫 AI Teacher — Clean Scaffold")
_index_status_badge()

# ===== [04A] MODE & LANG SWITCH =============================================
with st.container():
    c_mode, c_lang, c_info = st.columns([0.35, 0.20, 0.45])
    with c_mode:
        mode = st.segmented_control(
            "모드 선택",
            options=["Grammar", "Sentence", "Passage"],
            default=st.session_state.get("mode", "Grammar"),
            key="ui_mode_segmented",
        )
        st.session_state["mode"] = mode
    with c_lang:
        lang = st.segmented_control(
            "출력 언어",
            options=["한국어", "English"],
            default=st.session_state.get("lang", "한국어"),
            key="ui_lang_segmented",
        )
        st.session_state["lang"] = lang
    with c_info:
        if mode == "Grammar":
            st.caption("모드: **Grammar** — 문법 Q&A (태깅/부스팅 중심)")
        elif mode == "Sentence":
            st.caption("모드: **Sentence** — 문장 분석 (품사/구문/교정 프롬프트 중심)")
        else:
            st.caption("모드: **Passage** — 지문 설명 (요약→비유→제목/주제 프롬프트 중심)")

st.divider()

# ===== [05] RAG: Build/Restore Panels =======================================
def render_brain_prep_main():
    st.markdown("### 🧠 강의 준비")
    c1, c2 = st.columns([0.4, 0.6])

    with c1:
        if st.button("🧠 AI 두뇌 준비(복구/연결)", type="primary", key="btn_attach_restore"):
            ok = _auto_attach_or_restore_silently()
            if ok:
                st.success("두뇌 연결이 완료되었습니다.")
                st.rerun()
            else:
                st.error("두뇌 연결에 실패했습니다. 먼저 ‘사전점검→재최적화’를 실행해 인덱스를 만들어 주세요.")

        if st.button("📥 강의 자료 다시 불러오기 (두뇌 초기화)", key="btn_reset_local"):
            try:
                base = Path.home() / ".maic"
                persist = base / "persist"
                if persist.exists():
                    import shutil
                    shutil.rmtree(persist)
                if "rag_index" in st.session_state:
                    st.session_state["rag_index"] = None
                st.success("두뇌 파일이 초기화되었습니다. ‘AI 두뇌 준비’를 다시 눌러 연결해 주세요.")
            except Exception as e:
                st.error(f"초기화 중 오류: {type(e).__name__}")
                st.exception(e)

    with c2:
        st.markdown("#### ⚙️ 인덱스 최적화 — **사전점검 후 실행**")
        st.caption("변경이 없으면 재최적화는 생략하고, 필요 시 2차 확인 버튼으로만 강제 실행합니다.")

        if st.button("🔎 사전점검 (변경 여부 확인)", key="btn_precheck"):
            if precheck_build_needed is None:
                st.error("사전점검 모듈을 찾지 못했습니다. (src.rag.index_build)")
            else:
                try:
                    res = precheck_build_needed("")  # 시크릿의 PREPARED ID 자동 사용
                    st.session_state["_precheck_res"] = res
                    st.success("사전점검이 완료되었습니다.")
                except Exception as e:
                    st.session_state.pop("_precheck_res", None)
                    st.error(f"사전점검 실패: {type(e).__name__}: {e}")

        pre = st.session_state.get("_precheck_res")
        if pre:
            cA, cB, cC, cD = st.columns(4)
            cA.metric("총 파일", pre.get("total_files", 0))
            cB.metric("신규", pre.get("new_docs", 0))
            cC.metric("변경", pre.get("updated_docs", 0))
            cD.metric("변경 없음", pre.get("unchanged_docs", 0))

            if pre.get("new"):
                with st.expander("🆕 신규 문서 목록", expanded=False):
                    st.table(pre["new"])
            if pre.get("updated"):
                with st.expander("✏️ 변경 문서 목록", expanded=False):
                    st.table(pre["updated"])

            would = bool(pre.get("would_rebuild"))
            if not would:
                st.info("변경 사항이 없습니다. 굳이 재최적화하지 않아도 됩니다.")
                run_label = "⚠️ 그래도 재최적화 실행"
                run_help  = "변경이 없어도 강제로 다시 청크/ZIP을 생성합니다."
            else:
                run_label = "🛠 재최적화 실행 (변경 반영)"
                run_help  = "변경/신규 파일만 델타로 반영하여 인덱스를 갱신합니다."

            if st.button(run_label, help=run_help, key="btn_build_confirm"):
                if build_index_with_checkpoint is None:
                    st.error("인덱스 빌더 모듈을 찾지 못했습니다. (src.rag.index_build)")
                else:
                    prog = st.progress(0)
                    log = st.empty()

                    def _pct(v: int, msg: str | None = None):
                        prog.progress(max(0, min(int(v), 100)))
                        if msg:
                            log.info(str(msg))

                    def _msg(s: str):
                        log.write(f"• {s}")

                    try:
                        with st.spinner("인덱스를 최적화(빌드)하는 중…"):
                            res = build_index_with_checkpoint(
                                update_pct=_pct,
                                update_msg=_msg,
                                gdrive_folder_id="",
                                gcp_creds={},
                                persist_dir="",
                                remote_manifest={},
                            )
                        prog.progress(100)
                        st.success("최적화가 완료되었습니다.")
                        st.json(res)
                        if _attach_from_local():
                            st.success("두뇌가 새 인덱스로 재연결되었습니다.")
                        st.session_state.pop("_precheck_res", None)
                    except Exception as e:
                        st.error(f"최적화 실패: {type(e).__name__}: {e}")

# ===== [06] SIMPLE QA DEMO (mode-aware, ENTER SUBMIT, SPINNER) ===============
def _sentence_quick_fix(user_q: str) -> List[Tuple[str, str]]:
    tips: List[Tuple[str, str]] = []
    if re.search(r"\bI\s+seen\b", user_q, flags=re.I):
        tips.append(("I seen", "I **saw** the movie / I **have seen** the movie"))
    if re.search(r"\b(he|she|it)\s+don'?t\b", user_q, flags=re.I):
        tips.append(("he/she/it don't", "**doesn't**"))
    if re.search(r"\ba\s+[aeiouAEIOU]", user_q):
        tips.append(("a + 모음 시작 명사", "가능하면 **an** + 모음 시작 명사"))
    return tips

def _render_clean_answer(mode: str, answer_text: str, refs: List[Dict[str, str]], lang: str):
    st.markdown(f"**선택 모드:** `{mode}` · **출력 언어:** `{lang}`")

    if lang == "한국어":
        st.markdown("#### ✅ 요약/안내 (한국어)")
        st.write("아래는 자료 기반 엔진의 원문 응답입니다. 현재 단계에서는 원문이 영어일 수 있어요.")
        with st.expander("원문 응답 보기(영문)"):
            st.write(answer_text.strip() or "—")
    else:
        st.markdown("#### ✅ Answer")
        st.write(answer_text.strip() or "—")

    if refs:
        with st.expander("근거 자료(상위 2개)"):
            for i, r in enumerate(refs[:2], start=1):
                name = r.get("doc_id") or r.get("source") or f"ref{i}"
                url = r.get("url") or r.get("source_url") or ""
                st.markdown(f"- {name}  " + (f"(<{url}>)" if url else ""))

# Enter 제출용 on_change 콜백
def _on_q_enter():
    st.session_state["qa_submitted"] = True
    # 즉시 토스트로 피드백(선택적 시각 신호)
    try:
        st.toast("✳️ 답변 준비 중…")
    except Exception:
        pass

def render_simple_qa():
    st.markdown("### 💬 질문해 보세요 (간단 데모)")
    if not _index_ready():
        st.info("아직 두뇌가 준비되지 않았어요. 상단의 **AI 두뇌 준비** 또는 **사전점검→재최적화**를 먼저 실행해 주세요.")
        return

    mode = st.session_state.get("mode", "Grammar")
    lang = st.session_state.get("lang", "한국어")

    if mode == "Grammar":
        placeholder = "예: 관계대명사 which 사용법을 알려줘"
    elif mode == "Sentence":
        placeholder = "예: I seen the movie yesterday 문장 문제점 분석해줘"
    else:
        placeholder = "예: 이 지문 핵심 요약과 제목 3개, 주제 1개 제안해줘"

    # --- Enter 제출: on_change 콜백으로 플래그 설정 ---
    q = st.text_input("질문 입력", placeholder=placeholder, key="qa_q", on_change=_on_q_enter)
    k = st.slider("검색 결과 개수(top_k)", 1, 10, 5, key="qa_k")

    # 버튼 클릭도 동일하게 동작
    clicked = st.button("검색", key="qa_go")
    submitted = clicked or st.session_state.get("qa_submitted", False)

    if submitted and (q or "").strip():
        try:
            # 스피너: Enter/버튼 제출 즉시 ‘로딩 아이콘’ 표시
            with st.spinner("✳️ 답변 준비 중…"):
                qe = st.session_state["rag_index"].as_query_engine(top_k=k)
                r = qe.query(q)
                raw_text = getattr(r, "response", "") or str(r)

                refs: List[Dict[str, str]] = []
                hits = getattr(r, "source_nodes", None) or getattr(r, "hits", None)
                if hits:
                    for h in hits[:2]:
                        meta = getattr(h, "metadata", None) or getattr(h, "node", {}).get("metadata", {})
                        refs.append({
                            "doc_id": (meta or {}).get("doc_id") or (meta or {}).get("file_name", ""),
                            "url": (meta or {}).get("source") or (meta or {}).get("url", ""),
                        })

                # Sentence 모드: 빠른 교정(한국어 안내)
                if mode == "Sentence":
                    fixes = _sentence_quick_fix(q)
                    if fixes:
                        st.markdown("#### ✍️ 빠른 교정 제안 (한국어)")
                        for bad, good in fixes:
                            st.markdown(f"- **{bad}** → {good}")

                _render_clean_answer(mode, raw_text, refs, lang)

        except Exception as e:
            st.error(f"검색 실패: {type(e).__name__}: {e}")
        finally:
            # Enter 재입력을 위한 플래그 리셋
            st.session_state["qa_submitted"] = False

# ===== [07] MAIN =============================================================
def main():
    render_brain_prep_main()
    st.divider()
    render_simple_qa()

if __name__ == "__main__":
    main()
