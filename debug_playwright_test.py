#!/usr/bin/env python3
"""
디버그용 Playwright 테스트 - 페이지 구조 분석
"""

import asyncio
from playwright.async_api import async_playwright

async def debug_page_structure():
    """페이지 구조 디버깅"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            print("앱 접속 중...")
            await page.goto("http://localhost:8504")
            await page.wait_for_load_state("networkidle")
            print("앱 로딩 완료")
            
            # 페이지 제목 확인
            title = await page.title()
            print(f"페이지 제목: {title}")
            
            # 모든 버튼 찾기
            all_buttons = page.locator('button')
            button_count = await all_buttons.count()
            print(f"전체 버튼 개수: {button_count}")
            
            # 버튼 텍스트 출력
            for i in range(min(button_count, 10)):  # 최대 10개만
                try:
                    button_text = await all_buttons.nth(i).text_content()
                    print(f"버튼 {i}: '{button_text}'")
                except:
                    print(f"버튼 {i}: 텍스트 읽기 실패")
            
            # 모든 체크박스 찾기
            all_checkboxes = page.locator('input[type="checkbox"]')
            checkbox_count = await all_checkboxes.count()
            print(f"전체 체크박스 개수: {checkbox_count}")
            
            # 모든 input 요소 찾기
            all_inputs = page.locator('input')
            input_count = await all_inputs.count()
            print(f"전체 input 개수: {input_count}")
            
            # input 타입별 분류
            for i in range(min(input_count, 10)):
                try:
                    input_type = await all_inputs.nth(i).get_attribute('type')
                    print(f"Input {i}: type='{input_type}'")
                except:
                    print(f"Input {i}: 속성 읽기 실패")
            
            # 페이지 HTML 일부 출력
            html_content = await page.content()
            print(f"페이지 HTML 길이: {len(html_content)}")
            
            # 스크린샷 저장
            await page.screenshot(path="debug_page.png")
            print("디버그 스크린샷 저장: debug_page.png")
            
            return True
            
        except Exception as e:
            print(f"오류: {e}")
            await page.screenshot(path="debug_error.png")
            return False
            
        finally:
            await page.wait_for_timeout(3000)
            await browser.close()

if __name__ == "__main__":
    result = asyncio.run(debug_page_structure())
    if result:
        print("디버그 완료")
    else:
        print("디버그 실패")

