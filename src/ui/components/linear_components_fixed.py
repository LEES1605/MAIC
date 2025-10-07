# Linear 테마 기반 재사용 가능한 컴포넌트들
from __future__ import annotations
from typing import Any, Dict, List, Optional, Union, Tuple
import streamlit as st
from .linear_theme import get_color, get_font_size, get_radius, get_padding


def linear_button(
    label: str,
    key: Optional[str] = None,
    variant: str = "primary",
    size: str = "medium",
    disabled: bool = False,
    width: str = "content",
    **kwargs
) -> bool:
    """
    Linear 스타일 버튼 컴포넌트
    
    Args:
        label: 버튼 텍스트
        key: Streamlit key
        variant: "primary", "secondary", "danger", "success"
        size: "small", "medium", "large"
        disabled: 비활성화 여부
        width: 버튼 너비 ("content", "stretch")
        **kwargs: st.button에 전달할 추가 인자
    
    Returns:
        버튼 클릭 여부
    """
    if st is None:
        return False
    
    # Linear 스타일 CSS 적용
    button_css = f"""
    <style>
    .linear-button-{variant} {{
        font-family: var(--linear-font-primary) !important;
        font-weight: var(--linear-font-weight-medium) !important;
        font-size: var(--linear-font-size-regular) !important;
        line-height: var(--linear-line-height-normal) !important;
        border-radius: var(--linear-radius-{size}) !important;
        border: 2px solid {_get_button_color(variant)} !important;
        background: {_get_button_bg(variant)} !important;
        color: {_get_button_color(variant)} !important;
        padding: {_get_button_padding(size)} !important;
        transition: all 0.2s ease !important;
        box-shadow: none !important;
    }}
    
    .stButton > button {{
        border: 2px solid {_get_button_color(variant)} !important;
        background: {_get_button_bg(variant)} !important;
        color: {_get_button_color(variant)} !important;
        box-shadow: none !important;
        font-family: var(--linear-font-primary) !important;
        font-weight: var(--linear-font-weight-medium) !important;
        border-radius: var(--linear-radius-{size}) !important;
        padding: {_get_button_padding(size)} !important;
        transition: all 0.2s ease !important;
        min-height: 44px !important;
        display: block !important;
        width: 100% !important;
        box-sizing: border-box !important;
        position: relative !important;
        margin: 0 !important;
        outline: none !important;
        /* Streamlit의 기본 스타일 완전 제거 */
        border-style: solid !important;
        border-width: 2px !important;
        border-color: {_get_button_color(variant)} !important;
    }}
    
    .stButton > button:hover {{
        background: {_get_button_hover_bg(variant)} !important;
        border-color: var(--linear-brand) !important;
        transform: translateY(-1px) !important;
    }}
    
    .linear-button-{variant}:hover {{
        background: {_get_button_hover_bg(variant)} !important;
        border-color: var(--linear-brand) !important;
    }}
    
    /* Streamlit 버튼 완전 오버라이드 */
    div[data-testid="stButton"] > button {{
        border: 2px solid {_get_button_color(variant)} !important;
        background: {_get_button_bg(variant)} !important;
        color: {_get_button_color(variant)} !important;
        box-shadow: none !important;
        font-family: var(--linear-font-primary) !important;
        font-weight: var(--linear-font-weight-medium) !important;
        border-radius: var(--linear-radius-{size}) !important;
        padding: {_get_button_padding(size)} !important;
        transition: all 0.2s ease !important;
        min-height: 44px !important;
        display: block !important;
        width: 100% !important;
        box-sizing: border-box !important;
        position: relative !important;
        margin: 0 !important;
        outline: none !important;
        /* Streamlit의 기본 스타일 완전 제거 */
        border-style: solid !important;
        border-width: 2px !important;
        border-color: {_get_button_color(variant)} !important;
    }}
    
    .linear-button-{variant}:disabled {{
        opacity: 0.5 !important;
        cursor: not-allowed !important;
    }}
    
    /* Streamlit 기본 버튼 스타일 완전 무력화 */
    .stButton button {{
        border: 2px solid {_get_button_color(variant)} !important;
        border-style: solid !important;
        border-width: 2px !important;
        border-color: {_get_button_color(variant)} !important;
        background: {_get_button_bg(variant)} !important;
        color: {_get_button_color(variant)} !important;
        box-shadow: none !important;
        font-family: var(--linear-font-primary) !important;
        font-weight: var(--linear-font-weight-medium) !important;
        border-radius: var(--linear-radius-{size}) !important;
        padding: {_get_button_padding(size)} !important;
        transition: all 0.2s ease !important;
        min-height: 44px !important;
        display: block !important;
        width: 100% !important;
        box-sizing: border-box !important;
        position: relative !important;
        margin: 0 !important;
        outline: none !important;
    }}
    
    .stButton button:hover {{
        border-color: var(--linear-brand) !important;
        background: {_get_button_hover_bg(variant)} !important;
        transform: translateY(-1px) !important;
    }}
    
    /* 추가 테두리 강화 - 모든 가능한 선택자 */
    button[data-testid="baseButton-secondary"],
    button[data-testid="baseButton-primary"],
    button[data-testid="baseButton-danger"],
    button[data-testid="baseButton-success"] {{
        border: 2px solid {_get_button_color(variant)} !important;
        border-style: solid !important;
        border-width: 2px !important;
        border-color: {_get_button_color(variant)} !important;
        background: {_get_button_bg(variant)} !important;
        color: {_get_button_color(variant)} !important;
        box-shadow: none !important;
        font-family: var(--linear-font-primary) !important;
        font-weight: var(--linear-font-weight-medium) !important;
        border-radius: var(--linear-radius-{size}) !important;
        padding: {_get_button_padding(size)} !important;
        transition: all 0.2s ease !important;
        min-height: 44px !important;
        display: block !important;
        width: 100% !important;
        box-sizing: border-box !important;
        position: relative !important;
        margin: 0 !important;
        outline: none !important;
    }}
    
    /* ::after pseudo-element로 테두리 강제 적용 */
    .stButton > button::after {{
        content: '' !important;
        position: absolute !important;
        top: -2px !important;
        left: -2px !important;
        right: -2px !important;
        bottom: -2px !important;
        border: 2px solid {_get_button_color(variant)} !important;
        border-radius: var(--linear-radius-{size}) !important;
        pointer-events: none !important;
        z-index: 1 !important;
    }}
    
    /* Streamlit 버튼 컨테이너 강제 스타일 */
    .stButton {{
        border: 2px solid {_get_button_color(variant)} !important;
        border-radius: var(--linear-radius-{size}) !important;
        background: {_get_button_bg(variant)} !important;
        padding: 0 !important;
        margin: 0 !important;
        overflow: visible !important;
    }}
    
    /* 모바일 반응형 */
    @media (max-width: 480px) {{
        .stButton > button,
        div[data-testid="stButton"] > button {{
            font-size: 0.9rem !important;
            padding: 12px 16px !important;
            min-height: 48px !important;
        }}
    }}
    </style>
    """
    
    st.markdown(button_css, unsafe_allow_html=True)
    
    # 버튼 렌더링
    return st.button(
        label,
        key=key,
        disabled=disabled,
        width=width,
        **kwargs
    )


def linear_card(
    content: Any,
    title: Optional[str] = None,
    variant: str = "default",
    padding: str = "large",
    **kwargs
) -> None:
    """
    Linear 스타일 카드 컴포넌트
    
    Args:
        content: 카드 내용
        title: 카드 제목 (선택사항)
        variant: "default", "elevated", "outlined"
        padding: "small", "medium", "large", "xlarge"
        **kwargs: st.container에 전달할 추가 인자
    """
    if st is None:
        return
    
    # Linear 카드 CSS
    card_css = f"""
    <style>
    .linear-card-{variant} {{
        background: {_get_card_bg(variant)} !important;
        border: 1px solid {_get_card_border(variant)} !important;
        border-radius: var(--linear-radius-large) !important;
        padding: var(--linear-padding-{padding}) !important;
        margin: 8px 0 !important;
        box-shadow: {_get_card_shadow(variant)} !important;
    }}
    
    .linear-card-title {{
        font-family: var(--linear-font-primary) !important;
        font-weight: var(--linear-font-weight-semibold) !important;
        font-size: var(--linear-font-size-title3) !important;
        line-height: var(--linear-line-height-tight) !important;
        color: var(--linear-text-primary) !important;
        margin-bottom: 12px !important;
    }}
    </style>
    """
    
    st.markdown(card_css, unsafe_allow_html=True)
    
    # 카드 렌더링
    with st.container(**kwargs):
        if title:
            st.markdown(f'<div class="linear-card-title">{title}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="linear-card-{variant}">', unsafe_allow_html=True)
        content
        st.markdown('</div>', unsafe_allow_html=True)


