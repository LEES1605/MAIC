# 상세한 앱 테스트
import requests
import webbrowser

def test_app():
    url = "http://localhost:8501"
    
    print("상세 앱 테스트 시작...")
    print(f"URL: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print("SUCCESS: 앱이 정상적으로 응답합니다!")
            print(f"상태 코드: {response.status_code}")
            
            # HTML 내용 상세 분석
            html_content = response.text
            
            # Neumorphism 관련 키워드 검사
            keywords = [
                "LEES AI Teacher",
                "neumorphic-card",
                "neumorphic-button", 
                "Poppins",
                "#2c2f48",
                "box-shadow"
            ]
            
            found_keywords = []
            for keyword in keywords:
                if keyword in html_content:
                    found_keywords.append(keyword)
                    print(f"FOUND: {keyword}")
                else:
                    print(f"NOT FOUND: {keyword}")
            
            if len(found_keywords) >= 3:
                print("SUCCESS: Neumorphism 디자인이 적용되었습니다!")
            else:
                print("WARNING: Neumorphism 디자인이 부분적으로만 적용되었습니다.")
            
            # HTML 일부 출력
            print("\nHTML 내용 일부:")
            print("-" * 50)
            print(html_content[:1000] + "..." if len(html_content) > 1000 else html_content)
            print("-" * 50)
            
            # 브라우저 열기
            print("\n브라우저를 열고 있습니다...")
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
    print("=" * 60)
    print("MAIC 앱 상세 테스트")
    print("=" * 60)
    
    if test_app():
        print("\nSUCCESS: 앱 테스트 성공!")
        print("브라우저에서 앱을 확인하세요.")
    else:
        print("\nERROR: 앱 테스트 실패!")
    
    print("=" * 60)




