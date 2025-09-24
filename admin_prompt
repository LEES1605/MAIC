# ============================ [01] future import — START ============================
from __future__ import annotations
# ============================== [01] future import — END =============================

# ============================ [02] module imports — START ============================
from typing import Dict
import textwrap
try:
    import streamlit as st
except Exception:
    st = None  # CI/비-Streamlit 환경 보호
from src.ui.assist.prompt_normalizer import (
    normalize_to_yaml,
    normalize_to_yaml_from_pairs,
)
# ============================== [02] module imports — END ============================

# ============================== [03] defaults — START ================================
_DEF_PERSONA = textwrap.dedent("""
    당신은 영문법을 깊이 있게 전공했으며, 현대 영/미 영어에 정통한 언어 분석 전문가입니다.
    EFL 환경 사용자를 배려하여, 관용구/연어/굳어진 표현은 먼저 표기하고 설명을 덧붙입니다.
    정확성/근거를 중시하며, 불확실하면 질문을 통해 지침을 명확히 합니다.
""").strip()

_DEF_SYSTEM = textwrap.dedent("""
    1) 질문을 요약한다.
    2) 근거 자료(문법서적/코퍼스/AI지식)로 검증한다.
    3) 규칙→근거→예문→요약 순서로 제시한다.
    4) 오류/예외가 있으면 대비 설명을 덧붙인다.
    5) 모든 주장에는 간단한 출처 라벨을 붙인다.
""").strip()
# =============================== [03] defaults — END =================================

# ============================== [04] ui helpers — START ==============================
def _ta(label: str, key: str, value: str = "", height: int = 420) -> str:
    return st.text_area(
        label,
        value=value,
        key=key,
        height=height,
        placeholder=f"{label}를 입력하세요...",
        label_visibility="visible",
    )
# =============================== [04] ui helpers — END ===============================

# ================================ [05] main — START ==================================
def main() -> None:
    if st is None:
        return
    st.set_page_config(page_title="Prompts Admin", layout="wide", initial_sidebar_state="collapsed")
    st.title("Prompts Admin")
    st.caption("페르소나와 작업 지침(프롬프트)을 **분리 입력**해 스키마 적합 YAML을 생성합니다.")

    with st.expander("옵션", expanded=False):
        col_a, col_b, col_c = st.columns([1, 1, 1])
        with col_a:
            use_llm = st.toggle("LLM 리라이트 모드(자연어→요약/분해)", value=False, help="끄면 입력값을 그대로 스키마에 반영합니다.")
        with col_b:
            gpt_model = st.text_input("문법/지문 모델", "gpt-5-pro")
        with col_c:
            gemini_model = st.text_input("문장 모델", "gemini-pro")

    tabs = st.tabs(["문법", "문장", "지문"])

    # ── 문법
    with tabs[0]:
        g_persona = _ta("문법 - 페르소나", "g_persona", st.session_state.get("g_persona", _DEF_PERSONA))
        g_system  = _ta("문법 - 시스템 지침", "g_system", st.session_state.get("g_system", _DEF_SYSTEM))

    # ── 문장
    with tabs[1]:
        s_persona = _ta("문장 - 페르소나", "s_persona", st.session_state.get("s_persona", _DEF_PERSONA))
        s_system  = _ta("문장 - 시스템 지침", "s_system", st.session_state.get("s_system", _DEF_SYSTEM))

    # ── 지문
    with tabs[2]:
        p_persona = _ta("지문 - 페르소나", "p_persona", st.session_state.get("p_persona", _DEF_PERSONA))
        p_system  = _ta("지문 - 시스템 지침", "p_system", st.session_state.get("p_system", _DEF_SYSTEM))

    st.divider()
    c1, c2 = st.columns([1, 3], vertical_alignment="center")
    with c1:
        go = st.button("🧪 YAML 만들기", type="primary")
    with c2:
        st.caption("버튼을 누르면 오른쪽에 YAML 미리보기가 생성됩니다. 다운로드 가능.")

    if go:
        if st.session_state.get("use_llm_overrides", False) or False:
            # (보류) 전역 토글이 따로 있다면 사용 — 기본은 pairs 경로
            pass

        if not use_llm:
            yaml_text = normalize_to_yaml_from_pairs(
                grammar_persona=g_persona, grammar_system=g_system,
                sentence_persona=s_persona, sentence_system=s_system,
                passage_persona=p_persona, passage_system=p_system,
                gpt_model=gpt_model, gemini_model=gemini_model,
            )
        else:
            # LLM으로 자연어 덩어리를 분해/요약하고 싶을 때만 사용
            yaml_text = normalize_to_yaml(
                grammar_text=f"{g_persona}\n\n{g_system}",
                sentence_text=f"{s_persona}\n\n{s_system}",
                passage_text=f"{p_persona}\n\n{p_system}",
                openai_key=st.secrets.get("OPENAI_API_KEY"),
            )

        st.session_state["_last_yaml"] = yaml_text

    yaml_text = st.session_state.get("_last_yaml", "")
    if yaml_text:
        st.subheader("미리보기 (YAML)")
        st.code(yaml_text, language="yaml")
        st.download_button("💾 다운로드", data=yaml_text, file_name="prompts.yaml", mime="text/yaml")

if __name__ == "__main__":
    main()
# ================================= [05] main — END ===================================