def linear_badge(
    text: str,
    variant: str = "default",
    size: str = "medium"
) -> None:
    """
    Linear 스타일 배지 컴포넌트
    
    Args:
        text: 배지 텍스트
        variant: "default", "success", "warning", "danger", "info"
        size: "small", "medium", "large"
    """
    if st is None:
        return
    
    badge_css = f"""
    <style>
    .linear-badge-{variant} {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: {_get_badge_padding(size)};
        min-height: {_get_badge_height(size)};
        border-radius: var(--linear-radius-full);
        font-family: var(--linear-font-primary);
        font-weight: var(--linear-font-weight-medium);
        font-size: {_get_badge_font_size(size)};
        background: {_get_badge_bg(variant)};
        color: {_get_badge_color(variant)};
        border: 1px solid {_get_badge_border(variant)};
        line-height: 1;
    }}
    </style>
    """
    
    st.markdown(badge_css, unsafe_allow_html=True)
    st.markdown(f'<span class="linear-badge-{variant}">{text}</span>', unsafe_allow_html=True)


def linear_input(
    label: str,
    key: Optional[str] = None,
    placeholder: Optional[str] = None,
    type: str = "default",
    disabled: bool = False,
    **kwargs
) -> str:
    """
    Linear 스타일 입력 컴포넌트
    
    Args:
        label: 입력 필드 라벨
        key: Streamlit key
        placeholder: 플레이스홀더 텍스트
        type: "default", "password", "number"
        disabled: 비활성화 여부
        **kwargs: st.text_input에 전달할 추가 인자
    
    Returns:
        입력된 값
    """
    if st is None:
        return ""
    
    # Linear 입력 필드 CSS
    input_css = """
    <style>
    .linear-input {
        font-family: var(--linear-font-primary) !important;
        background: var(--linear-bg-tertiary) !important;
        border: 2px solid var(--linear-border-secondary) !important;
        border-radius: var(--linear-radius-medium) !important;
        color: var(--linear-text-primary) !important;
        padding: var(--linear-padding-medium) !important;
    }
    
    .stTextInput > div > div > input {
        border: 2px solid var(--linear-border-secondary) !important;
        background: var(--linear-bg-tertiary) !important;
        color: var(--linear-text-primary) !important;
        border-radius: var(--linear-radius-medium) !important;
        padding: 8px 12px !important;
        font-family: var(--linear-font-primary) !important;
        box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.2) !important;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: var(--linear-brand) !important;
        box-shadow: 0 0 0 2px rgba(94, 106, 210, 0.2), inset 0 1px 3px rgba(0, 0, 0, 0.2) !important;
        outline: none !important;
        background: var(--linear-bg-tertiary) !important;
    }
    
    /* 숫자 입력 필드 스타일 - 가장 얇은 회색 테두리 */
    .stNumberInput > div > div > input,
    div[data-testid="stNumberInput"] > div > div > input,
    .stNumberInput input[type="number"] {
        border: 1px solid #404040 !important; /* 가장 얇은 회색 테두리 */
        border-style: solid !important;
        border-width: 1px !important;
        border-color: #404040 !important;
        background: var(--linear-bg-tertiary) !important;
        color: var(--linear-text-primary) !important;
        border-radius: var(--linear-radius-medium) !important;
        padding: 8px 12px !important;
        font-family: var(--linear-font-primary) !important;
        box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.2) !important;
        outline: none !important;
    }
    
    .stNumberInput > div > div > input:focus {
        border-color: var(--linear-brand) !important;
        box-shadow: 0 0 0 2px rgba(94, 106, 210, 0.2), inset 0 1px 3px rgba(0, 0, 0, 0.2) !important;
        outline: none !important;
        background: var(--linear-bg-tertiary) !important;
    }
    
    /* 숫자 입력 버튼 스타일 */
    .stNumberInput button {
        background: var(--linear-bg-tertiary) !important;
        border: 1px solid var(--linear-border-secondary) !important;
        color: var(--linear-text-primary) !important;
    }
    
    .stNumberInput button:hover {
        background: var(--linear-brand) !important;
        border-color: var(--linear-brand) !important;
        color: white !important;
    }
    
    .linear-input:focus {
        border-color: var(--linear-brand) !important;
        box-shadow: 0 0 0 2px rgba(94, 106, 210, 0.2) !important;
    }
    
    .linear-label {
        font-family: var(--linear-font-primary) !important;
        font-weight: var(--linear-font-weight-medium) !important;
        color: var(--linear-text-secondary) !important;
        margin-bottom: 8px !important;
    }
    </style>
    """
    
    st.markdown(input_css, unsafe_allow_html=True)
    
    # 입력 필드 렌더링
    if type == "password":
        return st.text_input(label, key=key, placeholder=placeholder, type="password", disabled=disabled, **kwargs)
    elif type == "number":
        return st.number_input(label, key=key, placeholder=placeholder, disabled=disabled, **kwargs)
    else:
        return st.text_input(label, key=key, placeholder=placeholder, disabled=disabled, **kwargs)


def linear_alert(
    message: str,
    variant: str = "info",
    dismissible: bool = False,
    key: Optional[str] = None
) -> None:
    """
    Linear 스타일 알림 컴포넌트
    
    Args:
        message: 알림 메시지
        variant: "info", "success", "warning", "danger"
        dismissible: 닫기 버튼 여부
    """
    if st is None:
        return
    
    alert_css = f"""
    <style>
    .linear-alert-{variant} {{
        padding: var(--linear-padding-large);
        border-radius: var(--linear-radius-medium);
        border-left: 4px solid {_get_alert_border(variant)};
        background: {_get_alert_bg(variant)};
        color: {_get_alert_color(variant)};
        font-family: var(--linear-font-primary);
        margin: 8px 0;
    }}
    
    .linear-alert-icon {{
        display: inline-block;
        margin-right: 8px;
        font-weight: var(--linear-font-weight-bold);
    }}
    </style>
    """
    
    st.markdown(alert_css, unsafe_allow_html=True)
    
    icon = _get_alert_icon(variant)
    st.markdown(
        f'<div class="linear-alert-{variant}">'
        f'<span class="linear-alert-icon">{icon}</span>{message}'
        f'</div>',
        unsafe_allow_html=True
    )


def linear_divider(
    label: Optional[str] = None,
    variant: str = "default"
) -> None:
    """
    Linear 스타일 구분선 컴포넌트
    
    Args:
        label: 구분선 라벨 (선택사항)
        variant: "default", "thick", "dashed"
    """
    if st is None:
        return
    
    divider_css = f"""
    <style>
    .linear-divider-{variant} {{
        border: none;
        height: {_get_divider_height(variant)};
        background: var(--linear-border-primary);
        margin: 16px 0;
        border-radius: var(--linear-radius-small);
    }}
    
    .linear-divider-with-label {{
        display: flex;
        align-items: center;
        margin: 16px 0;
        font-family: var(--linear-font-primary);
        color: var(--linear-text-tertiary);
        font-size: var(--linear-font-size-small);
        font-weight: var(--linear-font-weight-medium);
    }}
    
    .linear-divider-with-label::before,
    .linear-divider-with-label::after {{
        content: '';
        flex: 1;
        height: 1px;
        background: var(--linear-border-primary);
        margin: 0 12px;
    }}
    </style>
    """
    
    st.markdown(divider_css, unsafe_allow_html=True)
    
    if label:
        st.markdown(f'<div class="linear-divider-with-label">{label}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<hr class="linear-divider-{variant}">', unsafe_allow_html=True)


# 헬퍼 함수들
def _get_button_bg(variant: str) -> str:
    """버튼 배경색 반환"""
    variants = {
        "primary": "var(--linear-brand)",
        "secondary": "var(--linear-bg-secondary)",
        "danger": "var(--linear-red)",
        "success": "var(--linear-green)"
    }
    return variants.get(variant, "var(--linear-bg-secondary)")


def _get_button_color(variant: str) -> str:
    """버튼 텍스트 색상 반환"""
    variants = {
        "primary": "white",
        "secondary": "var(--linear-text-primary)",
        "danger": "white",
        "success": "white"
    }
    return variants.get(variant, "var(--linear-text-primary)")


def _get_button_hover_bg(variant: str) -> str:
    """버튼 호버 배경색 반환"""
    variants = {
        "primary": "var(--linear-accent)",
        "secondary": "var(--linear-bg-tertiary)",
        "danger": "rgba(235, 87, 87, 0.8)",
        "success": "rgba(76, 183, 130, 0.8)"
    }
    return variants.get(variant, "var(--linear-bg-tertiary)")


def _get_button_padding(size: str) -> str:
    """버튼 패딩 반환"""
    sizes = {
        "small": "6px 12px",
        "medium": "8px 16px",
        "large": "12px 24px"
    }
    return sizes.get(size, "8px 16px")


def _get_button_font_size(size: str) -> str:
    """버튼 폰트 크기 반환"""
    sizes = {
        "small": "var(--linear-font-size-small)",
        "medium": "var(--linear-font-size-regular)",
        "large": "var(--linear-font-size-large)"
    }
    return sizes.get(size, "var(--linear-font-size-regular)")


def _get_card_shadow(variant: str) -> str:
    """카드 그림자 반환"""
    variants = {
        "default": "var(--linear-shadow-low)",
        "elevated": "var(--linear-shadow-medium)",
        "outlined": "none"
    }
    return variants.get(variant, "var(--linear-shadow-low)")


