"""
Responsive UI Styles Module

Contains responsive styles for mobile and tablet devices:
- Mobile media queries
- Tablet media queries
- Responsive layout adjustments
"""

import streamlit as st


def inject_responsive_styles():
    """Inject responsive styles for mobile and tablet devices."""
    if st.session_state.get("_responsive_styles_injected"):
        return
    
    st.session_state["_responsive_styles_injected"] = True
    
    st.markdown(
        """
        <style>
        /* 모바일 반응형 스타일 */
        @media (max-width:480px){
          .bubble{ max-width:96%; }
          .chip-src{ max-width:160px; }
          
          /* 버튼 모바일 최적화 */
          .stButton > button {
            font-size: 12px !important;
            padding: 8px 12px !important;
          }
          
          /* 헤더 모바일 최적화 */
          .brand-title {
            font-size: 180% !important;
          }
          .ready-chip {
            font-size: 14px !important;
            padding: 1px 8px !important;
          }
          
          /* 메인 컨테이너 모바일 최적화 */
          .main .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
          }
        }
        
        /* 태블릿 반응형 스타일 */
        @media (min-width: 481px) and (max-width: 768px) {
          .bubble{ max-width: 90%; }
          .chip-src{ max-width: 200px; }
          
          /* 버튼 태블릿 최적화 */
          .stButton > button {
            font-size: 14px !important;
            padding: 10px 16px !important;
          }
          
          /* 헤더 태블릿 최적화 */
          .brand-title {
            font-size: 200% !important;
          }
        }
        
        /* 데스크톱 반응형 스타일 */
        @media (min-width: 769px) {
          .bubble{ max-width: 88%; }
          .chip-src{ max-width: 220px; }
          
          /* 버튼 데스크톱 최적화 */
          .stButton > button {
            font-size: 16px !important;
            padding: 12px 20px !important;
          }
          
          /* 헤더 데스크톱 최적화 */
          .brand-title {
            font-size: 220% !important;
          }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
