"""
UI Styles Module

This module contains all CSS styles organized by functionality:
- base: Basic styles (Streamlit hiding, layout)
- chat: Chat-related styles
- header: Header/navigation styles
- admin: Admin UI styles
- components: Linear component styles
- responsive: Mobile/tablet responsive styles
"""

from .base import inject_base_styles, inject_linear_theme_variables
from .chat import inject_chat_styles
from .responsive import inject_responsive_styles

# TODO: 다음 단계에서 추가할 모듈들
# from .header import inject_header_styles
# from .admin import inject_admin_styles
# from .components import inject_component_styles

__all__ = [
    'inject_base_styles',
    'inject_linear_theme_variables',
    'inject_chat_styles', 
    'inject_responsive_styles'
]
