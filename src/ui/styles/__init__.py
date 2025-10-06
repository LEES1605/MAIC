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

from .base import inject_base_styles
from .chat import inject_chat_styles
from .header import inject_header_styles
from .admin import inject_admin_styles
from .components import inject_component_styles
from .responsive import inject_responsive_styles

__all__ = [
    'inject_base_styles',
    'inject_chat_styles', 
    'inject_header_styles',
    'inject_admin_styles',
    'inject_component_styles',
    'inject_responsive_styles'
]
