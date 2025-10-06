#!/usr/bin/env python3
"""간단한 관리자 로그인 테스트"""

import streamlit as st
import os

def main():
    st.title("관리자 로그인 테스트")
    
    # 세션 상태 초기화
    if "admin_mode" not in st.session_state:
        st.session_state.admin_mode = False
    if "_show_admin_login" not in st.session_state:
        st.session_state._show_admin_login = False
    
    # 현재 상태 표시
    st.write(f"현재 admin_mode: {st.session_state.admin_mode}")
    st.write(f"현재 _show_admin_login: {st.session_state._show_admin_login}")
    
    # 관리자 버튼
    if not st.session_state.admin_mode:
        if st.button("🔐 관리자 로그인"):
            st.session_state._show_admin_login = True
            st.rerun()
    
    # 로그인 폼
    if st.session_state._show_admin_login and not st.session_state.admin_mode:
        st.write("---")
        st.write("🔐 관리자 로그인")
        
        with st.form("login_form"):
            password = st.text_input("비밀번호", type="password")
            col1, col2 = st.columns(2)
            
            with col1:
                login_btn = st.form_submit_button("로그인")
            with col2:
                cancel_btn = st.form_submit_button("취소")
        
        if login_btn:
            if password == "0000":  # 하드코딩된 비밀번호
                st.session_state.admin_mode = True
                st.session_state._show_admin_login = False
                st.success("로그인 성공!")
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
        
        if cancel_btn:
            st.session_state._show_admin_login = False
            st.rerun()
    
    # 관리자 모드
    if st.session_state.admin_mode:
        st.success("관리자 모드입니다!")
        if st.button("🚪 로그아웃"):
            st.session_state.admin_mode = False
            st.session_state._show_admin_login = False
            st.rerun()

if __name__ == "__main__":
    main()
