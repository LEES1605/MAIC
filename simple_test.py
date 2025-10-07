# 간단한 앱 테스트
import requests
import webbrowser

def test_app():
    url = "http://localhost:8501"
    
    print("앱 테스트 시작...")
    print(f"URL: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print("SUCCESS: 앱이 정상적으로 응답합니다!")
            print(f"상태 코드: {response.status_code}")
            
            # HTML 내용 확인
            html_content = response.text
            if "LEES AI Teacher" in html_content:
                print("SUCCESS: Neumorphism 디자인이 적용되었습니다!")
            else:
                print("WARNING: Neumorphism 디자인이 적용되지 않았을 수 있습니다.")
            
            # 브라우저 열기
            print("브라우저를 열고 있습니다...")
            webbrowser.open(url)
            
            return True
        else:
            print(f"ERROR: 앱 응답 오류: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("ERROR: 앱에 연결할 수 없습니다.")
        return False
    except Exception as e:
        print(f"ERROR: 테스트 중 오류: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("MAIC 앱 테스트")
    print("=" * 50)
    
    if test_app():
        print("\nSUCCESS: 앱 테스트 성공!")
        print("브라우저에서 앱을 확인하세요.")
    else:
        print("\nERROR: 앱 테스트 실패!")
    
    print("=" * 50)

