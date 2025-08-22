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
    st.markdown("### 🧠 강의 준비 (자동 사전점검 기반)")

    # 자동 사전점검 결과
    pre = st.session_state.get("_precheck_res")
    had_auto = st.session_state.get("_precheck_auto_done", False)

    # 상태 배너 ---------------------------------------------------------------
    banner = st.container()
    with banner:
        if pre:
            would = bool(pre.get("would_rebuild"))
            total = pre.get("total_files", 0)
            new_n = pre.get("new_docs", 0)
            upd_n = pre.get("updated_docs", 0)
            unchg = pre.get("unchanged_docs", 0)

            if would:
                st.info(f"🔎 자동 사전점검 결과: **신규 {new_n} / 변경 {upd_n} 건** 감지됨 · 총 {total}개 (변경 없음 {unchg})")
            else:
                st.success(f"🔎 자동 사전점검 결과: **변경 없음** · 총 {total}개 (변경 없음 {unchg})")
        else:
            if had_auto:
                st.warning("자동 사전점검을 시도했지만 결과를 가져오지 못했습니다. 네트워크/권한을 확인하거나 ‘다시 점검’을 눌러 주세요.")
            else:
                st.caption("자동 사전점검 준비 중…")

    st.divider()

    # 흐름형 CTA 패널 ---------------------------------------------------------
    cta = st.container()
    with cta:
        cols = st.columns([0.5, 0.5])
        with cols[0]:
            st.caption("현재 두뇌 상태")
            _index_status_badge()
        with cols[1]:
            st.caption("작업 선택")

        # 버튼 영역
        c1, c2 = st.columns([0.6, 0.4])

        # [A] 사전점검 결과가 있는 경우
        if pre:
            would = bool(pre.get("would_rebuild"))

            if would:
                # 1차 CTA: 재최적화
                with c1:
                    if st.button("🛠 재최적화 실행 (변경 반영)", type="primary", key="cta_build"):
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
                                with st.status("재최적화 중…", state="running") as s:
                                    res = build_index_with_checkpoint(
                                        update_pct=_pct,
                                        update_msg=_msg,
                                        gdrive_folder_id="",
                                        gcp_creds={},
                                        persist_dir="",
                                        remote_manifest={},
                                    )
                                    prog.progress(100)
                                    s.update(label="최적화 완료 ✅", state="complete")
                                st.success("최적화가 완료되었습니다.")
                                st.json(res)
                                # 완료 후 자동 연결
                                if _auto_attach_or_restore_silently():
                                    st.success("두뇌가 새 인덱스로 재연결되었습니다.")
                                # 사전점검 결과 초기화(다시 점검 유도)
                                st.session_state.pop("_precheck_res", None)
                            except Exception as e:
                                st.error(f"최적화 실패: {type(e).__name__}: {e}")

                # 2차 CTA: 지금은 연결만
                with c2:
                    if st.button("지금은 연결만", key="cta_connect_anyway"):
                        ok = _auto_attach_or_restore_silently()
                        if ok:
                            st.success("두뇌 연결 완료 ✅")
                            st.rerun()
                        else:
                            st.error("두뇌 연결 실패. 먼저 재최적화를 실행해 인덱스를 만들어 주세요.")

            else:
                # 변경 없음 → 1차 CTA: 바로 연결
                with c1:
                    if st.button("🧠 두뇌 연결", type="primary", key="cta_connect"):
                        ok = _auto_attach_or_restore_silently()
                        if ok:
                            st.success("두뇌 연결 완료 ✅")
                            st.rerun()
                        else:
                            st.error("두뇌 연결 실패. 필요 시 ‘다시 점검’ 후 재최적화를 실행하세요.")

                with c2:
                    # 보조: 다시 점검
                    if st.button("🔄 다시 점검", key="cta_recheck"):
                        try:
                            if precheck_build_needed is None:
                                st.error("사전점검 모듈을 찾지 못했습니다. (src.rag.index_build)")
                            else:
                                res = precheck_build_needed("")
                                st.session_state["_precheck_res"] = res
                                st.success("사전점검이 완료되었습니다.")
                                st.rerun()
                        except Exception as e:
                            st.error(f"사전점검 실패: {type(e).__name__}: {e}")

        # [B] 사전점검 결과가 없는 경우(자동 점검 실패 등)
        else:
            with c1:
                if st.button("🔎 사전점검 실행", type="primary", key="cta_precheck_manual"):
                    if precheck_build_needed is None:
                        st.error("사전점검 모듈을 찾지 못했습니다. (src.rag.index_build)")
                    else:
                        try:
                            res = precheck_build_needed("")
                            st.session_state["_precheck_res"] = res
                            st.success("사전점검이 완료되었습니다.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"사전점검 실패: {type(e).__name__}: {e}")
            with c2:
                if st.button("🧠 두뇌 연결 시도", key="cta_connect_when_no_precheck"):
                    ok = _auto_attach_or_restore_silently()
                    if ok:
                        st.success("두뇌 연결 완료 ✅")
                        st.rerun()
                    else:
                        st.error("두뇌 연결 실패. 먼저 사전점검/재최적화를 실행하세요.")

    # Advanced(접기) — 강제 초기화 등 ----------------------------------------
    with st.expander("고급(Advanced)", expanded=False):
        st.caption("일반적으로는 필요 없습니다. 문제가 있을 때만 사용하세요.")
        if st.button("🧹 강제 초기화 (두뇌 캐시 삭제)", key="btn_reset_local_advanced"):
            try:
                base = Path.home() / ".maic"
                persist = base / "persist"
                if persist.exists():
                    import shutil
                    shutil.rmtree(persist)
                if "rag_index" in st.session_state:
                    st.session_state["rag_index"] = None
                st.success("두뇌 파일이 초기화되었습니다. 위의 ‘사전점검/재최적화→연결’ 순서로 다시 준비해 주세요.")
            except Exception as e:
                st.error(f"초기화 중 오류: {type(e).__name__}")
                st.exception(e)

# ===== [05B] TAG DIAGNOSTICS (NEW) ==========================================
def render_tag_diagnostics():
    """
    서버의 ~/.maic/persist/chunks.jsonl을 직접 읽어서
    grammar_tags 필드 존재 여부와 샘플을 보여주는 임시 진단 패널.
    """
    import json as _json
    from pathlib import Path as _P

    st.markdown("### 🧪 태그 확인(임시 진단)")
    base = _P.home() / ".maic" / "persist"
    path = base / "chunks.jsonl"

    c1, c2 = st.columns([0.6, 0.4])
    with c1:
        st.caption(f"경로: `{path}`")
    with c2:
        if path.exists():
            try:
                size_mb = path.stat().st_size / (1024 * 1024)
                st.caption(f"파일 크기: 약 {size_mb:.2f} MB")
            except Exception:
                pass

    if not path.exists():
        st.info("아직 파일이 없어요. 먼저 **사전점검 → 재최적화 실행**으로 인덱스를 만든 뒤 다시 확인해 주세요.")
        return

    # 설정
    max_preview = st.slider("미리보기 라인 수", 1, 50, 5, key="diag_preview_lines")
    max_scan = st.slider("스캔 라인 수(존재 여부 집계)", 50, 5000, 1000, step=50, key="diag_scan_lines")

    if st.button("열어서 확인", type="primary", key="btn_diag_open"):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception as e:
            st.error(f"파일 읽기 실패: {type(e).__name__}: {e}")
            return

        has_field = 0
        samples = []
        scan_n = min(max_scan, len(lines))

        for i, ln in enumerate(lines[:scan_n]):
            try:
                obj = _json.loads(ln)
            except Exception:
                continue
            if "grammar_tags" in obj:
                has_field += 1
            if len(samples) < max_preview:
                samples.append({
                    "doc_id": obj.get("doc_id"),
                    "chunk_index": obj.get("chunk_index"),
                    "grammar_tags": obj.get("grammar_tags", None),
                })

        st.success(f"스캔 완료: 총 {scan_n}줄 중 **grammar_tags** 필드가 보인 줄: **{has_field}**")
        st.caption("※ 0이어도 ‘필드가 전혀 없다’는 뜻은 아닙니다. 스캔 구간에 해당 줄이 없을 수 있어요. 아래 미리보기를 확인하세요.")

        # 표 미리보기
        if samples:
            st.dataframe(samples, use_container_width=True, hide_index=True)
        else:
            st.warning("미리보기 구간에서 파싱 가능한 샘플을 찾지 못했습니다.")

        # 원시 JSONL 일부
        with st.expander("원시 JSONL 일부 보기(상위 미리보기)"):
            st.code("\n".join(lines[:max_preview]), language="json")

        # 다운로드(옵션)
        with st.expander("파일 내려받기"):
            try:
                st.download_button(
                    label="chunks.jsonl 다운로드",
                    data=path.read_bytes(),
                    file_name="chunks.jsonl",
                    mime="application/json",
                )
            except Exception as e:
                st.error(f"다운로드 준비 실패: {type(e).__name__}: {e}")


# ===== [06] SIMPLE QA DEMO (mode-aware, ENTER SUBMIT, CHAT-AREA SPINNER) =====
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

    # --- 입력부 ---------------------------------------------------------------
    q = st.text_input("질문 입력", placeholder=placeholder, key="qa_q", on_change=_on_q_enter)
    k = st.slider("검색 결과 개수(top_k)", 1, 10, 5, key="qa_k")

    clicked = st.button("검색", key="qa_go")
    submitted = clicked or st.session_state.get("qa_submitted", False)

    # 답변 표시 영역(채팅 위치) 컨테이너
    answer_box = st.container()

    if submitted and (q or "").strip():
        st.session_state["qa_submitted"] = False
        try:
            with answer_box:
                with st.status("✳️ 답변 준비 중…", state="running") as s:
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

                    if mode == "Sentence":
                        fixes = _sentence_quick_fix(q)
                        if fixes:
                            st.markdown("#### ✍️ 빠른 교정 제안 (한국어)")
                            for bad, good in fixes:
                                st.markdown(f"- **{bad}** → {good}")

                    _render_clean_answer(mode, raw_text, refs, lang)
                    s.update(label="완료 ✅", state="complete")
        except Exception:
            with answer_box:
                with st.spinner("✳️ 답변 준비 중…"):
                    try:
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
                        if mode == "Sentence":
                            fixes = _sentence_quick_fix(q)
                            if fixes:
                                st.markdown("#### ✍️ 빠른 교정 제안 (한국어)")
                                for bad, good in fixes:
                                    st.markdown(f"- **{bad}** → {good}")
                        _render_clean_answer(mode, raw_text, refs, lang)
                    except Exception as e:
                        st.error(f"검색 실패: {type(e).__name__}: {e}")

# ===== [07] MAIN =============================================================
def main():
    # (1) 세션당 1회 자동 사전점검
    if not st.session_state.get("_precheck_auto_done", False):
        st.session_state["_precheck_auto_done"] = True
        if precheck_build_needed is not None:
            try:
                st.session_state["_precheck_res"] = precheck_build_needed("")  # 시크릿 기반 자동 처리
            except Exception:
                # 조용한 실패 처리: 패널에서 안내
                st.session_state["_precheck_res"] = None
        else:
            st.session_state["_precheck_res"] = None

    # (2) 준비 패널 (자동 사전점검 결과에 따라 흐름형 CTA)
    render_brain_prep_main()
    st.divider()

    # (3) (NEW) 태그 진단 패널 — 그대로 유지
    render_tag_diagnostics()
    st.divider()

    # (4) 기존 QA 데모
    render_simple_qa()

if __name__ == "__main__":
    main()

