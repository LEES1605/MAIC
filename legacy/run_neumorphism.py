# Neumorphism 앱 직접 실행
import streamlit as st
from src.ui.components.neumorphism_app import render_neumorphism_maic_app

def main():
    st.set_page_config(
        page_title="MAIC - Neumorphism",
        page_icon="🎓",
        layout="wide"
    )
    
    render_neumorphism_maic_app()

if __name__ == "__main__":
    main()


