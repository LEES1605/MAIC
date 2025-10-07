#!/usr/bin/env python3
"""
Playwright 디버깅 테스트 스크립트
창 크기 변경 시 응답창 높이 조정이 작동하는지 확인
"""

import time
import sys
from playwright.sync_api import sync_playwright

def test_responsive_height():
    """응답창 높이 조정 테스트"""
    print("Playwright 테스트 시작...")
    
    try:
        with sync_playwright() as p:
            # 브라우저 실행 (헤드리스 모드 비활성화로 디버깅)
            browser = p.chromium.launch(headless=False, slow_mo=1000)
            page = browser.new_page()
            
            print("페이지 로딩 중...")
            page.goto("http://localhost:8080/neumorphism_app.html")
            
            # 페이지 로딩 대기
            page.wait_for_load_state("networkidle")
            time.sleep(2)
            
            print("초기 응답창 높이 확인...")
            # 응답창 요소 찾기
            response_area = page.locator("#response-area")
            if response_area.count() > 0:
                initial_height = response_area.evaluate("el => el.style.maxHeight")
                print(f"   초기 높이: {initial_height}")
                
                # 창 크기 변경 테스트
                print("창 크기 변경 테스트...")
                
                # 작은 크기로 변경
                page.set_viewport_size({"width": 800, "height": 600})
                time.sleep(2)
                small_height = response_area.evaluate("el => el.style.maxHeight")
                print(f"   작은 창 높이: {small_height}")
                
                # 큰 크기로 변경
                page.set_viewport_size({"width": 1400, "height": 1000})
                time.sleep(2)
                large_height = response_area.evaluate("el => el.style.maxHeight")
                print(f"   큰 창 높이: {large_height}")
                
                # JavaScript 함수 직접 호출 테스트
                print("JavaScript 함수 직접 호출...")
                result = page.evaluate("""
                    () => {
                        const responseArea = document.getElementById('response-area');
                        if (responseArea) {
                            const viewportHeight = window.innerHeight;
                            const headerHeight = 200;
                            const inputHeight = 100;
                            const margin = 80;
                            
                            const maxHeight = viewportHeight - headerHeight - inputHeight - margin;
                            responseArea.style.maxHeight = Math.max(400, maxHeight) + 'px';
                            return {
                                viewportHeight: viewportHeight,
                                calculatedHeight: Math.max(400, maxHeight),
                                actualHeight: responseArea.style.maxHeight
                            };
                        }
                        return null;
                    }
                """)
                print(f"   JavaScript 결과: {result}")
                
                # 스크린샷 저장
                page.screenshot(path="test_responsive.png")
                print("스크린샷 저장: test_responsive.png")
                
            else:
                print("응답창 요소를 찾을 수 없습니다!")
                
            print("5초 대기 후 브라우저 종료...")
            time.sleep(5)
            browser.close()
            
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("테스트 완료!")
    return True

if __name__ == "__main__":
    success = test_responsive_height()
    sys.exit(0 if success else 1)
