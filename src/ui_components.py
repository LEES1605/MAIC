# ===== [UI-01] TOP OF FILE — UI Components (header, titles, list rows) ======  # [UI-01] START
from __future__ import annotations
from typing import Any, Callable

import streamlit as st

# ── 디자인 토큰(간격/폰트/색) — 향후 theme 분리 가능 ─────────────────────────────
TOKENS = {
    "font_title_size": "1.6rem",
    "font_section_size": "1.1rem",
    "pill_font_size": "0.9rem",
    "gap_sm": "6px",
    "gap_md": "8px",
    "color_green": "#16a34a",
    "color_green_border": "#16a34a55",
    "color_green_bg": "#16a34a22",
}

# ===== [UI-01] END ===========================================================


# ===== [UI-02] CSS INJECTOR ==================================================
def _inject_base_css():
    """기본 UI CSS를 한 번만 주입"""
    if st.session_state.get("_ui_base_css_injected"):
        return
    st.session_state["_ui_base_css_injected"] = True

    css = f"""
    <style>
      .ui-topbar {{
        display: flex; align-items: center; gap: {TOKENS['gap_md']}; margin-bottom: {TOKENS['gap_sm']};
      }}
      .ui-title {{
        font-size: {TOKENS['font_title_size']}; font-weight: 800; line-height: 1.2; margin: 0;
      }}
      .ui-pill {{
        display: inline-block; padding: 4px 8px; border-radius: 999px; font-weight: 600;
        font-size: {TOKENS['pill_font_size']};
      }}
      .ui-pill-green {{
        background: {TOKENS['color_green_bg']}; color: {TOKENS['color_green']}; border: 1px solid {TOKENS['color_green_border']};
      }}
      .ui-section-title {{
        font-weight: 700; font-size: {TOKENS['font_section_size']}; margin: 6px 0 2px 0;
      }}
      .ui-row {{
        display: grid; grid-template-columns: 1fr auto; align-items: start; gap: {TOKENS['gap_sm']};
      }}
      .ui-row-text {{ word-break: break-word; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
# ===== [UI-02] END ===========================================================


# ===== [UI-03] BADGE HELPERS =================================================
def badge_ready(text: str = "🟢 답변 준비 완료") -> str:
    """초록 배지(학생 화면 기본) — HTML 문자열 반환"""
    return f"<span class='ui-pill ui-pill-green'>{text}</span>"

def badge_plain(html: str) -> str:
    """임의 배지 HTML을 그대로 사용하고 싶을 때"""
    return html
# ===== [UI-03] END ===========================================================


# ===== [UI-04] HEADER RENDERER ===============================================
def render_header(title: str, badge_html: str = ""):
    """
    상단 헤더: 제목 + 배지를 '한 줄'에 인라인 배치.
    - title: 왼쪽 굵은 제목(예: 'LEES AI 쌤')
    - badge_html: 오른쪽에 붙는 배지(예: badge_ready())
    """
    _inject_base_css()
    html = f"""
    <div class='ui-topbar'>
      <div class='ui-title'>{title}</div>
      <div>{badge_html}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
# ===== [UI-04] END ===========================================================


# ===== [UI-05] SECTION TITLE =================================================
def render_section_title(text: str):
    """
    굵고 살짝 큰 섹션 타이틀. (예: '📒 나의 질문 히스토리')
    빈 리스트일 경우 호출을 생략하면 타이틀도 노출되지 않음.
    """
    _inject_base_css()
    st.markdown(f"<div class='ui-section-title'>{text}</div>", unsafe_allow_html=True)
# ===== [UI-05] END ===========================================================
# ===== [UI-06] LIST ROW (TEXT + OPTIONAL RIGHT BUTTON) =======================  # [UI-06] START
def render_item_row(
    text: str,
    right_btn: Callable[..., Any] | None = None,
    key: str | None = None,
) -> None:
    """
    리스트 한 줄: 왼쪽 텍스트, 오른쪽에 작은 버튼(옵션)
    - right_btn: 호출 시 버튼을 그리는 콜백(예: lambda: st.button('👁️', key='...'))
    - key: 행 식별용 키(필수는 아님) — 필요 시 해시 충돌 방지용으로 사용
    """
    _inject_base_css()
    with st.container():
        st.markdown("<div class='ui-row'>", unsafe_allow_html=True)
        st.markdown(f"<div class='ui-row-text'>- {text}</div>", unsafe_allow_html=True)
        # 오른쪽 버튼 영역
        if right_btn:
            right_btn()
        else:
            st.write("")  # 그리드 균형용 빈 칸
        st.markdown("</div>", unsafe_allow_html=True)
# ===== [UI-06] END ===========================================================
