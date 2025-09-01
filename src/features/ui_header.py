# ============================== features/ui_header.py — START ====================
from __future__ import annotations

from typing import Optional

import streamlit as st


def render_header(
    *,
    title: str = "LEES AI Teacher",
    ready: bool = True,
    on_admin_click=None,
    gap_px: int = 10,
) -> None:
    """
    상단 헤더(모바일 줄바꿈 방지):
    [✅ 준비완료]  [LEES AI Teacher]  [⚙️]
    - 타이틀 색: 진한 남색(#0B3D91), 크기 크게
    - 버튼/타이틀 사이 간격: gap_px
    """
    st.markdown(
        """
        <style>
        .maic-header{
          display:flex; align-items:center; gap:12px; flex-wrap:nowrap;
        }
        .maic-badge{
          font-size:0.9rem; padding:4px 8px; border-radius:8px;
          background:#E6F7E6; color:#155724; border:1px solid #B7E1B7;
          white-space:nowrap;
        }
        .maic-title{
          font-weight:800;
          color:#0B3D91; /* 진한 남색 */
          font-size:2.4rem; /* 기본보다 크게 */
          line-height:1.1;
          letter-spacing:0.3px;
          text-shadow: 0 1px 0 #fff, 0 2px 0 #ddd; /* 살짝 입체감 */
        }
        .maic-gear{
          font-size:1.4rem; cursor:pointer; user-select:none;
          padding:6px 10px; border-radius:10px; border:1px solid #e5e7eb;
          background:#fafafa;
        }
        .maic-gear:hover{ background:#f2f2f2; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    col = st.columns([0.15, 0.65, 0.2])

    with col[0]:
        label = "✅ 준비완료" if ready else "⏳ 준비중"
        st.markdown(f'<div class="maic-badge">{label}</div>', unsafe_allow_html=True)

    with col[1]:
        st.markdown('<div class="maic-title">LEES AI Teacher</div>', unsafe_allow_html=True)
        st.write("")  # 간격 추가
        st.write("")

    with col[2]:
        if st.button("⚙️", key="btn_admin_gear", help="관리자", use_container_width=False):
            if callable(on_admin_click):
                on_admin_click()
# =============================== features/ui_header.py — END =====================
