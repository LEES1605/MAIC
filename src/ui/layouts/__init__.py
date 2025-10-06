"""
UI Layouts Module

This module contains layout components organized by functionality:
- main: Main application layout
- admin: Admin panel layout
- chat: Chat interface layout
"""

from .main import render_main_layout
from .admin import render_admin_layout
from .chat import render_chat_layout

__all__ = [
    'render_main_layout',
    'render_admin_layout',
    'render_chat_layout'
]
