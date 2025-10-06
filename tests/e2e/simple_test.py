#!/usr/bin/env python3
"""간단한 앱 상태 테스트"""

import requests
import time

def test_app_status():
    """앱 상태 테스트"""
    print("=== 앱 상태 테스트 ===")
    
    try:
        # 앱 접속 테스트
        print("1. 앱 접속 테스트...")
        response = requests.get("http://localhost:8501", timeout=10)
        
        if response.status_code == 200:
            print("   [OK] 앱이 정상적으로 실행 중")
            print(f"   [INFO] 응답 코드: {response.status_code}")
            
            # HTML 내용 확인
            html_content = response.text
            if "LEES AI Teacher" in html_content:
                print("   [OK] 앱 제목이 정상적으로 로드됨")
            else:
                print("   [WARN] 앱 제목을 찾을 수 없음")
                
            if "관리자" in html_content:
                print("   [OK] 관리자 버튼이 HTML에 포함됨")
            else:
                print("   [WARN] 관리자 버튼을 찾을 수 없음")
                
        else:
            print(f"   [ERROR] 앱 접속 실패 - 응답 코드: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("   [ERROR] 앱에 연결할 수 없음 - 앱이 실행되지 않았을 수 있음")
    except requests.exceptions.Timeout:
        print("   [ERROR] 앱 응답 시간 초과")
    except Exception as e:
        print(f"   [ERROR] 테스트 중 오류 발생: {e}")
    
    print("=== 앱 상태 테스트 완료 ===")

if __name__ == "__main__":
    test_app_status()