def _get_badge_bg(variant: str) -> str:
    """배지 배경색 반환"""
    variants = {
        "default": "var(--linear-bg-tertiary)",
        "success": "rgba(76, 183, 130, 0.1)",
        "warning": "rgba(242, 201, 76, 0.1)",
        "danger": "rgba(235, 87, 87, 0.1)",
        "info": "rgba(94, 106, 210, 0.1)"
    }
    return variants.get(variant, "var(--linear-bg-tertiary)")


def _get_badge_color(variant: str) -> str:
    """배지 텍스트 색상 반환"""
    variants = {
        "default": "var(--linear-text-secondary)",
        "success": "var(--linear-green)",
        "warning": "var(--linear-yellow)",
        "danger": "var(--linear-red)",
        "info": "var(--linear-brand)"
    }
    return variants.get(variant, "var(--linear-text-secondary)")


def _get_badge_border(variant: str) -> str:
    """배지 테두리 색상 반환"""
    variants = {
        "default": "var(--linear-border-primary)",
        "success": "var(--linear-green)",
        "warning": "var(--linear-yellow)",
        "danger": "var(--linear-red)",
        "info": "var(--linear-brand)"
    }
    return variants.get(variant, "var(--linear-border-primary)")


def _get_badge_padding(size: str) -> str:
    """배지 패딩 반환"""
    sizes = {
        "small": "4px 8px",
        "medium": "6px 12px",
        "large": "8px 16px"
    }
    return sizes.get(size, "6px 12px")


def _get_badge_font_size(size: str) -> str:
    """배지 폰트 크기 반환"""
    sizes = {
        "small": "var(--linear-font-size-micro)",
        "medium": "var(--linear-font-size-small)",
        "large": "var(--linear-font-size-regular)"
    }
    return sizes.get(size, "var(--linear-font-size-small)")


def _get_badge_height(size: str) -> str:
    """배지 높이 반환"""
    sizes = {
        "small": "20px",
        "medium": "24px",
        "large": "28px"
    }
    return sizes.get(size, "24px")


def _get_alert_border(variant: str) -> str:
    """알림 테두리 색상 반환"""
    variants = {
        "info": "var(--linear-brand)",
        "success": "var(--linear-green)",
        "warning": "var(--linear-yellow)",
        "danger": "var(--linear-red)"
    }
    return variants.get(variant, "var(--linear-brand)")


def _get_alert_bg(variant: str) -> str:
    """알림 배경색 반환"""
    variants = {
        "info": "rgba(94, 106, 210, 0.1)",
        "success": "rgba(76, 183, 130, 0.1)",
        "warning": "rgba(242, 201, 76, 0.1)",
        "danger": "rgba(235, 87, 87, 0.1)"
    }
    return variants.get(variant, "rgba(94, 106, 210, 0.1)")


def _get_alert_color(variant: str) -> str:
    """알림 텍스트 색상 반환"""
    variants = {
        "info": "var(--linear-brand)",
        "success": "var(--linear-green)",
        "warning": "var(--linear-yellow)",
        "danger": "var(--linear-red)"
    }
    return variants.get(variant, "var(--linear-brand)")


def _get_alert_icon(variant: str) -> str:
    """알림 아이콘 반환"""
    variants = {
        "info": "ℹ️",
        "success": "✅",
        "warning": "⚠️",
        "danger": "❌"
    }
    return variants.get(variant, "ℹ️")


def _get_divider_height(variant: str) -> str:
    """구분선 높이 반환"""
    variants = {
        "default": "1px",
        "thick": "2px",
        "dashed": "1px"
    }
    return variants.get(variant, "1px")


