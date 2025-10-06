#!/usr/bin/env python3
"""토큰 인증 문제 디버깅"""

import os

def debug_token_issue():
    """토큰 인증 문제 분석"""
    print("=== 환경변수 확인 ===")
    github_token_env = os.getenv("GITHUB_TOKEN")
    github_repo_env = os.getenv("GITHUB_REPO")
    
    print(f"GITHUB_TOKEN (env): {'SET' if github_token_env else 'NOT_SET'}")
    print(f"GITHUB_REPO (env): {github_repo_env or 'NOT_SET'}")
    
    print("\n=== Streamlit Secrets 확인 ===")
    try:
        import streamlit as st
        github_token_secrets = st.secrets.get("GITHUB_TOKEN")
        github_repo_secrets = st.secrets.get("GITHUB_REPO")
        
        print(f"GITHUB_TOKEN (secrets): {'SET' if github_token_secrets else 'NOT_SET'}")
        print(f"GITHUB_REPO (secrets): {github_repo_secrets or 'NOT_SET'}")
        
        # 토큰 길이 확인
        if github_token_secrets:
            print(f"토큰 길이: {len(github_token_secrets)}")
            print(f"토큰 시작: {github_token_secrets[:10]}...")
            
    except Exception as e:
        print(f"Streamlit secrets 접근 실패: {e}")
    
    print("\n=== 토큰 유효성 테스트 ===")
    # 실제 사용되는 토큰 확인
    from src.runtime.sequential_release import create_sequential_manager
    
    # 환경변수 우선
    token = github_token_env
    if not token:
        try:
            import streamlit as st
            token = st.secrets.get("GITHUB_TOKEN")
        except:
            pass
    
    if token:
        print(f"사용할 토큰: {'SET' if token else 'NOT_SET'}")
        print(f"토큰 길이: {len(token)}")
        print(f"토큰 시작: {token[:10]}...")
        
        # GitHub API 테스트
        try:
            import requests
            headers = {"Authorization": f"token {token}"}
            response = requests.get("https://api.github.com/user", headers=headers)
            print(f"GitHub API 응답: {response.status_code}")
            if response.status_code == 200:
                user_data = response.json()
                print(f"인증된 사용자: {user_data.get('login')}")
            else:
                print(f"인증 실패: {response.text}")
        except Exception as e:
            print(f"API 테스트 실패: {e}")
    else:
        print("토큰을 찾을 수 없습니다.")

if __name__ == "__main__":
    debug_token_issue()


