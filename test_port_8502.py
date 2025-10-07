# 포트 8502 테스트
import requests

def test_port_8502():
    url = "http://localhost:8502"
    
    print("포트 8502 테스트...")
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print("SUCCESS: 포트 8502에서 앱이 실행 중입니다!")
            
            html_content = response.text
            
            # Neumorphism 키워드 검사
            if "LEES AI Teacher" in html_content:
                print("SUCCESS: Neumorphism 디자인이 적용되었습니다!")
                return True
            else:
                print("WARNING: Neumorphism 디자인이 적용되지 않았습니다.")
                return False
        else:
            print(f"ERROR: 상태 코드 {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("ERROR: 포트 8502에 연결할 수 없습니다.")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    test_port_8502()
