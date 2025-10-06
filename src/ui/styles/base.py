"""
Base UI Styles Module

Contains fundamental styles for the application:
- Streamlit default UI hiding
- Basic layout settings
- Common variables and mixins
"""

import streamlit as st


def inject_base_styles():
    """Inject base styles including Streamlit UI hiding and basic layout."""
    if st.session_state.get("_base_styles_injected"):
        return
    
    st.session_state["_base_styles_injected"] = True
    
    st.markdown(
        """
        <style>
        /* Streamlit 기본 네비게이션 및 사이드바 숨김 */
        nav[data-testid='stSidebarNav']{display:none!important;}
        div[data-testid='stSidebarNav']{display:none!important;}
        section[data-testid='stSidebar']{display:none!important;}
        section[data-testid='stSidebar'] [data-testid='stSidebarNav']{display:none!important;}
        section[data-testid='stSidebar'] ul[role='list']{display:none!important;}
        
        /* Linear 네비게이션 바 가로 레이아웃 강제 적용 */
        .linear-navbar-container{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;align-items:center!important;justify-content:space-between!important;}
        .linear-navbar-container > *{display:inline-block!important;vertical-align:middle!important;}
        .linear-navbar-nav{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;align-items:center!important;list-style:none!important;margin:0!important;padding:0!important;}
        .linear-navbar-nav li{display:inline-block!important;margin:0!important;padding:0!important;}
        .linear-navbar-nav-item{display:inline-block!important;vertical-align:middle!important;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_linear_theme_variables():
    """Inject Linear theme CSS variables."""
    if st.session_state.get("_linear_theme_variables_injected"):
        return
    
    st.session_state["_linear_theme_variables_injected"] = True
    
    st.markdown(
        """
        <style>
        :root {
          /* Linear 테마 색상 변수 */
          --linear-bg-primary: #08090a;
          --linear-bg-secondary: #1c1c1f;
          --linear-bg-tertiary: #232326;
          --linear-bg-quaternary: #2a2a2d;
          --linear-bg-hover: #2a2a2d;
          --linear-bg-active: #3a3a3d;
          
          --linear-text-primary: #ffffff;
          --linear-text-secondary: #b3b3b3;
          --linear-text-tertiary: #8a8a8a;
          --linear-text-quaternary: #6a6a6a;
          
          --linear-border-primary: #3a3a3d;
          --linear-border-secondary: #2a2a2d;
          --linear-border-tertiary: #1a1a1d;
          
          --linear-brand: #5e6ad2;
          --linear-brand-hover: #4c56b8;
          --linear-brand-active: #3a429e;
          
          --linear-success: #34d399;
          --linear-warning: #fbbf24;
          --linear-error: #ef4444;
          --linear-info: #3b82f6;
          
          /* Linear 폰트 변수 */
          --linear-font-primary: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
          --linear-font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
          
          --linear-font-size-xs: 12px;
          --linear-font-size-sm: 14px;
          --linear-font-size-base: 16px;
          --linear-font-size-lg: 18px;
          --linear-font-size-xl: 20px;
          --linear-font-size-2xl: 24px;
          --linear-font-size-3xl: 30px;
          
          --linear-font-weight-normal: 400;
          --linear-font-weight-medium: 500;
          --linear-font-weight-semibold: 600;
          --linear-font-weight-bold: 700;
          
          --linear-line-height-tight: 1.25;
          --linear-line-height-normal: 1.5;
          --linear-line-height-relaxed: 1.75;
          
          /* Linear 간격 변수 */
          --linear-spacing-xs: 4px;
          --linear-spacing-sm: 8px;
          --linear-spacing-md: 16px;
          --linear-spacing-lg: 24px;
          --linear-spacing-xl: 32px;
          --linear-spacing-2xl: 48px;
          
          /* Linear 패딩 변수 */
          --linear-padding-xs: 4px 8px;
          --linear-padding-sm: 8px 12px;
          --linear-padding-md: 12px 16px;
          --linear-padding-lg: 16px 24px;
          --linear-padding-xl: 24px 32px;
          
          /* Linear 반지름 변수 */
          --linear-radius-sm: 4px;
          --linear-radius-md: 8px;
          --linear-radius-lg: 12px;
          --linear-radius-xl: 16px;
          --linear-radius-2xl: 24px;
          --linear-radius-full: 9999px;
          
          /* Linear 그림자 변수 */
          --linear-shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
          --linear-shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1);
          --linear-shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.1);
          --linear-shadow-xl: 0 20px 25px rgba(0, 0, 0, 0.1);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