def linear_carousel(
    items: List[Dict[str, Any]],
    title: Optional[str] = None,
    autoplay: bool = True,
    autoplay_interval: int = 3000,
    show_dots: bool = True,
    show_arrows: bool = True,
    key: Optional[str] = None
) -> None:
    """
    Linear 스타일 캐러셀 컴포넌트
    
    Args:
        items: 캐러셀 아이템 리스트 [{"title": "제목", "content": "내용", "image": "이미지URL", "action": "액션"}]
        title: 캐러셀 제목 (선택사항)
        autoplay: 자동 재생 여부
        autoplay_interval: 자동 재생 간격 (밀리초)
        show_dots: 하단 점 표시 여부
        show_arrows: 좌우 화살표 표시 여부
        key: Streamlit key
    """
    if st is None or not items:
        return
    
    carousel_key = key or "linear_carousel"
    
    # 세션 상태 초기화
    if f"{carousel_key}_current" not in st.session_state:
        st.session_state[f"{carousel_key}_current"] = 0
    
    current_index = st.session_state[f"{carousel_key}_current"]
    
    # 캐러셀 CSS
    carousel_css = f"""
    <style>
    .linear-carousel {{
        background: var(--linear-bg-secondary);
        border: 1px solid var(--linear-border-primary);
        border-radius: var(--linear-radius-large);
        padding: var(--linear-padding-large);
        margin: 16px 0;
        overflow: hidden;
        position: relative;
    }}
    
    .linear-carousel-title {{
        font-family: var(--linear-font-primary);
        font-weight: var(--linear-font-weight-semibold);
        font-size: var(--linear-font-size-title3);
        color: var(--linear-text-primary);
        margin-bottom: 16px;
        text-align: center;
    }}
    
    .linear-carousel-container {{
        position: relative;
        overflow: hidden;
        border-radius: var(--linear-radius-medium);
        background: var(--linear-bg-tertiary);
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        text-align: center !important;
    }}
    
    .linear-carousel-track {{
        display: flex;
        transition: transform 0.5s ease;
        transform: translateX(-{current_index * 100}%);
    }}
    
    .linear-carousel-item {{
        min-width: 100%;
        padding: var(--linear-padding-large);
        box-sizing: border-box;
        background: var(--linear-bg-secondary);
        border: 1px solid var(--linear-border-primary);
        border-radius: var(--linear-radius-medium);
        margin: 0 8px;
    }}
    
    .linear-carousel-item-image {{
        width: 100%;
        height: 200px;
        object-fit: cover;
        border-radius: var(--linear-radius-medium);
        margin-bottom: 12px;
    }}
    
    .linear-carousel-item-title {{
        font-family: var(--linear-font-primary);
        font-weight: var(--linear-font-weight-semibold);
        font-size: var(--linear-font-size-title2);
        color: var(--linear-text-primary);
        margin-bottom: 8px;
    }}
    
    .linear-carousel-item-content {{
        font-family: var(--linear-font-primary);
        font-weight: var(--linear-font-weight-normal);
        font-size: var(--linear-font-size-regular);
        color: var(--linear-text-secondary);
        line-height: 1.6;
        margin-bottom: 16px;
    }}
    
    .linear-carousel-arrow {{
        position: absolute;
        top: 50%;
        transform: translateY(-50%);
        background: var(--linear-bg-secondary);
        border: 1px solid var(--linear-border-primary);
        border-radius: var(--linear-radius-full);
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        font-size: 18px;
        color: var(--linear-text-primary);
        z-index: 10;
        transition: all 0.2s ease;
    }}
    
    .linear-carousel-arrow:hover {{
        background: var(--linear-bg-tertiary);
        border-color: var(--linear-brand);
        color: var(--linear-brand);
    }}
    
    .linear-carousel-arrow-left {{
        left: 10px;
    }}
    
    .linear-carousel-arrow-right {{
        right: 10px;
    }}
    
    .linear-carousel-dots {{
        display: flex;
        justify-content: center;
        gap: 8px;
        margin-top: 16px;
    }}
    
    .linear-carousel-dot {{
        width: 12px;
        height: 12px;
        border-radius: var(--linear-radius-full);
        background: var(--linear-border-primary);
        cursor: pointer;
        transition: all 0.2s ease;
        border: 1px solid var(--linear-border-secondary);
    }}
    
    .linear-carousel-dot.active {{
        background: var(--linear-brand);
        border-color: var(--linear-brand);
        box-shadow: 0 0 8px rgba(94, 106, 210, 0.3);
        transform: scale(1.2);
    }}
    
    .linear-carousel-dot:hover {{
        background: var(--linear-text-secondary);
        border-color: var(--linear-brand);
        transform: scale(1.2);
    }}
    
    /* 캐러셀 화살표 버튼 스타일 */
    .linear-carousel [data-testid="stButton"] > button {{
        font-size: 32px !important;
        font-weight: bold !important;
        color: var(--linear-brand) !important;
        background: var(--linear-bg-tertiary) !important;
        border: 2px solid var(--linear-brand) !important;
        border-radius: var(--linear-radius-full) !important;
        width: 40px !important;
        height: 40px !important;
        min-height: 40px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        transition: all 0.2s ease !important;
        padding: 0 !important;
    }}
    
    .linear-carousel [data-testid="stButton"] > button:hover {{
        background: var(--linear-brand) !important;
        color: white !important;
        transform: scale(1.1) !important;
        box-shadow: 0 4px 12px rgba(94, 106, 210, 0.3) !important;
    }}
    </style>
    """
    
    st.markdown(carousel_css, unsafe_allow_html=True)
    
    # 캐러셀 렌더링
    with st.container():
        st.markdown('<div class="linear-carousel">', unsafe_allow_html=True)
        
        if title:
            # 제목을 컨테이너 안으로 이동하여 정렬 맞춤
            pass
        
        st.markdown('<div class="linear-carousel-container">', unsafe_allow_html=True)
        
        # 제목을 사진과 같은 영역에 배치
        if title:
            st.markdown(f'<div class="linear-carousel-title" style="text-align: center; margin-bottom: 1rem; padding: 0 2rem;">{title}</div>', unsafe_allow_html=True)
        
        # 현재 아이템 표시
        if items:
            current_item = items[current_index]
            
            # 화살표와 아이템을 함께 배치 - 화살표 영역 축소, 콘텐츠 영역 확대
            col1, col2, col3 = st.columns([1, 8, 1])
            
            # 화살표 (이전) - 300% 확대, 테두리 없음
            with col1:
                if show_arrows and len(items) > 1:
                    st.markdown('<div style="display: flex; align-items: center; justify-content: center; height: 100%; min-height: 200px;">', unsafe_allow_html=True)
                    # 큰 화살표 아이콘 스타일
                    st.markdown("""
                    <style>
                    /* 모든 가능한 선택자로 화살표 테두리 완전 제거 */
                    .carousel-arrow-prev button,
                    .carousel-arrow-prev .stButton > button,
                    div[data-testid="stButton"] > button,
                    .carousel-arrow-prev div[data-testid="stButton"] > button {
                        background: transparent !important;
                        border: none !important;
                        border-width: 0px !important;
                        border-style: none !important;
                        border-color: transparent !important;
                        outline: none !important;
                        box-shadow: none !important;
                        font-size: 3rem !important;
                        color: var(--linear-text-primary) !important;
                        padding: 0 !important;
                        margin: 0 !important;
                        width: auto !important;
                        height: auto !important;
                    }
                    .carousel-arrow-prev button:hover,
                    .carousel-arrow-prev .stButton > button:hover,
                    .carousel-arrow-prev div[data-testid="stButton"] > button:hover {
                        background: rgba(255, 255, 255, 0.1) !important;
                        border: none !important;
                        border-width: 0px !important;
                        outline: none !important;
                        box-shadow: none !important;
                        transform: scale(1.1) !important;
                    }
                    .carousel-arrow-prev button:focus,
                    .carousel-arrow-prev .stButton > button:focus,
                    .carousel-arrow-prev div[data-testid="stButton"] > button:focus {
                        border: none !important;
                        border-width: 0px !important;
                        outline: none !important;
                        box-shadow: none !important;
                    }
                    </style>
                    """, unsafe_allow_html=True)
                    st.markdown('<div class="carousel-arrow-prev">', unsafe_allow_html=True)
                    if st.button("◀", key=f"{carousel_key}_prev", help="이전"):
                        st.session_state[f"{carousel_key}_current"] = (current_index - 1) % len(items)
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
            
            # 현재 아이템 - 정렬 조정
            with col2:
                st.markdown('<div class="linear-carousel-item">', unsafe_allow_html=True)
                
                # 이미지 - 약간 왼쪽으로 이동
                if "image" in current_item and current_item["image"]:
                    st.markdown('<div style="display: flex; justify-content: center; margin-left: -20px; margin-bottom: 1rem;">', unsafe_allow_html=True)
                    st.image(current_item["image"], width="stretch")
                    st.markdown('</div>', unsafe_allow_html=True)
                
                # 제목 - 사진보다 2배 더 왼쪽으로 이동
                if "title" in current_item:
                    st.markdown(f'<div class="linear-carousel-item-title" style="text-align: center; margin-left: -40px; margin-bottom: 0.5rem;">{current_item["title"]}</div>', unsafe_allow_html=True)
                
                # 내용 - 가운데 정렬 유지
                if "content" in current_item:
                    st.markdown(f'<div class="linear-carousel-item-content" style="text-align: center; margin-bottom: 1rem;">{current_item["content"]}</div>', unsafe_allow_html=True)
                
                # 액션 버튼 - 사진과 가운데 정렬 (사진과 같은 위치)
                if "action" in current_item and current_item["action"]:
                    # 버튼을 사진과 같은 위치로 정렬
                    st.markdown('<div style="display: flex; justify-content: center; margin-left: -20px;">', unsafe_allow_html=True)
                    action_key = f"carousel_action_{carousel_key}_{current_index}"
                    if linear_button(current_item["action"], variant="primary", size="small", key=action_key):
                        if "action_callback" in current_item:
                            current_item["action_callback"]()
                    st.markdown('</div>', unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
            
            # 화살표 (다음) - 300% 확대, 테두리 없음
            with col3:
                if show_arrows and len(items) > 1:
                    st.markdown('<div style="display: flex; align-items: center; justify-content: center; height: 100%; min-height: 200px;">', unsafe_allow_html=True)
                    # 큰 화살표 아이콘 스타일
                    st.markdown("""
                    <style>
                    /* 모든 가능한 선택자로 화살표 테두리 완전 제거 */
                    .carousel-arrow-next button,
                    .carousel-arrow-next .stButton > button,
                    div[data-testid="stButton"] > button,
                    .carousel-arrow-next div[data-testid="stButton"] > button {
                        background: transparent !important;
                        border: none !important;
                        border-width: 0px !important;
                        border-style: none !important;
                        border-color: transparent !important;
                        outline: none !important;
                        box-shadow: none !important;
                        font-size: 3rem !important;
                        color: var(--linear-text-primary) !important;
                        padding: 0 !important;
                        margin: 0 !important;
                        width: auto !important;
                        height: auto !important;
                    }
                    .carousel-arrow-next button:hover,
                    .carousel-arrow-next .stButton > button:hover,
                    .carousel-arrow-next div[data-testid="stButton"] > button:hover {
                        background: rgba(255, 255, 255, 0.1) !important;
                        border: none !important;
                        border-width: 0px !important;
                        outline: none !important;
                        box-shadow: none !important;
                        transform: scale(1.1) !important;
                    }
                    .carousel-arrow-next button:focus,
                    .carousel-arrow-next .stButton > button:focus,
                    .carousel-arrow-next div[data-testid="stButton"] > button:focus {
                        border: none !important;
                        border-width: 0px !important;
                        outline: none !important;
                        box-shadow: none !important;
                    }
                    </style>
                    """, unsafe_allow_html=True)
                    st.markdown('<div class="carousel-arrow-next">', unsafe_allow_html=True)
                    if st.button("▶", key=f"{carousel_key}_next", help="다음"):
                        st.session_state[f"{carousel_key}_current"] = (current_index + 1) % len(items)
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # 하단 점들
        if show_dots and len(items) > 1:
            st.markdown('<div class="linear-carousel-dots" style="text-align: center; margin-top: 1rem;">', unsafe_allow_html=True)
            
            # 점들을 가로로 배치
            cols = st.columns(len(items), gap="small")
            for i, col in enumerate(cols):
                with col:
                    if st.button("●" if i == current_index else "○", 
                               key=f"{carousel_key}_dot_{i}",
                               help=f"슬라이드 {i+1}로 이동"):
                        st.session_state[f"{carousel_key}_current"] = i
                        st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)


def linear_card_with_image(
    title: str,
    content: str,
    image_url: str,
    image_alt: str = "",
    variant: str = "default",
    padding: str = "large",
    image_position: str = "top",
    action_button: Optional[str] = None,
    action_callback: Optional[callable] = None,
    **kwargs
) -> None:
    """
    이미지가 포함된 Linear 스타일 카드 컴포넌트
    
    Args:
        title: 카드 제목
        content: 카드 내용
        image_url: 이미지 URL
        image_alt: 이미지 대체 텍스트
        variant: "default", "elevated", "outlined"
        padding: "small", "medium", "large", "xlarge"
        image_position: "top", "left", "right", "bottom"
        action_button: 액션 버튼 텍스트 (선택사항)
        action_callback: 액션 버튼 클릭 콜백 (선택사항)
        **kwargs: st.container에 전달할 추가 인자
    """
    if st is None:
        return
    
    # 이미지 카드 CSS
    card_css = f"""
    <style>
    .linear-image-card-{variant} {{
        background: var(--linear-bg-secondary) !important;
        border: 1px solid var(--linear-border-primary) !important;
        border-radius: var(--linear-radius-large) !important;
        padding: var(--linear-padding-{padding}) !important;
        margin: 8px 0 !important;
        box-shadow: {_get_card_shadow(variant)} !important;
        overflow: hidden;
    }}
    
    .linear-image-card-title {{
        font-family: var(--linear-font-primary) !important;
        font-weight: var(--linear-font-weight-semibold) !important;
        font-size: var(--linear-font-size-title3) !important;
        color: var(--linear-text-primary) !important;
        margin-bottom: 12px !important;
    }}
    
    .linear-image-card-content {{
        font-family: var(--linear-font-primary) !important;
        font-weight: var(--linear-font-weight-normal) !important;
        font-size: var(--linear-font-size-regular) !important;
        color: var(--linear-text-secondary) !important;
        line-height: 1.6 !important;
        margin-bottom: 16px !important;
    }}
    
    .linear-image-card-image {{
        border-radius: var(--linear-radius-medium) !important;
        margin-bottom: 16px !important;
        width: 100% !important;
        height: auto !important;
        object-fit: cover !important;
    }}
    
    .linear-image-card-image-left,
    .linear-image-card-image-right {{
        border-radius: var(--linear-radius-medium) !important;
        width: 100% !important;
        height: 200px !important;
        object-fit: cover !important;
    }}
    </style>
    """
    
    st.markdown(card_css, unsafe_allow_html=True)
    
    # 카드 렌더링
    with st.container(**kwargs):
        st.markdown(f'<div class="linear-image-card-{variant}">', unsafe_allow_html=True)
        
        if image_position == "top":
            # 이미지가 위에
            if image_url:
                st.image(image_url, caption=image_alt, width="stretch")
            st.markdown(f'<div class="linear-image-card-title">{title}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="linear-image-card-content">{content}</div>', unsafe_allow_html=True)
            
        elif image_position == "left":
            # 이미지가 왼쪽에
            col1, col2 = st.columns([1, 2])
            with col1:
                if image_url:
                    st.image(image_url, caption=image_alt, width="stretch")
            with col2:
                st.markdown(f'<div class="linear-image-card-title">{title}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="linear-image-card-content">{content}</div>', unsafe_allow_html=True)
                
        elif image_position == "right":
            # 이미지가 오른쪽에
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f'<div class="linear-image-card-title">{title}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="linear-image-card-content">{content}</div>', unsafe_allow_html=True)
            with col2:
                if image_url:
                    st.image(image_url, caption=image_alt, width="stretch")
                    
        elif image_position == "bottom":
            # 이미지가 아래에
            st.markdown(f'<div class="linear-image-card-title">{title}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="linear-image-card-content">{content}</div>', unsafe_allow_html=True)
            if image_url:
                st.image(image_url, caption=image_alt, width="stretch")
        
        # 액션 버튼
        if action_button:
            button_key = f"image_card_action_{hash(action_button)}_{hash(title)}"
            if linear_button(action_button, variant="primary", size="medium", key=button_key):
                if action_callback:
                    action_callback()
        
        st.markdown('</div>', unsafe_allow_html=True)


