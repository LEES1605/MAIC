# 테마 관리 시스템
from __future__ import annotations
import streamlit as st
from typing import Dict, Any, Optional

class ThemeManager:
    """테마 관리를 위한 유틸리티 클래스"""
    
    def __init__(self):
        self.current_theme = "linear"
        self.themes = {
            "linear": {
                "primary_color": "#667eea",
                "secondary_color": "#764ba2",
                "background_color": "#1a1a2e",
                "text_color": "#ffffff"
            }
        }
    
    def get_theme(self, theme_name: str = None) -> Dict[str, Any]:
        """테마 정보를 반환합니다."""
        if theme_name is None:
            theme_name = self.current_theme
        
        return self.themes.get(theme_name, self.themes["linear"])
    
    def set_theme(self, theme_name: str) -> None:
        """현재 테마를 설정합니다."""
        if theme_name in self.themes:
            self.current_theme = theme_name
        else:
            st.warning(f"알 수 없는 테마: {theme_name}")
    
    def get_color(self, color_name: str, theme_name: str = None) -> str:
        """테마에서 색상을 가져옵니다."""
        theme = self.get_theme(theme_name)
        return theme.get(color_name, "#ffffff")

