# Linear 테마 시스템 - 중앙화된 테마 관리
from __future__ import annotations
from typing import Dict, Any
import streamlit as st

# Linear 테마 JSON 데이터
LINEAR_THEME = {
    "colors": {
        "primary": {
            "brand": "#5e6ad2",
            "accent": "#7170ff",
            "accentHover": "#828fff"
        },
        "background": {
            "primary": "#08090a",
            "secondary": "#1c1c1f", 
            "tertiary": "#232326",
            "quaternary": "#28282c",
            "translucent": "rgba(255,255,255,.05)"
        },
        "text": {
            "primary": "#f7f8f8",
            "secondary": "#d0d6e0",
            "tertiary": "#8a8f98",
            "quaternary": "#62666d"
        },
        "border": {
            "primary": "#23252a",
            "secondary": "#34343a",
            "tertiary": "#3e3e44",
            "translucent": "rgba(255,255,255,.05)"
        },
        "semantic": {
            "blue": "#4ea7fc",
            "red": "#eb5757", 
            "green": "#4cb782",
            "orange": "#fc7840",
            "yellow": "#f2c94c"
        }
    },
    
    "typography": {
        "fontFamily": {
            "primary": '"Inter Variable", "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, "Open Sans", "Helvetica Neue", sans-serif',
            "monospace": '"Berkeley Mono", ui-monospace, "SF Mono", Menlo, monospace'
        },
        "fontWeights": {
            "light": 300,
            "normal": 400,
            "medium": 510,
            "semibold": 590,
            "bold": 680
        },
        "fontSizes": {
            "micro": "0.6875rem",
            "mini": "0.75rem", 
            "small": "0.8125rem",
            "regular": "0.9375rem",
            "large": "1.125rem",
            "title1": "2.25rem",
            "title2": "1.5rem",
            "title3": "1.25rem"
        }
    },
    
    "spacing": {
        "radius": {
            "small": "4px",
            "medium": "8px", 
            "large": "12px",
            "xlarge": "16px",
            "xxlarge": "24px",
            "full": "9999px"
        },
        "padding": {
            "small": "8px",
            "medium": "12px",
            "large": "16px",
            "xlarge": "24px"
        }
    },
    
    "shadows": {
        "low": "0px 2px 4px rgba(0,0,0,.1)",
        "medium": "0px 4px 24px rgba(0,0,0,.2)",
        "high": "0px 7px 32px rgba(0,0,0,.35)"
    }
}