def linear_navbar(
    brand_name: str,
    brand_logo: Optional[str] = None,
    nav_items: Optional[List[Dict[str, Any]]] = None,
    user_menu: Optional[Dict[str, Any]] = None,
    variant: str = "default",
    sticky: bool = True,
    key: Optional[str] = None
) -> None:
    """
    Linear 스타일 네비게이션 바 컴포넌트
    
    Args:
        brand_name: 브랜드 이름
        brand_logo: 브랜드 로고 이미지 URL (선택사항)
        nav_items: 네비게이션 아이템 리스트 [{"label": "홈", "href": "/", "active": False}]
        user_menu: 사용자 메뉴 {"name": "사용자명", "avatar": "아바타URL", "menu_items": [{"label": "로그아웃", "callback": callback}]}
        variant: "default", "transparent", "elevated"
        sticky: 상단 고정 여부
        key: Streamlit key
    """
    if st is None:
        return
    
    navbar_key = key or "linear_navbar"
    
    # 간단하고 작동하는 네비게이션 바 CSS
    navbar_css = """
    <style>
    .linear-navbar-wrapper {
        background: rgba(0, 0, 0, 0.95) !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important;
        padding: 0 !important;
        margin: -1rem -1rem 2rem -1rem !important;
        width: calc(100% + 2rem) !important;
        position: sticky !important;
        top: 0 !important;
        z-index: 1000 !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3) !important;
    }
    
    .linear-navbar-content {
        max-width: 1200px !important;
        margin: 0 auto !important;
        padding: 16px 24px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: space-between !important;
        height: 64px !important;
    }
    
    .linear-navbar-brand {
        color: white !important;
        font-weight: 600 !important;
        font-size: 1.2rem !important;
        text-decoration: none !important;
    }
    
    .linear-navbar-nav {
        display: flex !important;
        align-items: center !important;
        gap: 24px !important;
        flex: 1 !important;
        justify-content: center !important;
    }
    
    .linear-nav-item {
        background: transparent !important;
        border: none !important;
        color: rgba(255, 255, 255, 0.8) !important;
        font-size: 0.9rem !important;
        font-weight: 500 !important;
        padding: 8px 16px !important;
        border-radius: 6px !important;
        transition: all 0.2s ease !important;
        cursor: pointer !important;
        text-decoration: none !important;
    }
    
    .linear-nav-item:hover {
        background: rgba(255, 255, 255, 0.1) !important;
        color: white !important;
    }
    
    .linear-navbar-actions {
        display: flex !important;
        align-items: center !important;
        gap: 12px !important;
    }
    
    .linear-login-btn .stButton > button {
        background: transparent !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        color: rgba(255, 255, 255, 0.8) !important;
        font-size: 0.9rem !important;
        padding: 8px 16px !important;
        border-radius: 6px !important;
    }
    
    .linear-login-btn .stButton > button:hover {
        background: rgba(255, 255, 255, 0.1) !important;
        color: white !important;
    }
    
    .linear-signup-btn .stButton > button {
        background: white !important;
        border: 1px solid white !important;
        color: #000 !important;
        font-size: 0.9rem !important;
        padding: 8px 16px !important;
        border-radius: 6px !important;
    }
    
    .linear-signup-btn .stButton > button:hover {
        background: rgba(255, 255, 255, 0.9) !important;
    }
    
    /* 모바일 반응형 */
    @media (max-width: 768px) {
        .linear-navbar-content {
            padding: 12px 16px !important;
            height: 56px !important;
        }
        
        .linear-navbar-nav {
            gap: 16px !important;
        }
        
        .linear-nav-item {
            font-size: 0.8rem !important;
            padding: 6px 12px !important;
        }
        
        .linear-navbar-brand {
            font-size: 1rem !important;
        }
    }
    </style>
    """
    
    st.markdown(navbar_css, unsafe_allow_html=True)
    
    # 네비게이션 바 렌더링
    with st.container():
        st.markdown('<div class="linear-navbar-wrapper">', unsafe_allow_html=True)
        st.markdown('<div class="linear-navbar-content">', unsafe_allow_html=True)
        
        # 3개 영역으로 분할: 브랜드, 네비게이션, 액션
        brand_col, nav_col, action_col = st.columns([2, 6, 2])
        
        # 브랜드 (로고) - 왼쪽
        with brand_col:
            st.markdown(f'<div class="linear-navbar-brand">🔷 {brand_name}</div>', unsafe_allow_html=True)
        
        # 네비게이션 메뉴 - 가운데
        with nav_col:
            if nav_items:
                # Streamlit 버튼으로 메뉴 생성
                cols = st.columns(len(nav_items))
                for i, item in enumerate(nav_items):
                    with cols[i]:
                        if st.button(
                            item["label"], 
                            key=f"nav_{item['label']}_{navbar_key}",
                            help=f"{item['label']} 메뉴"
                        ):
                            st.info(f"{item['label']} 클릭됨")
        
        # 액션 버튼 (로그인/사인업) - 오른쪽
        with action_col:
            st.markdown('<div class="linear-navbar-actions">', unsafe_allow_html=True)
            login_col, signup_col = st.columns(2)
            
            with login_col:
                st.markdown('<div class="linear-login-btn">', unsafe_allow_html=True)
                if st.button("Log in", key=f"{navbar_key}_login"):
                    st.info("로그인 클릭됨")
                st.markdown('</div>', unsafe_allow_html=True)
            
            with signup_col:
                st.markdown('<div class="linear-signup-btn">', unsafe_allow_html=True)
                if st.button("Sign up", key=f"{navbar_key}_signup"):
                    st.info("사인업 클릭됨")
                st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)  # linear-navbar-content
        st.markdown('</div>', unsafe_allow_html=True)  # linear-navbar-wrapper


# 헬퍼 함수들
def _get_button_color(variant: str) -> str:
    """버튼 색상 반환"""
    colors = {
        "primary": "var(--linear-brand)",
        "secondary": "var(--linear-text-secondary)",
        "danger": "var(--linear-error)",
        "success": "var(--linear-success)",
        "warning": "var(--linear-warning)"
    }
    return colors.get(variant, "var(--linear-text-primary)")


def _get_button_bg(variant: str) -> str:
    """버튼 배경색 반환"""
    backgrounds = {
        "primary": "transparent",
        "secondary": "var(--linear-bg-tertiary)",
        "danger": "transparent",
        "success": "transparent",
        "warning": "transparent"
    }
    return backgrounds.get(variant, "transparent")


def _get_button_hover_bg(variant: str) -> str:
    """버튼 호버 배경색 반환"""
    hover_bgs = {
        "primary": "rgba(94, 106, 210, 0.1)",
        "secondary": "var(--linear-bg-quaternary)",
        "danger": "rgba(239, 68, 68, 0.1)",
        "success": "rgba(34, 197, 94, 0.1)",
        "warning": "rgba(245, 158, 11, 0.1)"
    }
    return hover_bgs.get(variant, "var(--linear-bg-tertiary)")


def _get_button_padding(size: str) -> str:
    """버튼 패딩 반환"""
    paddings = {
        "small": "6px 12px",
        "medium": "8px 16px",
        "large": "12px 24px"
    }
    return paddings.get(size, "8px 16px")


