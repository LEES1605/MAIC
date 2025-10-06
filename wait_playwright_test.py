#!/usr/bin/env python3
"""
대기 시간을 늘린 Playwright 테스트
"""

import asyncio
from playwright.async_api import async_playwright

async def wait_and_test():
    """대기 시간을 늘려서 테스트"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            print("앱 접속 중...")
            await page.goto("http://localhost:8504")
            
            # 더 긴 대기 시간
            print("페이지 로딩 대기 중... (10초)")
            await page.wait_for_timeout(10000)
            
            # 네트워크 대기
            await page.wait_for_load_state("networkidle")
            print("네트워크 대기 완료")
            
            # 추가 대기
            print("추가 대기 중... (5초)")
            await page.wait_for_timeout(5000)
            
            # 페이지 제목 확인
            title = await page.title()
            print(f"페이지 제목: {title}")
            
            # 모든 버튼 찾기
            all_buttons = page.locator('button')
            button_count = await all_buttons.count()
            print(f"전체 버튼 개수: {button_count}")
            
            # 버튼 텍스트 출력 (더 많이)
            for i in range(min(button_count, 20)):
                try:
                    button_text = await all_buttons.nth(i).text_content()
                    print(f"버튼 {i}: '{button_text}'")
                except:
                    print(f"버튼 {i}: 텍스트 읽기 실패")
            
            # Streamlit 특정 요소 찾기
            st_buttons = page.locator('[data-testid="stButton"]')
            st_button_count = await st_buttons.count()
            print(f"Streamlit 버튼 개수: {st_button_count}")
            
            # 체크박스 찾기 (다양한 선택자)
            checkboxes1 = page.locator('input[type="checkbox"]')
            checkboxes2 = page.locator('[data-testid="stCheckbox"]')
            checkbox_count1 = await checkboxes1.count()
            checkbox_count2 = await checkboxes2.count()
            print(f"체크박스 (input): {checkbox_count1}")
            print(f"체크박스 (stCheckbox): {checkbox_count2}")
            
            # 스크린샷 저장
            await page.screenshot(path="wait_test.png")
            print("스크린샷 저장: wait_test.png")
            
            return True
            
        except Exception as e:
            print(f"오류: {e}")
            await page.screenshot(path="wait_error.png")
            return False
            
        finally:
            await page.wait_for_timeout(3000)
            await browser.close()

if __name__ == "__main__":
    result = asyncio.run(wait_and_test())
    if result:
        print("대기 테스트 완료")
    else:
        print("대기 테스트 실패")