def get_theme_css() -> str:
    """Linear 테마 CSS 변수를 반환"""
    theme = LINEAR_THEME
    
    return f"""
    <style>
    :root {{
        /* Linear 테마 색상 변수 */
        --linear-bg-primary: {theme['colors']['background']['primary']};
        --linear-bg-secondary: {theme['colors']['background']['secondary']};
        --linear-bg-tertiary: {theme['colors']['background']['tertiary']};
        --linear-bg-quaternary: {theme['colors']['background']['quaternary']};
        --linear-bg-translucent: {theme['colors']['background']['translucent']};
        
        --linear-text-primary: {theme['colors']['text']['primary']};
        --linear-text-secondary: {theme['colors']['text']['secondary']};
        --linear-text-tertiary: {theme['colors']['text']['tertiary']};
        --linear-text-quaternary: {theme['colors']['text']['quaternary']};
        
        --linear-brand: {theme['colors']['primary']['brand']};
        --linear-accent: {theme['colors']['primary']['accent']};
        --linear-accent-hover: {theme['colors']['primary']['accentHover']};
        
        --linear-border-primary: {theme['colors']['border']['primary']};
        --linear-border-secondary: {theme['colors']['border']['secondary']};
        --linear-border-tertiary: {theme['colors']['border']['tertiary']};
        --linear-border-translucent: {theme['colors']['border']['translucent']};
        
        --linear-blue: {theme['colors']['semantic']['blue']};
        --linear-red: {theme['colors']['semantic']['red']};
        --linear-green: {theme['colors']['semantic']['green']};
        --linear-orange: {theme['colors']['semantic']['orange']};
        --linear-yellow: {theme['colors']['semantic']['yellow']};
        
        /* Linear 타이포그래피 */
        --linear-font-primary: {theme['typography']['fontFamily']['primary']};
        --linear-font-monospace: {theme['typography']['fontFamily']['monospace']};
        
        --linear-font-weight-light: {theme['typography']['fontWeights']['light']};
        --linear-font-weight-normal: {theme['typography']['fontWeights']['normal']};
        --linear-font-weight-medium: {theme['typography']['fontWeights']['medium']};
        --linear-font-weight-semibold: {theme['typography']['fontWeights']['semibold']};
        --linear-font-weight-bold: {theme['typography']['fontWeights']['bold']};
        
        --linear-font-size-micro: {theme['typography']['fontSizes']['micro']};
        --linear-font-size-mini: {theme['typography']['fontSizes']['mini']};
        --linear-font-size-small: {theme['typography']['fontSizes']['small']};
        --linear-font-size-regular: {theme['typography']['fontSizes']['regular']};
        --linear-font-size-large: {theme['typography']['fontSizes']['large']};
        --linear-font-size-title1: {theme['typography']['fontSizes']['title1']};
        --linear-font-size-title2: {theme['typography']['fontSizes']['title2']};
        --linear-font-size-title3: {theme['typography']['fontSizes']['title3']};
        
        /* Linear 간격 */
        --linear-radius-small: {theme['spacing']['radius']['small']};
        --linear-radius-medium: {theme['spacing']['radius']['medium']};
        --linear-radius-large: {theme['spacing']['radius']['large']};
        --linear-radius-xlarge: {theme['spacing']['radius']['xlarge']};
        --linear-radius-xxlarge: {theme['spacing']['radius']['xxlarge']};
        --linear-radius-full: {theme['spacing']['radius']['full']};
        
        --linear-padding-small: {theme['spacing']['padding']['small']};
        --linear-padding-medium: {theme['spacing']['padding']['medium']};
        --linear-padding-large: {theme['spacing']['padding']['large']};
        --linear-padding-xlarge: {theme['spacing']['padding']['xlarge']};
        
        /* Linear 그림자 */
        --linear-shadow-low: {theme['shadows']['low']};
        --linear-shadow-medium: {theme['shadows']['medium']};
        --linear-shadow-high: {theme['shadows']['high']};
    }}
    
    /* Streamlit 다크 테마 적용 - 더 강력한 선택자 */
    .stApp, 
    .stApp > div,
    .stApp > div > div,
    .stApp > div > div > div {{
        background: var(--linear-bg-primary) !important;
        color: var(--linear-text-primary) !important;
    }}
    
    /* 메인 컨테이너 */
    .main .block-container,
    .main .block-container > div,
    .main .block-container > div > div {{
        background: var(--linear-bg-primary) !important;
        color: var(--linear-text-primary) !important;
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        max-width: 1200px !important;
    }}
    
    /* 전체 페이지 배경 */
    body, html {{
        background: var(--linear-bg-primary) !important;
        color: var(--linear-text-primary) !important;
    }}
    
    /* Streamlit 루트 요소 */
    #root {{
        background: var(--linear-bg-primary) !important;
    }}
    
    /* 헤더 */
    .stHeader {{
        background: var(--linear-bg-primary) !important;
    }}
    
    /* 사이드바 */
    .css-1d391kg {{
        background: var(--linear-bg-secondary) !important;
    }}
    
    /* 텍스트 색상 */
    .stMarkdown, .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {{
        color: var(--linear-text-primary) !important;
    }}
    
    /* 캡션 */
    .stCaption {{
        color: var(--linear-text-tertiary) !important;
    }}
    
    /* 메트릭 */
    .metric-container {{
        background: var(--linear-bg-secondary) !important;
        border: 1px solid var(--linear-border-primary) !important;
        border-radius: var(--linear-radius-large) !important;
        padding: var(--linear-padding-large) !important;
    }}
    
    /* 정보 박스 */
    .stInfo {{
        background: rgba(94, 106, 210, 0.1) !important;
        border: 1px solid var(--linear-brand) !important;
        border-radius: var(--linear-radius-medium) !important;
        color: var(--linear-text-primary) !important;
    }}
    
    .stSuccess {{
        background: rgba(76, 183, 130, 0.1) !important;
        border: 1px solid var(--linear-green) !important;
        border-radius: var(--linear-radius-medium) !important;
        color: var(--linear-text-primary) !important;
    }}
    
    .stError {{
        background: rgba(235, 87, 87, 0.1) !important;
        border: 1px solid var(--linear-red) !important;
        border-radius: var(--linear-radius-medium) !important;
        color: var(--linear-text-primary) !important;
    }}
    
    .stWarning {{
        background: rgba(242, 201, 76, 0.1) !important;
        border: 1px solid var(--linear-yellow) !important;
        border-radius: var(--linear-radius-medium) !important;
        color: var(--linear-text-primary) !important;
    }}
    
    /* 확장 가능한 섹션 */
    .streamlit-expanderHeader {{
        background: var(--linear-bg-secondary) !important;
        border: 1px solid var(--linear-border-primary) !important;
        border-radius: var(--linear-radius-medium) !important;
        color: var(--linear-text-primary) !important;
    }}
    
    .streamlit-expanderContent {{
        background: var(--linear-bg-tertiary) !important;
        border: 1px solid var(--linear-border-primary) !important;
        border-radius: 0 0 var(--linear-radius-medium) var(--linear-radius-medium) !important;
    }}
    
    /* 테이블 */
    .dataframe {{
        background: var(--linear-bg-secondary) !important;
        border: 1px solid var(--linear-border-primary) !important;
        border-radius: var(--linear-radius-medium) !important;
        color: var(--linear-text-primary) !important;
    }}
    
    .dataframe th {{
        background: var(--linear-bg-tertiary) !important;
        color: var(--linear-text-primary) !important;
        border-bottom: 1px solid var(--linear-border-primary) !important;
    }}
    
    .dataframe td {{
        background: var(--linear-bg-secondary) !important;
        color: var(--linear-text-primary) !important;
        border-bottom: 1px solid var(--linear-border-primary) !important;
    }}
    </style>
    """