def _get_card_bg(variant: str) -> str:
    """카드 배경색 반환"""
    backgrounds = {
        "default": "var(--linear-bg-secondary)",
        "elevated": "var(--linear-bg-primary)",
        "outlined": "transparent"
    }
    return backgrounds.get(variant, "var(--linear-bg-secondary)")


def linear_chip(
    label: str,
    key: Optional[str] = None,
    variant: str = "default",
    selected: bool = False,
    size: str = "medium",
    disabled: bool = False,
    **kwargs
) -> bool:
    """
    Linear 스타일 칩 컴포넌트 (모드 선택용)
    
    Args:
        label: 칩 텍스트
        key: Streamlit key
        variant: "default", "primary", "secondary"
        selected: 선택 상태
        size: "small", "medium", "large"
        disabled: 비활성화 여부
        **kwargs: st.button에 전달할 추가 인자
    
    Returns:
        칩 클릭 여부
    """
    if st is None:
        return False
    
    # 칩 스타일 CSS 적용
    chip_css = f"""
    <style>
    .linear-chip-{variant} {{
        font-family: var(--linear-font-primary) !important;
        font-weight: var(--linear-font-weight-medium) !important;
        font-size: var(--linear-font-size-regular) !important;
        line-height: var(--linear-line-height-normal) !important;
        border-radius: 20px !important;
        border: 1px solid var(--linear-border) !important;
        background: var(--linear-bg-secondary) !important;
        color: var(--linear-text-secondary) !important;
        padding: {_get_chip_padding(size)} !important;
        transition: all 0.2s ease !important;
        text-align: center !important;
        min-width: 60px !important;
        cursor: pointer !important;
        box-shadow: none !important;
    }}
    
    .linear-chip-{variant}:hover {{
        background: var(--linear-bg-tertiary) !important;
        border-color: var(--linear-border-hover) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1) !important;
    }}
    
    .linear-chip-{variant}.selected {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        border-color: transparent !important;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4) !important;
    }}
    
    .linear-chip-{variant}.selected:hover {{
        background: linear-gradient(135deg, #5a6fd8 0%, #6a4190 100%) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5) !important;
    }}
    </style>
    """
    
    st.markdown(chip_css, unsafe_allow_html=True)
    
    # 선택 상태에 따른 클래스 적용
    chip_class = f"linear-chip-{variant}"
    if selected:
        chip_class += " selected"
    
    # 버튼 렌더링
    return st.button(
        label,
        key=key,
        disabled=disabled,
        **kwargs
    )


def linear_gradient_button(
    label: str,
    key: Optional[str] = None,
    gradient: str = "primary",
    size: str = "medium",
    disabled: bool = False,
    **kwargs
) -> bool:
    """
    Linear 스타일 그라디언트 버튼 컴포넌트
    
    Args:
        label: 버튼 텍스트
        key: Streamlit key
        gradient: "primary", "secondary", "tertiary"
        size: "small", "medium", "large"
        disabled: 비활성화 여부
        **kwargs: st.button에 전달할 추가 인자
    
    Returns:
        버튼 클릭 여부
    """
    if st is None:
        return False
    
    # 그라디언트 스타일 CSS 적용
    gradient_css = f"""
    <style>
    .linear-gradient-{gradient} {{
        font-family: var(--linear-font-primary) !important;
        font-weight: var(--linear-font-weight-semibold) !important;
        font-size: var(--linear-font-size-regular) !important;
        line-height: var(--linear-line-height-normal) !important;
        border-radius: var(--linear-radius-{size}) !important;
        border: none !important;
        background: {_get_gradient_bg(gradient)} !important;
        color: white !important;
        padding: {_get_button_padding(size)} !important;
        transition: all 0.2s ease !important;
        cursor: pointer !important;
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3) !important;
    }}
    
    .linear-gradient-{gradient}:hover {{
        background: {_get_gradient_hover_bg(gradient)} !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4) !important;
    }}
    </style>
    """
    
    st.markdown(gradient_css, unsafe_allow_html=True)
    
    # 버튼 렌더링
    return st.button(
        label,
        key=key,
        disabled=disabled,
        **kwargs
    )


def _get_chip_padding(size: str) -> str:
    """칩 패딩 반환"""
    paddings = {
        "small": "6px 12px",
        "medium": "8px 16px",
        "large": "10px 20px"
    }
    return paddings.get(size, "8px 16px")


def _get_gradient_bg(gradient: str) -> str:
    """그라디언트 배경 반환"""
    gradients = {
        "primary": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
        "secondary": "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
        "tertiary": "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)"
    }
    return gradients.get(gradient, "linear-gradient(135deg, #667eea 0%, #764ba2 100%)")


def _get_gradient_hover_bg(gradient: str) -> str:
    """그라디언트 호버 배경 반환"""
    hover_gradients = {
        "primary": "linear-gradient(135deg, #5a6fd8 0%, #6a4190 100%)",
        "secondary": "linear-gradient(135deg, #e881f9 0%, #f3455a 100%)",
        "tertiary": "linear-gradient(135deg, #3d9bfe 0%, #00d4fe 100%)"
    }
    return hover_gradients.get(gradient, "linear-gradient(135deg, #5a6fd8 0%, #6a4190 100%)")


def _get_card_border(variant: str) -> str:
    """카드 테두리색 반환"""
    borders = {
        "default": "var(--linear-border-primary)",
        "elevated": "var(--linear-border-secondary)",
        "outlined": "var(--linear-border-primary)"
    }
    return borders.get(variant, "var(--linear-border-primary)")


def _get_card_shadow(variant: str) -> str:
    """카드 그림자 반환"""
    shadows = {
        "default": "var(--linear-shadow-sm)",
        "elevated": "var(--linear-shadow-md)",
        "outlined": "none"
    }
    return shadows.get(variant, "var(--linear-shadow-sm)")


def linear_floating_card(
    content: Any,
    title: Optional[str] = None,
    variant: str = "default",
    padding: str = "large",
    **kwargs
) -> None:
    """
    떠있는 효과가 있는 Linear 스타일 카드 컴포넌트
    
    Args:
        content: 카드 내용
        title: 카드 제목 (선택사항)
        variant: "default", "elevated", "glass"
        padding: "small", "medium", "large", "xlarge"
        **kwargs: st.container에 전달할 추가 인자
    """
    if st is None:
        return
    
    # 떠있는 카드 CSS
    floating_card_css = f"""
    <style>
    .linear-floating-card-{variant} {{
        background: {_get_floating_card_bg(variant)} !important;
        border: 1px solid {_get_floating_card_border(variant)} !important;
        border-radius: 24px !important;
        padding: {_get_floating_card_padding(padding)} !important;
        margin: 8px 0 !important;
        box-shadow: {_get_floating_card_shadow(variant)} !important;
        backdrop-filter: blur(18px) !important;
        transition: all 0.35s ease !important;
        position: relative !important;
    }}
    
    .linear-floating-card-{variant}:hover {{
        transform: translateY(-8px) !important;
        box-shadow: {_get_floating_card_hover_shadow(variant)} !important;
    }}
    
    .linear-floating-card-title {{
        font-family: 'Poppins', 'Inter', system-ui, sans-serif !important;
        font-weight: 600 !important;
        font-size: 1.125rem !important;
        line-height: 1.4 !important;
        color: #f5f7ff !important;
        margin-bottom: 12px !important;
    }}
    </style>
    """
    
    st.markdown(floating_card_css, unsafe_allow_html=True)
    
    # 카드 렌더링
    with st.container(**kwargs):
        if title:
            st.markdown(f'<div class="linear-floating-card-title">{title}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="linear-floating-card-{variant}">', unsafe_allow_html=True)
        content
        st.markdown('</div>', unsafe_allow_html=True)


def linear_floating_button(
    label: str,
    key: Optional[str] = None,
    variant: str = "primary",
    size: str = "medium",
    disabled: bool = False,
    **kwargs
) -> bool:
    """
    떠있는 효과가 있는 Linear 스타일 버튼 컴포넌트
    
    Args:
        label: 버튼 텍스트
        key: Streamlit key
        variant: "primary", "secondary", "gradient"
        size: "small", "medium", "large"
        disabled: 비활성화 여부
        **kwargs: st.button에 전달할 추가 인자
    
    Returns:
        버튼 클릭 여부
    """
    if st is None:
        return False
    
    # 떠있는 버튼 CSS
    floating_button_css = f"""
    <style>
    .linear-floating-button-{variant} {{
        font-family: 'Inter', system-ui, sans-serif !important;
        font-weight: 600 !important;
        font-size: {_get_floating_button_font_size(size)} !important;
        line-height: 1.4 !important;
        border-radius: 16px !important;
        border: none !important;
        background: {_get_floating_button_bg(variant)} !important;
        color: {_get_floating_button_color(variant)} !important;
        padding: {_get_floating_button_padding(size)} !important;
        transition: all 0.3s ease !important;
        cursor: pointer !important;
        box-shadow: 0 20px 45px rgba(12, 13, 34, 0.45) !important;
        position: relative !important;
    }}
    
    .linear-floating-button-{variant}:hover {{
        transform: translateY(-3px) !important;
        box-shadow: 0 25px 40px rgba(108, 99, 255, 0.35) !important;
    }}
    
    .linear-floating-button-{variant}:active {{
        transform: translateY(-2px) !important;
    }}
    
    /* Streamlit 버튼 오버라이드 */
    div[data-testid="stButton"] > button,
    .stButton > button {{
        font-family: 'Inter', system-ui, sans-serif !important;
        font-weight: 600 !important;
        font-size: {_get_floating_button_font_size(size)} !important;
        line-height: 1.4 !important;
        border-radius: 16px !important;
        border: none !important;
        background: {_get_floating_button_bg(variant)} !important;
        color: {_get_floating_button_color(variant)} !important;
        padding: {_get_floating_button_padding(size)} !important;
        transition: all 0.3s ease !important;
        cursor: pointer !important;
        box-shadow: 0 20px 45px rgba(12, 13, 34, 0.45) !important;
        position: relative !important;
        min-height: 44px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }}
    
    div[data-testid="stButton"] > button:hover,
    .stButton > button:hover {{
        transform: translateY(-3px) !important;
        box-shadow: 0 25px 40px rgba(108, 99, 255, 0.35) !important;
    }}
    
    div[data-testid="stButton"] > button:active,
    .stButton > button:active {{
        transform: translateY(-2px) !important;
    }}
    </style>
    """
    
    st.markdown(floating_button_css, unsafe_allow_html=True)
    
    # 버튼 렌더링
    return st.button(
        label,
        key=key,
        disabled=disabled,
        **kwargs
    )


