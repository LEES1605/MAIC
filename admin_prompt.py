# =============================== [01] imports & setup — START ==========================
from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    import streamlit as st
except Exception:
    st = None  # test/CI 환경 대비

# 페이지 메타(중복 호출 예외 무시)
if st is not None:
    try:
        st.set_page_config(page_title="Prompts Admin", layout="wide", initial_sidebar_state="collapsed")
    except Exception:
        pass

# 공용 헬퍼/정규화기
def _persist_dir() -> Path:
    try:
        from src.core.persist import effective_persist_dir
        return Path(str(effective_persist_dir())).expanduser()
    except Exception:
        return Path.home() / ".maic" / "persist"

def _openai_key() -> Optional[str]:
    try:
        return (st.secrets.get("OPENAI_API_KEY") if st and hasattr(st, "secrets") else None) or None
    except Exception:
        return None

# =============================== [01] imports & setup — END ============================


# =============================== [02] admin gate & header — START =====================
def _render_header() -> None:
    """프로젝트 헤더와 관리자 버튼(로그인 포함) 렌더."""
    try:
        from src.ui.header import render as _hdr
        _hdr()
    except Exception:
        if st is not None:
            st.markdown("**LEES AI Teacher — Admin**")

def _require_admin() -> bool:
    """관리자 모드일 때만 True. 아니면 로그인 유도."""
    if st is None:
        return False
    _render_header()
    ss = st.session_state
    if not bool(ss.get("admin_mode")):
        st.info("🔐 이 페이지는 **관리자 전용**입니다. 우측 상단의 **관리자** 버튼으로 로그인해 주세요.")
        return False
    return True
# =============================== [02] admin gate & header — END =======================


# =============================== [03] UI: persona + prompts — START ====================
def _default_persona() -> str:
    return (
        "당신은 영문법에 정통한 최고 수준의 언어 분석 전문가 AI입니다. "
        "근거 중심으로 간결하고 단계적으로 설명합니다. "
        "모호하면 반드시 질문으로 확인합니다."
    )

def _section_inputs() -> tuple[str, str, str, str]:
    """
    반환: (persona, grammar_text, sentence_text, passage_text)
    - persona: 공통 상단 입력(모든 모드에 접두로 합쳐 전달)
    - *text: 각 모드의 자유서술 프롬프트(자연어)
    """
    st.subheader("🧩 Prompts Admin")
    with st.expander("도움말", expanded=False):
        st.markdown(
            "- 상단 **페르소나**는 모든 모드에 공통으로 접두됩니다.\n"
            "- 각 모드 입력은 자유서술(자연어) 한 덩어리로 적어 주세요.\n"
            "- [스키마 변환]은 OpenAI 키가 있으면 모델로, 없으면 템플릿 폴백으로 동작합니다."
        )

    persona = st.text_area("공통 페르소나", _default_persona(), height=180)
    st.caption("아래 3개 입력은 자유서술입니다. (문법/문장/지문)")
    grammar_text  = st.text_area("문법 모드 입력",    "", height=180, key="txt_grammar")
    sentence_text = st.text_area("문장 모드 입력",    "", height=160, key="txt_sentence")
    passage_text  = st.text_area("지문(독해) 모드 입력", "", height=140, key="txt_passage")
    return persona, grammar_text, sentence_text, passage_text
# =============================== [03] UI: persona + prompts — END ======================


# =============================== [04] normalize & preview & save — START ==============
def _normalize_and_preview(
    persona: str,
    grammar_text: str,
    sentence_text: str,
    passage_text: str,
) -> str:
    """
    자연어 → 레니언트 정규화(YAML).
    - 공통 페르소나는 각 모드 입력의 접두로 합쳐 전달.
    - 실패 시 템플릿 폴백.
    """
    try:
        from src.ui.assist.prompt_normalizer import normalize_to_yaml
    except Exception:
        # 최소 폴백
        def normalize_to_yaml(**_k):  # type: ignore
            return "version: auto\nmodes:\n  grammar: {persona: '', system_instructions: ''}\n  sentence: {persona: '', system_instructions: ''}\n  passage: {persona: '', system_instructions: ''}\n"

    p = (persona or "").strip()
    g = (p + "\n\n" + grammar_text).strip() if grammar_text.strip() else p
    s = (p + "\n\n" + sentence_text).strip() if sentence_text.strip() else p
    pa = (p + "\n\n" + passage_text).strip() if passage_text.strip() else p

    yaml_text = normalize_to_yaml(
        grammar_text=g,
        sentence_text=s,
        passage_text=pa,
        openai_key=_openai_key(),
        openai_model="gpt-4o-mini",
    )
    st.subheader("📄 미리보기 (YAML)")
    st.code(yaml_text, language="yaml")
    return yaml_text

def _save_yaml(yaml_text: str) -> None:
    base = _persist_dir()
    base.mkdir(parents=True, exist_ok=True)
    out = base / "prompts.yaml"
    out.write_text(yaml_text, encoding="utf-8")
    try:
        st.toast(f"저장 완료: {out}", icon="✅")
    except Exception:
        st.success(f"저장 완료: {out}")

def _actions(yaml_text: str) -> None:
    col_a, col_b = st.columns([1,1])
    with col_a:
        if st.button("💾 persist/prompts.yaml 로 저장", type="primary"):
            _save_yaml(yaml_text)
    with col_b:
        st.download_button("⬇️ YAML 내려받기", data=yaml_text.encode("utf-8"),
                           file_name="prompts.yaml", mime="text/yaml")
# =============================== [04] normalize & preview & save — END =================


# =============================== [05] main — START ====================================
def main() -> None:
    if st is None:
        print("Streamlit 환경이 아닙니다.")
        return
    if not _require_admin():
        return

    persona, g, s, pa = _section_inputs()

    run = st.button("🔧 스키마 변환", type="primary")
    if run:
        yaml_text = _normalize_and_preview(persona, g, s, pa)
        _actions(yaml_text)
    else:
        st.caption("상단 입력 후 [🔧 스키마 변환]을 눌러 주세요.")

if __name__ == "__main__":
    main()
# =============================== [05] main — END ======================================
