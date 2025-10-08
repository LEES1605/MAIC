#!/usr/bin/env python3
"""
질문모드 토글 저장 기능 디버그 테스트
"""

import asyncio
from playwright.async_api import async_playwright
import json

async def test_debug_toggle():
    async with async_playwright() as p:
        # 브라우저 시작
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            print("디버그 테스트 시작")
            
            # 1. 앱 로드
            print("앱 로드 중...")
            await page.goto("http://localhost:8080/neumorphism_app.html")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(3000)
            
            # 2. 페이지 상태 확인
            print("페이지 상태 확인...")
            title = await page.title()
            print(f"페이지 제목: {title}")
            
            # 3. 관리자 로그인 버튼 찾기
            print("관리자 로그인 버튼 찾기...")
            admin_buttons = page.locator("button")
            button_count = await admin_buttons.count()
            print(f"총 버튼 개수: {button_count}")
            
            for i in range(button_count):
                button = admin_buttons.nth(i)
                button_text = await button.text_content()
                button_id = await button.get_attribute("id")
                print(f"버튼 {i}: '{button_text}' (id: {button_id})")
            
            # 4. 특정 ID로 관리자 로그인 버튼 찾기
            print("ID로 관리자 로그인 버튼 찾기...")
            admin_login_by_id = page.locator("#admin-login-btn")
            if await admin_login_by_id.count() > 0:
                print("ID로 관리자 로그인 버튼을 찾았습니다!")
                await admin_login_by_id.click()
                await page.wait_for_timeout(2000)
            else:
                print("ID로 관리자 로그인 버튼을 찾을 수 없습니다.")
            
            # 5. 텍스트로 관리자 로그인 버튼 찾기
            print("텍스트로 관리자 로그인 버튼 찾기...")
            admin_login_by_text = page.locator("button:has-text('관리자')")
            if await admin_login_by_text.count() > 0:
                print("텍스트로 관리자 로그인 버튼을 찾았습니다!")
                await admin_login_by_text.click()
                await page.wait_for_timeout(2000)
            else:
                print("텍스트로 관리자 로그인 버튼을 찾을 수 없습니다.")
            
            # 6. 현재 localStorage 상태 확인
            print("현재 localStorage 상태 확인...")
            settings = await page.evaluate("localStorage.getItem('questionModeSettings')")
            print(f"localStorage questionModeSettings: {settings}")
            
            # 7. 질문모드 관련 요소 찾기
            print("질문모드 관련 요소 찾기...")
            question_mode_buttons = page.locator("button:has-text('질문모드')")
            if await question_mode_buttons.count() > 0:
                print("질문모드 버튼을 찾았습니다!")
            else:
                print("질문모드 버튼을 찾을 수 없습니다.")
            
            print("디버그 테스트 완료!")
            
        except Exception as e:
            print(f"테스트 중 오류 발생: {e}")
            await page.screenshot(path="debug_error_screenshot.png")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_debug_toggle())