def linear_floating_chip(
    label: str,
    key: Optional[str] = None,
    variant: str = "default",
    selected: bool = False,
    size: str = "medium",
    disabled: bool = False,
    **kwargs
) -> bool:
    """
    떠있는 효과가 있는 Linear 스타일 칩 컴포넌트
    
    Args:
        label: 칩 텍스트
        key: Streamlit key
        variant: "default", "primary", "secondary"
        selected: 선택 상태
        size: "small", "medium", "large"
        disabled: 비활성화 여부
        **kwargs: st.button에 전달할 추가 인자
    
    Returns:
        칩 클릭 여부
    """
    if st is None:
        return False
    
    # 떠있는 칩 CSS
    floating_chip_css = f"""
    <style>
    .linear-floating-chip-{variant} {{
        font-family: 'Inter', system-ui, sans-serif !important;
        font-weight: 600 !important;
        font-size: {_get_floating_chip_font_size(size)} !important;
        line-height: 1.4 !important;
        border-radius: 999px !important;
        border: 1px solid {_get_floating_chip_border(variant, selected)} !important;
        background: {_get_floating_chip_bg(variant, selected)} !important;
        color: {_get_floating_chip_color(variant, selected)} !important;
        padding: {_get_floating_chip_padding(size)} !important;
        transition: all 0.3s ease !important;
        cursor: pointer !important;
        box-shadow: {_get_floating_chip_shadow(variant, selected)} !important;
        position: relative !important;
        min-width: 80px !important;
        text-align: center !important;
    }}
    
    .linear-floating-chip-{variant}:hover {{
        transform: translateY(-2px) !important;
        box-shadow: {_get_floating_chip_hover_shadow(variant, selected)} !important;
    }}
    
    /* Streamlit 버튼 오버라이드 */
    div[data-testid="stButton"] > button,
    .stButton > button {{
        font-family: 'Inter', system-ui, sans-serif !important;
        font-weight: 600 !important;
        font-size: {_get_floating_chip_font_size(size)} !important;
        line-height: 1.4 !important;
        border-radius: 999px !important;
        border: 1px solid {_get_floating_chip_border(variant, selected)} !important;
        background: {_get_floating_chip_bg(variant, selected)} !important;
        color: {_get_floating_chip_color(variant, selected)} !important;
        padding: {_get_floating_chip_padding(size)} !important;
        transition: all 0.3s ease !important;
        cursor: pointer !important;
        box-shadow: {_get_floating_chip_shadow(variant, selected)} !important;
        position: relative !important;
        min-height: 40px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }}
    
    div[data-testid="stButton"] > button:hover,
    .stButton > button:hover {{
        transform: translateY(-2px) !important;
        box-shadow: {_get_floating_chip_hover_shadow(variant, selected)} !important;
    }}
    </style>
    """
    
    st.markdown(floating_chip_css, unsafe_allow_html=True)
    
    # 버튼 렌더링
    return st.button(
        label,
        key=key,
        disabled=disabled,
        **kwargs
    )


def linear_circular_progress(
    progress: float,
    size: int = 120,
    stroke_width: int = 8,
    color: str = "primary",
    show_percentage: bool = True,
    label: Optional[str] = None,
    key: Optional[str] = None
) -> None:
    """
    원형 진행바 컴포넌트
    
    Args:
        progress: 진행률 (0.0 ~ 1.0)
        size: 원형 크기 (픽셀)
        stroke_width: 선 두께
        color: 색상 테마 ("primary", "secondary", "success", "warning", "danger")
        show_percentage: 퍼센트 표시 여부
        label: 라벨 텍스트
    """
    if st is None:
        return
    
    # 진행률을 0-100 범위로 변환
    percentage = int(progress * 100)
    
    # 원형 진행바 CSS
    progress_css = f"""
    <style>
    .linear-circular-progress {{
        display: inline-flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
    }}
    
    .linear-circular-progress-svg {{
        transform: rotate(-90deg);
    }}
    
    .linear-circular-progress-bg {{
        fill: none;
        stroke: rgba(255, 255, 255, 0.1);
        stroke-width: {stroke_width};
    }}
    
    .linear-circular-progress-fill {{
        fill: none;
        stroke: {_get_progress_color(color)};
        stroke-width: {stroke_width};
        stroke-linecap: round;
        stroke-dasharray: {2 * 3.14159 * (size/2 - stroke_width/2)};
        stroke-dashoffset: {2 * 3.14159 * (size/2 - stroke_width/2) * (1 - progress)};
        transition: stroke-dashoffset 0.5s ease;
    }}
    
    .linear-circular-progress-text {{
        font-family: 'Inter', system-ui, sans-serif;
        font-weight: 700;
        font-size: 1.5rem;
        color: {_get_progress_color(color)};
        text-anchor: middle;
        dominant-baseline: middle;
    }}
    
    .linear-circular-progress-label {{
        font-family: 'Inter', system-ui, sans-serif;
        font-weight: 500;
        font-size: 0.875rem;
        color: #9aa6c8;
        text-align: center;
    }}
    </style>
    """
    
    st.markdown(progress_css, unsafe_allow_html=True)
    
    # SVG 원형 진행바 생성
    radius = size / 2 - stroke_width / 2
    circumference = 2 * 3.14159 * radius
    stroke_dashoffset = circumference * (1 - progress)
    
    progress_html = f"""
    <div class="linear-circular-progress">
        <svg class="linear-circular-progress-svg" width="{size}" height="{size}">
            <circle class="linear-circular-progress-bg" cx="{size/2}" cy="{size/2}" r="{radius}"/>
            <circle class="linear-circular-progress-fill" cx="{size/2}" cy="{size/2}" r="{radius}"/>
            {f'<text class="linear-circular-progress-text" x="{size/2}" y="{size/2}">{percentage}%</text>' if show_percentage else ''}
        </svg>
        {f'<div class="linear-circular-progress-label">{label}</div>' if label else ''}
    </div>
    """
    
    st.markdown(progress_html, unsafe_allow_html=True)


def linear_modern_background() -> None:
    """
    모던한 그라디언트 배경 적용
    """
    if st is None:
        return
    
    background_css = """
    <style>
    .stApp {
        background: radial-gradient(circle at 20% 20%, rgba(108, 99, 255, 0.35), transparent 55%),
                    radial-gradient(circle at 75% 15%, rgba(75, 211, 192, 0.25), transparent 45%),
                    linear-gradient(160deg, #101739 0%, #070817 100%) !important;
        color: #f5f7ff !important;
    }
    
    .stApp > div {
        background: transparent !important;
    }
    
    .main .block-container {
        background: transparent !important;
        padding-top: 2rem !important;
    }
    
    /* 스크롤바 스타일링 */
    ::-webkit-scrollbar {
        width: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(16, 23, 57, 0.3);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: rgba(108, 99, 255, 0.6);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(108, 99, 255, 0.8);
    }
    </style>
    """
    
    st.markdown(background_css, unsafe_allow_html=True)


