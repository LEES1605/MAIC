#!/usr/bin/env python3
"""
토글 즉시 반응 테스트
"""

import asyncio
from playwright.async_api import async_playwright
import json

async def test_instant_toggle():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            print("Instant toggle test start")
            
            # 앱 로드
            await page.goto("http://localhost:8080/neumorphism_app.html")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(3000)
            
            # 관리자 로그인
            print("1. 관리자 로그인...")
            admin_btn = page.locator("#admin-login-btn")
            await admin_btn.click()
            await page.wait_for_timeout(2000)
            
            password_input = page.locator("#adminPassword")
            await password_input.fill("admin123")
            await page.wait_for_timeout(1000)
            
            login_btn = page.locator("#modal-login-btn")
            await login_btn.click()
            await page.wait_for_timeout(3000)
            
            # 질문모드로 이동
            print("2. 질문모드로 이동...")
            question_btn = page.locator("button:has-text('질문모드')")
            await question_btn.click()
            await page.wait_for_timeout(2000)
            
            # 학생화면으로 전환하여 초기 상태 확인
            print("3. 학생화면으로 전환하여 초기 상태 확인...")
            await page.evaluate("showUserMode()")
            await page.wait_for_timeout(2000)
            
            mode_buttons = page.locator(".mode-btn:not(.admin-mode-btn)")
            button_count = await mode_buttons.count()
            
            print("   초기 학생화면 모드 버튼 상태:")
            for i in range(button_count):
                button = mode_buttons.nth(i)
                button_text = await button.text_content()
                button_class = await button.get_attribute("class")
                is_disabled = "disabled" in button_class if button_class else False
                
                print(f"     {button_text}: {'비활성화' if is_disabled else '활성화'}")
            
            # 다시 관리자 모드로 돌아가기
            print("4. 관리자 모드로 돌아가기...")
            admin_btn = page.locator("#admin-login-btn")
            await admin_btn.click()
            await page.wait_for_timeout(2000)
            
            password_input = page.locator("#adminPassword")
            await password_input.fill("admin123")
            await page.wait_for_timeout(1000)
            
            login_btn = page.locator("#modal-login-btn")
            await login_btn.click()
            await page.wait_for_timeout(3000)
            
            # 질문모드로 이동
            question_btn = page.locator("button:has-text('질문모드')")
            await question_btn.click()
            await page.wait_for_timeout(2000)
            
            # 문법학습 토글 비활성화
            print("5. 문법학습 토글 비활성화 (즉시 반응 테스트)...")
            await page.evaluate("""
                document.getElementById('grammar-mode-toggle').checked = false;
                document.getElementById('grammar-mode-status').textContent = '비활성화';
                // change 이벤트 트리거
                document.getElementById('grammar-mode-toggle').dispatchEvent(new Event('change'));
            """)
            await page.wait_for_timeout(1000)
            
            # localStorage 확인
            settings = await page.evaluate("localStorage.getItem('questionModeSettings')")
            print(f"   localStorage: {settings}")
            
            # 학생화면으로 전환하여 즉시 반영 확인
            print("6. 학생화면으로 전환하여 즉시 반영 확인...")
            await page.evaluate("showUserMode()")
            await page.wait_for_timeout(2000)
            
            print("   토글 변경 후 학생화면 모드 버튼 상태:")
            for i in range(button_count):
                button = mode_buttons.nth(i)
                button_text = await button.text_content()
                button_class = await button.get_attribute("class")
                is_disabled = "disabled" in button_class if button_class else False
                
                print(f"     {button_text}: {'비활성화' if is_disabled else '활성화'}")
            
            # 다시 관리자 모드로 돌아가서 문장분석도 비활성화
            print("7. 관리자 모드로 돌아가서 문장분석도 비활성화...")
            admin_btn = page.locator("#admin-login-btn")
            await admin_btn.click()
            await page.wait_for_timeout(2000)
            
            password_input = page.locator("#adminPassword")
            await password_input.fill("admin123")
            await page.wait_for_timeout(1000)
            
            login_btn = page.locator("#modal-login-btn")
            await login_btn.click()
            await page.wait_for_timeout(3000)
            
            question_btn = page.locator("button:has-text('질문모드')")
            await question_btn.click()
            await page.wait_for_timeout(2000)
            
            # 문장분석 토글 비활성화
            await page.evaluate("""
                document.getElementById('sentence-mode-toggle').checked = false;
                document.getElementById('sentence-mode-status').textContent = '비활성화';
                document.getElementById('sentence-mode-toggle').dispatchEvent(new Event('change'));
            """)
            await page.wait_for_timeout(1000)
            
            # localStorage 확인
            settings = await page.evaluate("localStorage.getItem('questionModeSettings')")
            print(f"   localStorage: {settings}")
            
            # 학생화면으로 전환하여 두 번째 변경 확인
            print("8. 학생화면으로 전환하여 두 번째 변경 확인...")
            await page.evaluate("showUserMode()")
            await page.wait_for_timeout(2000)
            
            print("   두 번째 토글 변경 후 학생화면 모드 버튼 상태:")
            for i in range(button_count):
                button = mode_buttons.nth(i)
                button_text = await button.text_content()
                button_class = await button.get_attribute("class")
                is_disabled = "disabled" in button_class if button_class else False
                
                print(f"     {button_text}: {'비활성화' if is_disabled else '활성화'}")
            
            print("Test completed!")
            
        except Exception as e:
            print(f"Error: {e}")
            await page.screenshot(path="instant_toggle_error.png")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_instant_toggle())



