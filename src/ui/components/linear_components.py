# Linear 테마 기반 재사용 가능한 컴포넌트들
from __future__ import annotations
from typing import Any, Dict, List, Optional, Union
import streamlit as st
from .linear_theme import get_color, get_font_size, get_radius, get_padding


def linear_button(
    label: str,
    key: Optional[str] = None,
    variant: str = "primary",
    size: str = "medium",
    disabled: bool = False,
    use_container_width: bool = False,
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
        use_container_width: 컨테이너 너비 사용
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
    </style>
    """
    
    st.markdown(button_css, unsafe_allow_html=True)
    
    # 버튼 렌더링
    return st.button(
        label,
        key=key,
        disabled=disabled,
        use_container_width=use_container_width,
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
    
    /* 숫자 입력 필드 스타일 - 텍스트 입력과 동일하게 */
    .stNumberInput > div > div > input {
        border: 2px solid var(--linear-border-secondary) !important;
        background: var(--linear-bg-tertiary) !important;
        color: var(--linear-text-primary) !important;
        border-radius: var(--linear-radius-medium) !important;
        padding: 8px 12px !important;
        font-family: var(--linear-font-primary) !important;
        box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.2) !important;
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
    dismissible: bool = False
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
            st.markdown(f'<div class="linear-carousel-title">{title}</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="linear-carousel-container">', unsafe_allow_html=True)
        
        # 현재 아이템 표시
        if items:
            current_item = items[current_index]
            
            # 화살표와 아이템을 함께 배치
            col1, col2, col3 = st.columns([2, 6, 2])
            
            # 화살표 (이전)
            with col1:
                if show_arrows and len(items) > 1:
                    st.markdown('<div style="display: flex; align-items: center; justify-content: center; height: 100%; min-height: 200px;">', unsafe_allow_html=True)
                    if st.button("‹", key=f"{carousel_key}_prev", help="이전", use_container_width=True):
                        st.session_state[f"{carousel_key}_current"] = (current_index - 1) % len(items)
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
            
            # 현재 아이템
            with col2:
                st.markdown('<div class="linear-carousel-item">', unsafe_allow_html=True)
                
                # 이미지
                if "image" in current_item and current_item["image"]:
                    st.image(current_item["image"], use_container_width=True)
                
                # 제목
                if "title" in current_item:
                    st.markdown(f'<div class="linear-carousel-item-title">{current_item["title"]}</div>', unsafe_allow_html=True)
                
                # 내용
                if "content" in current_item:
                    st.markdown(f'<div class="linear-carousel-item-content">{current_item["content"]}</div>', unsafe_allow_html=True)
                
                # 액션 버튼
                if "action" in current_item and current_item["action"]:
                    action_key = f"carousel_action_{carousel_key}_{current_index}"
                    if linear_button(current_item["action"], variant="primary", size="small", key=action_key):
                        if "action_callback" in current_item:
                            current_item["action_callback"]()
                
                st.markdown('</div>', unsafe_allow_html=True)
            
            # 화살표 (다음)
            with col3:
                if show_arrows and len(items) > 1:
                    st.markdown('<div style="display: flex; align-items: center; justify-content: center; height: 100%; min-height: 200px;">', unsafe_allow_html=True)
                    if st.button("›", key=f"{carousel_key}_next", help="다음", use_container_width=True):
                        st.session_state[f"{carousel_key}_current"] = (current_index + 1) % len(items)
                        st.rerun()
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
                st.image(image_url, caption=image_alt, use_container_width=True)
            st.markdown(f'<div class="linear-image-card-title">{title}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="linear-image-card-content">{content}</div>', unsafe_allow_html=True)
            
        elif image_position == "left":
            # 이미지가 왼쪽에
            col1, col2 = st.columns([1, 2])
            with col1:
                if image_url:
                    st.image(image_url, caption=image_alt, use_container_width=True)
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
                    st.image(image_url, caption=image_alt, use_container_width=True)
                    
        elif image_position == "bottom":
            # 이미지가 아래에
            st.markdown(f'<div class="linear-image-card-title">{title}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="linear-image-card-content">{content}</div>', unsafe_allow_html=True)
            if image_url:
                st.image(image_url, caption=image_alt, use_container_width=True)
        
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
    
    # 네비게이션 바 CSS
    navbar_css = f"""
    <style>
    .linear-navbar {{
        background: #000000 !important;
        background-color: #000000 !important;
        border-bottom: 2px solid var(--linear-brand) !important;
        border-top: 1px solid var(--linear-border-primary) !important;
        padding: 0 !important;
        margin: -1rem -1rem 2rem -1rem !important;
        width: calc(100% + 2rem) !important;
        position: {'sticky' if sticky else 'relative'} !important;
        top: 0 !important;
        z-index: 1000 !important;
        backdrop-filter: blur(10px) !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.5) !important;
    }}
    
    /* 더 강력한 블랙 배경 오버라이드 */
    .linear-navbar,
    .linear-navbar *,
    .linear-navbar [data-testid="column"],
    .linear-navbar [data-testid="column"] > div {{
        background-color: #000000 !important;
    }}
    
    .linear-navbar-container {{
        max-width: 1200px !important;
        margin: 0 auto !important;
        padding: 0 1rem !important;
        display: flex !important;
        align-items: center !important;
        justify-content: space-between !important;
        height: 64px !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        width: 100% !important;
    }}
    
    /* 네비게이션 바 내 모든 요소 수직 정렬 최대 강화 */
    .linear-navbar * {{
        vertical-align: middle !important;
        line-height: 1 !important;
        margin: 0 !important;
        padding: 0 !important;
    }}
    
    .linear-navbar [data-testid="column"] {{
        vertical-align: middle !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        height: 64px !important;
        margin: 0 !important;
        padding: 0 !important;
    }}
    
    .linear-navbar [data-testid="column"] > div {{
        vertical-align: middle !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        height: 64px !important;
        margin: 0 !important;
        padding: 0 !important;
    }}
    
    /* 브랜드와 메뉴 텍스트 정렬 최대 강제 */
    .linear-navbar-brand, .linear-navbar-nav, .linear-navbar-user {{
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        height: 64px !important;
        line-height: 1 !important;
        margin: 0 !important;
        padding: 0 !important;
    }}
    
    .linear-navbar-brand-name, .linear-navbar-nav-link, .linear-navbar-user-name {{
        line-height: 1 !important;
        vertical-align: middle !important;
        margin: 0 !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
    }}
    
    /* Streamlit 기본 마진/패딩 완전 제거 */
    .linear-navbar .stMarkdown {{
        margin: 0 !important;
        padding: 0 !important;
    }}
    
    .linear-navbar .stMarkdown > div {{
        margin: 0 !important;
        padding: 0 !important;
    }}
    
    /* Streamlit 기본 스타일 오버라이드 */
    .linear-navbar-container > * {{
        display: inline-block !important;
        vertical-align: middle !important;
    }}
    
    .linear-navbar-brand {{
        display: flex !important;
        align-items: center !important;
        gap: 12px !important;
        text-decoration: none !important;
    }}
    
    .linear-navbar-logo {{
        width: 32px !important;
        height: 32px !important;
        border-radius: var(--linear-radius-medium) !important;
    }}
    
    .linear-navbar-brand-name {{
        font-family: var(--linear-font-primary) !important;
        font-weight: var(--linear-font-weight-semibold) !important;
        font-size: var(--linear-font-size-title3) !important;
        color: var(--linear-text-primary) !important;
        text-decoration: none !important;
    }}
    
    .linear-navbar-nav {{
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
        list-style: none !important;
        margin: 0 !important;
        padding: 0 !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        justify-content: center !important;
    }}
    
    .linear-navbar-nav li {{
        display: inline-block !important;
        margin: 0 !important;
        padding: 0 !important;
    }}
    
    .linear-navbar-nav-item {{
        display: flex !important;
        align-items: center !important;
    }}
    
    /* Streamlit columns 내에서 가로 배치 강제 */
    .linear-navbar [data-testid="column"] {{
        display: inline-block !important;
        vertical-align: top !important;
    }}
    
    .linear-navbar [data-testid="column"] > div {{
        display: inline-block !important;
        vertical-align: top !important;
    }}
    
    .linear-navbar-nav-link {{
        font-family: var(--linear-font-primary) !important;
        font-weight: var(--linear-font-weight-medium) !important;
        font-size: var(--linear-font-size-regular) !important;
        color: var(--linear-text-secondary) !important;
        text-decoration: none !important;
        padding: 8px 16px !important;
        border-radius: var(--linear-radius-medium) !important;
        transition: all 0.2s ease !important;
        border: 1px solid transparent !important;
        white-space: nowrap !important;
        display: inline-block !important;
        margin-right: 16px !important;
    }}
    
    .linear-navbar-nav-link:hover {{
        background: var(--linear-bg-tertiary) !important;
        color: var(--linear-text-primary) !important;
        border-color: var(--linear-border-primary) !important;
    }}
    
    .linear-navbar-nav-link.active {{
        background: rgba(94, 106, 210, 0.1) !important;
        color: var(--linear-brand) !important;
        border-color: var(--linear-brand) !important;
    }}
    
    .linear-navbar-user {{
        display: flex !important;
        align-items: center !important;
        gap: 12px !important;
    }}
    
    .linear-navbar-user-avatar {{
        width: 32px !important;
        height: 32px !important;
        border-radius: var(--linear-radius-full) !important;
        border: 1px solid var(--linear-border-primary) !important;
    }}
    
    .linear-navbar-user-name {{
        font-family: var(--linear-font-primary) !important;
        font-weight: var(--linear-font-weight-medium) !important;
        font-size: var(--linear-font-size-regular) !important;
        color: var(--linear-text-primary) !important;
    }}
    
    .linear-navbar-mobile-menu {{
        display: none !important;
    }}
    
    @media (max-width: 768px) {{
        .linear-navbar-nav {{
            display: none !important;
        }}
        .linear-navbar-mobile-menu {{
            display: block !important;
        }}
        .linear-navbar-user-name {{
            display: none !important;
        }}
    }}
    </style>
    """
    
    st.markdown(navbar_css, unsafe_allow_html=True)
    
    # 네비게이션 바 렌더링 - 완전한 HTML/CSS 방식
    # 메뉴 아이템 HTML 생성
    nav_html = ""
    if nav_items:
        for item in nav_items:
            link_class = "linear-navbar-nav-link"
            if item.get("active", False):
                link_class += " active"
            nav_html += f'<a href="{item.get("href", "#")}" class="{link_class}">{item["label"]}</a>'
    
    # 사용자 메뉴 HTML 생성
    user_html = ""
    if user_menu:
        user_avatar = ""
        if user_menu.get("avatar"):
            user_avatar = f'<img src="{user_menu["avatar"]}" class="linear-navbar-user-avatar" alt="Avatar">'
        user_html = f'<div class="linear-navbar-user">{user_avatar}<span class="linear-navbar-user-name">{user_menu["name"]}</span></div>'
    
    # 브랜드 로고 HTML 생성
    brand_logo_html = ""
    if brand_logo:
        brand_logo_html = f'<img src="{brand_logo}" class="linear-navbar-logo" alt="Logo">'
    
    # 완전한 네비게이션 바 HTML
    navbar_html = f"""
    <div class="linear-navbar">
        <div class="linear-navbar-container">
            <div class="linear-navbar-brand">
                {brand_logo_html}
                <span class="linear-navbar-brand-name">{brand_name}</span>
            </div>
            <div class="linear-navbar-nav">
                {nav_html}
            </div>
            {user_html}
        </div>
    </div>
    """
    
    st.markdown(navbar_html, unsafe_allow_html=True)
    
    # JavaScript로 DOM 직접 조작하여 레이아웃과 색상 강제 적용
    st.markdown(f"""
    <script>
    setTimeout(function() {{
        // 네비게이션 바 배경색 강제 적용
        const navbar = document.querySelector('.linear-navbar');
        if (navbar) {{
            navbar.style.backgroundColor = '#000000';
            navbar.style.background = '#000000';
        }}
        
        // 컨테이너 레이아웃 강제 적용
        const container = document.querySelector('.linear-navbar-container');
        if (container) {{
            container.style.display = 'flex';
            container.style.flexDirection = 'row';
            container.style.flexWrap = 'nowrap';
            container.style.alignItems = 'center';
            container.style.justifyContent = 'space-between';
            container.style.height = '64px';
            container.style.width = '100%';
        }}
        
        // 브랜드 정렬
        const brand = document.querySelector('.linear-navbar-brand');
        if (brand) {{
            brand.style.display = 'flex';
            brand.style.alignItems = 'center';
            brand.style.height = '64px';
        }}
        
        // 네비게이션 메뉴 정렬
        const nav = document.querySelector('.linear-navbar-nav');
        if (nav) {{
            nav.style.display = 'flex';
            nav.style.alignItems = 'center';
            nav.style.height = '64px';
            nav.style.gap = '16px';
        }}
        
        // 사용자 메뉴 정렬
        const user = document.querySelector('.linear-navbar-user');
        if (user) {{
            user.style.display = 'flex';
            user.style.alignItems = 'center';
            user.style.height = '64px';
        }}
        
        // 모든 링크 줄바꿈 방지
        const links = document.querySelectorAll('.linear-navbar-nav-link');
        links.forEach(function(link) {{
            link.style.whiteSpace = 'nowrap';
            link.style.display = 'inline-block';
        }});
    }}, 100);
    </script>
    """, unsafe_allow_html=True)


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
