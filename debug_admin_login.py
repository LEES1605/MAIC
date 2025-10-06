#!/usr/bin/env python3
"""관리자 로그인 디버깅 스크립트"""

import streamlit as st
import os

def debug_admin_login():
    """관리자 로그인 상태 디버깅"""
    print("=== 관리자 로그인 디버깅 ===")
    
    # 1. 세션 상태 확인
    print("\n1. 세션 상태 확인:")
    print(f"admin_mode: {st.session_state.get('admin_mode', 'NOT_SET')}")
    print(f"_show_admin_login: {st.session_state.get('_show_admin_login', 'NOT_SET')}")
    
    # 2. 비밀번호 설정 확인
    print("\n2. 비밀번호 설정 확인:")
    try:
        # secrets에서 비밀번호 확인
        pwd_set = (
            st.secrets.get("ADMIN_PASSWORD") or
            st.secrets.get("APP_ADMIN_PASSWORD") or
            st.secrets.get("MAIC_ADMIN_PASSWORD")
        )
        print(f"APP_ADMIN_PASSWORD: {st.secrets.get('APP_ADMIN_PASSWORD', 'NOT_SET')}")
        print(f"ADMIN_PASSWORD: {st.secrets.get('ADMIN_PASSWORD', 'NOT_SET')}")
        print(f"MAIC_ADMIN_PASSWORD: {st.secrets.get('MAIC_ADMIN_PASSWORD', 'NOT_SET')}")
        print(f"최종 비밀번호: {pwd_set if pwd_set else 'NOT_SET'}")
    except Exception as e:
        print(f"secrets 접근 오류: {e}")
    
    # 3. 환경 변수 확인
    print("\n3. 환경 변수 확인:")
    print(f"ADMIN_PASSWORD (env): {os.getenv('ADMIN_PASSWORD', 'NOT_SET')}")
    print(f"APP_ADMIN_PASSWORD (env): {os.getenv('APP_ADMIN_PASSWORD', 'NOT_SET')}")
    
    # 4. 로그인 폼 표시 테스트
    print("\n4. 로그인 폼 표시 테스트:")
    need_login = (not st.session_state.get("admin_mode")) and st.session_state.get("_show_admin_login")
    print(f"need_login: {need_login}")
    print(f"admin_mode: {st.session_state.get('admin_mode')}")
    print(f"_show_admin_login: {st.session_state.get('_show_admin_login')}")

def main():
    st.title("관리자 로그인 디버깅")
    
    # 디버깅 정보 표시
    debug_admin_login()
    
    # 관리자 로그인 버튼
    if st.button("🔐 관리자 로그인 폼 표시"):
        st.session_state["_show_admin_login"] = True
        st.rerun()
    
    # 로그인 폼
    if st.session_state.get("_show_admin_login"):
        st.write("🔐 관리자 로그인")
        
        with st.form("admin_login_form"):
            pw = st.text_input("비밀번호", type="password", key="admin_pw_input")
            col_a, col_b = st.columns([1, 1])
            submit = col_a.form_submit_button("로그인")
            cancel = col_b.form_submit_button("닫기")
        
        if cancel:
            st.session_state["_show_admin_login"] = False
            st.rerun()
        
        if submit:
            try:
                pwd_set = (
                    st.secrets.get("ADMIN_PASSWORD") or
                    st.secrets.get("APP_ADMIN_PASSWORD") or
                    st.secrets.get("MAIC_ADMIN_PASSWORD")
                )
                
                if not pwd_set:
                    st.error("서버에 관리자 비밀번호가 설정되어 있지 않습니다.")
                elif pw and str(pw) == str(pwd_set):
                    st.session_state["admin_mode"] = True
                    st.session_state["_show_admin_login"] = False
                    st.success("로그인 성공")
                    st.rerun()
                else:
                    st.error("비밀번호가 올바르지 않습니다.")
            except Exception as e:
                st.error(f"로그인 오류: {e}")
    
    # 로그아웃 버튼
    if st.session_state.get("admin_mode"):
        if st.button("🚪 로그아웃"):
            st.session_state["admin_mode"] = False
            st.session_state["_show_admin_login"] = False
            st.success("로그아웃 완료")
            st.rerun()

if __name__ == "__main__":
    main()