def apply_theme() -> None:
    """Linear 테마를 Streamlit에 적용"""
    # CSS 적용
    st.markdown(get_theme_css(), unsafe_allow_html=True)
    
    # JavaScript로 강제 적용
    st.markdown("""
    <script>
    // 페이지 로드 후 강제로 다크 테마 적용
    document.addEventListener('DOMContentLoaded', function() {
        // 배경색 강제 적용
        document.body.style.backgroundColor = '#08090a';
        document.documentElement.style.backgroundColor = '#08090a';
        
        // 모든 Streamlit 컨테이너에 배경색 적용
        const containers = document.querySelectorAll('.main .block-container, .stApp, .main');
        containers.forEach(container => {
            container.style.backgroundColor = '#08090a';
            container.style.color = '#f7f8f8';
        });
        
        // 텍스트 색상 적용
        const textElements = document.querySelectorAll('p, h1, h2, h3, h4, h5, h6, span, div');
        textElements.forEach(element => {
            if (!element.style.color || element.style.color === 'rgb(0, 0, 0)' || element.style.color === 'black') {
                element.style.color = '#f7f8f8';
            }
        });
    });
    
    // 지연 실행 (Streamlit이 완전히 로드된 후)
    setTimeout(function() {
        document.body.style.backgroundColor = '#08090a';
        document.documentElement.style.backgroundColor = '#08090a';
    }, 1000);
    </script>
    """, unsafe_allow_html=True)


def get_color(category: str, name: str) -> str:
    """테마에서 색상 값을 가져옴"""
    return LINEAR_THEME["colors"][category][name]


def get_font_size(size: str) -> str:
    """테마에서 폰트 크기를 가져옴"""
    return LINEAR_THEME["typography"]["fontSizes"][size]


def get_radius(size: str) -> str:
    """테마에서 border-radius를 가져옴"""
    return LINEAR_THEME["spacing"]["radius"][size]


def get_padding(size: str) -> str:
    """테마에서 padding을 가져옴"""
    return LINEAR_THEME["spacing"]["padding"][size]