def linear_modern_input_pill(
    placeholder: str = "Enter your email",
    button_text: str = "Get Started",
    key: Optional[str] = None
) -> Tuple[str, bool]:
    """
    모던한 입력 필드와 버튼이 결합된 pill 형태 컴포넌트
    
    Args:
        placeholder: 입력 필드 플레이스홀더
        button_text: 버튼 텍스트
        key: Streamlit key
    
    Returns:
        (입력값, 버튼 클릭 여부)
    """
    if st is None:
        return "", False
    
    # 모던 입력 pill CSS
    input_pill_css = """
    <style>
    .linear-input-pill {
        display: grid;
        grid-template-columns: 1fr auto;
        align-items: center;
        background: rgba(16, 19, 45, 0.85);
        border-radius: 999px;
        padding: 6px;
        border: 1px solid rgba(255, 255, 255, 0.06);
        width: min(420px, 100%);
        margin: 16px 0;
    }
    
    .linear-input-pill input {
        background: transparent;
        border: none;
        color: #f5f7ff;
        padding: 12px 18px;
        font-size: 15px;
        outline: none;
        font-family: 'Inter', system-ui, sans-serif;
    }
    
    .linear-input-pill input::placeholder {
        color: #b4bbd9;
    }
    
    .linear-input-pill button {
        background: #6c63ff;
        border: none;
        color: #ffffff;
        padding: 12px 24px;
        border-radius: 999px;
        font-weight: 600;
        cursor: pointer;
        transition: transform 0.3s ease;
        font-family: 'Inter', system-ui, sans-serif;
    }
    
    .linear-input-pill button:hover {
        transform: translateY(-2px);
    }
    
    /* Streamlit 입력 필드 오버라이드 */
    div[data-testid="stTextInput"] {
        background: transparent !important;
        border: none !important;
    }
    
    div[data-testid="stTextInput"] input {
        background: transparent !important;
        border: none !important;
        color: #f5f7ff !important;
        padding: 12px 18px !important;
        font-size: 15px !important;
        font-family: 'Inter', system-ui, sans-serif !important;
    }
    
    div[data-testid="stTextInput"] input::placeholder {
        color: #b4bbd9 !important;
    }
    </style>
    """
    
    st.markdown(input_pill_css, unsafe_allow_html=True)
    
    # 입력 필드와 버튼 렌더링
    col1, col2 = st.columns([3, 1])
    
    with col1:
        user_input = st.text_input(
            placeholder,
            key=f"{key}_input" if key else None,
            label_visibility="collapsed"
        )
    
    with col2:
        button_clicked = st.button(
            button_text,
            key=f"{key}_button" if key else None,
            type="primary"
        )
    
    return user_input, button_clicked


# 헬퍼 함수들
def _get_floating_card_bg(variant: str) -> str:
    """떠있는 카드 배경색 반환"""
    backgrounds = {
        "default": "rgba(30, 41, 59, 0.8)",
        "elevated": "rgba(15, 23, 42, 0.9)",
        "glass": "rgba(255, 255, 255, 0.05)"
    }
    return backgrounds.get(variant, "rgba(30, 41, 59, 0.8)")


def _get_floating_card_border(variant: str) -> str:
    """떠있는 카드 테두리색 반환"""
    borders = {
        "default": "rgba(255, 255, 255, 0.1)",
        "elevated": "rgba(255, 255, 255, 0.2)",
        "glass": "rgba(255, 255, 255, 0.1)"
    }
    return borders.get(variant, "rgba(255, 255, 255, 0.1)")


def _get_floating_card_padding(padding: str) -> str:
    """떠있는 카드 패딩 반환"""
    paddings = {
        "small": "12px",
        "medium": "16px",
        "large": "24px",
        "xlarge": "32px"
    }
    return paddings.get(padding, "24px")


def _get_floating_card_shadow(variant: str) -> str:
    """떠있는 카드 그림자 반환"""
    shadows = {
        "default": "0 4px 20px rgba(0, 0, 0, 0.3)",
        "elevated": "0 8px 32px rgba(0, 0, 0, 0.4)",
        "glass": "0 4px 20px rgba(0, 0, 0, 0.2)"
    }
    return shadows.get(variant, "0 4px 20px rgba(0, 0, 0, 0.3)")


def _get_floating_card_hover_shadow(variant: str) -> str:
    """떠있는 카드 호버 그림자 반환"""
    shadows = {
        "default": "0 12px 40px rgba(0, 0, 0, 0.4)",
        "elevated": "0 16px 48px rgba(0, 0, 0, 0.5)",
        "glass": "0 8px 32px rgba(0, 0, 0, 0.3)"
    }
    return shadows.get(variant, "0 12px 40px rgba(0, 0, 0, 0.4)")


def _get_floating_button_bg(variant: str) -> str:
    """떠있는 버튼 배경색 반환"""
    backgrounds = {
        "primary": "linear-gradient(135deg, #7b5cff, #5f4bff)",
        "secondary": "rgba(255, 255, 255, 0.1)",
        "gradient": "linear-gradient(135deg, #667eea, #764ba2)"
    }
    return backgrounds.get(variant, "linear-gradient(135deg, #7b5cff, #5f4bff)")


def _get_floating_button_color(variant: str) -> str:
    """떠있는 버튼 텍스트 색상 반환"""
    colors = {
        "primary": "white",
        "secondary": "#ffffff",
        "gradient": "white"
    }
    return colors.get(variant, "white")


def _get_floating_button_font_size(size: str) -> str:
    """떠있는 버튼 폰트 크기 반환"""
    sizes = {
        "small": "0.875rem",
        "medium": "1rem",
        "large": "1.125rem"
    }
    return sizes.get(size, "1rem")


def _get_floating_button_padding(size: str) -> str:
    """떠있는 버튼 패딩 반환"""
    paddings = {
        "small": "8px 16px",
        "medium": "12px 24px",
        "large": "16px 32px"
    }
    return paddings.get(size, "12px 24px")


def _get_floating_button_shadow(variant: str) -> str:
    """떠있는 버튼 그림자 반환"""
    shadows = {
        "primary": "0 8px 32px rgba(123, 92, 255, 0.3)",
        "secondary": "0 4px 20px rgba(0, 0, 0, 0.3)",
        "gradient": "0 8px 32px rgba(102, 126, 234, 0.3)"
    }
    return shadows.get(variant, "0 8px 32px rgba(123, 92, 255, 0.3)")


def _get_floating_button_hover_shadow(variant: str) -> str:
    """떠있는 버튼 호버 그림자 반환"""
    shadows = {
        "primary": "0 12px 40px rgba(123, 92, 255, 0.4)",
        "secondary": "0 8px 32px rgba(0, 0, 0, 0.4)",
        "gradient": "0 12px 40px rgba(102, 126, 234, 0.4)"
    }
    return shadows.get(variant, "0 12px 40px rgba(123, 92, 255, 0.4)")


def _get_floating_chip_bg(variant: str, selected: bool) -> str:
    """떠있는 칩 배경색 반환"""
    if selected:
        return "linear-gradient(135deg, #7b5cff, #5f4bff)"
    
    backgrounds = {
        "default": "rgba(255, 255, 255, 0.05)",
        "primary": "rgba(123, 92, 255, 0.1)",
        "secondary": "rgba(255, 255, 255, 0.1)"
    }
    return backgrounds.get(variant, "rgba(255, 255, 255, 0.05)")


def _get_floating_chip_color(variant: str, selected: bool) -> str:
    """떠있는 칩 텍스트 색상 반환"""
    if selected:
        return "white"
    
    colors = {
        "default": "#9aa6c8",
        "primary": "#7b5cff",
        "secondary": "#ffffff"
    }
    return colors.get(variant, "#9aa6c8")


def _get_floating_chip_border(variant: str, selected: bool) -> str:
    """떠있는 칩 테두리색 반환"""
    if selected:
        return "transparent"
    
    borders = {
        "default": "rgba(255, 255, 255, 0.1)",
        "primary": "rgba(123, 92, 255, 0.3)",
        "secondary": "rgba(255, 255, 255, 0.2)"
    }
    return borders.get(variant, "rgba(255, 255, 255, 0.1)")


def _get_floating_chip_font_size(size: str) -> str:
    """떠있는 칩 폰트 크기 반환"""
    sizes = {
        "small": "0.75rem",
        "medium": "0.875rem",
        "large": "1rem"
    }
    return sizes.get(size, "0.875rem")


def _get_floating_chip_padding(size: str) -> str:
    """떠있는 칩 패딩 반환"""
    paddings = {
        "small": "6px 12px",
        "medium": "8px 16px",
        "large": "10px 20px"
    }
    return paddings.get(size, "8px 16px")


def _get_floating_chip_shadow(variant: str, selected: bool) -> str:
    """떠있는 칩 그림자 반환"""
    if selected:
        return "0 4px 15px rgba(123, 92, 255, 0.4)"
    
    shadows = {
        "default": "0 2px 8px rgba(0, 0, 0, 0.2)",
        "primary": "0 2px 8px rgba(123, 92, 255, 0.2)",
        "secondary": "0 2px 8px rgba(0, 0, 0, 0.3)"
    }
    return shadows.get(variant, "0 2px 8px rgba(0, 0, 0, 0.2)")


def _get_floating_chip_hover_shadow(variant: str, selected: bool) -> str:
    """떠있는 칩 호버 그림자 반환"""
    if selected:
        return "0 6px 20px rgba(123, 92, 255, 0.5)"
    
    shadows = {
        "default": "0 4px 12px rgba(0, 0, 0, 0.3)",
        "primary": "0 4px 12px rgba(123, 92, 255, 0.3)",
        "secondary": "0 4px 12px rgba(0, 0, 0, 0.4)"
    }
    return shadows.get(variant, "0 4px 12px rgba(0, 0, 0, 0.3)")


def _get_progress_color(color: str) -> str:
    """진행바 색상 반환"""
    colors = {
        "primary": "#7b5cff",
        "secondary": "#5f4bff",
        "success": "#10b981",
        "warning": "#f59e0b",
        "danger": "#ef4444"
    }
    return colors.get(color, "#7b5cff")
