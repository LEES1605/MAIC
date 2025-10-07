# 앱 테스트 스크립트
import requests
import time
import webbrowser
from pathlib import Path

def test_app():
    """앱 테스트"""
    url = "http://localhost:8501"
    
    print("앱 테스트 시작...")
    print(f"URL: {url}")
    
    # 1. 앱 응답 확인
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print("✅ 앱이 정상적으로 응답합니다!")
            print(f"상태 코드: {response.status_code}")
            
            # 2. HTML 내용 확인
            html_content = response.text
            if "LEES AI Teacher" in html_content:
                print("✅ Neumorphism 디자인이 적용되었습니다!")
            else:
                print("⚠️ Neumorphism 디자인이 적용되지 않았을 수 있습니다.")
            
            # 3. 브라우저 열기
            print("🌐 브라우저를 열고 있습니다...")
            webbrowser.open(url)
            
            return True
        else:
            print(f"❌ 앱 응답 오류: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ 앱에 연결할 수 없습니다. 앱이 실행 중인지 확인하세요.")
        return False
    except requests.exceptions.Timeout:
        print("❌ 앱 응답 시간 초과")
        return False
    except Exception as e:
        print(f"❌ 테스트 중 오류: {e}")
        return False

def check_app_status():
    """앱 상태 확인"""
    import subprocess
    
    try:
        result = subprocess.run(
            'netstat -ano | findstr :8501',
            shell=True, capture_output=True, text=True
        )
        
        if 'LISTENING' in result.stdout:
            print("✅ 앱이 포트 8501에서 실행 중입니다.")
            return True
        else:
            print("❌ 앱이 실행되지 않았습니다.")
            return False
    except Exception as e:
        print(f"상태 확인 오류: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("MAIC 앱 테스트")
    print("=" * 50)
    
    # 앱 상태 확인
    if check_app_status():
        # 앱 테스트
        if test_app():
            print("\n🎉 앱 테스트 성공!")
            print("브라우저에서 앱을 확인하세요.")
        else:
            print("\n❌ 앱 테스트 실패!")
    else:
        print("\n❌ 앱이 실행되지 않았습니다.")
        print("다음 명령어로 앱을 시작하세요:")
        print("python simple_start.py")
    
    print("=" * 50)


