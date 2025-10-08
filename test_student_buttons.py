#!/usr/bin/env python3
"""
학생화면 모드 버튼 비활성화 테스트
"""

import asyncio
from playwright.async_api import async_playwright
import json

async def test_student_buttons():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            print("Student buttons test start")
            
            # 앱 로드
            await page.goto("http://localhost:8080/neumorphism_app.html")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(3000)
            
            # 관리자 로그인
            print("Logging in as admin...")
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
            print("Going to question mode...")
            question_btn = page.locator("button:has-text('질문모드')")
            await question_btn.click()
            await page.wait_for_timeout(2000)
            
            # 문법학습 토글 비활성화
            print("Disabling grammar toggle...")
            await page.evaluate("""
                document.getElementById('grammar-mode-toggle').checked = false;
                document.getElementById('grammar-mode-status').textContent = '비활성화';
            """)
            await page.wait_for_timeout(1000)
            
            # 설정 저장
            print("Saving settings...")
            await page.evaluate("saveQuestionModeSettings()")
            await page.wait_for_timeout(1000)
            
            # localStorage 확인
            settings = await page.evaluate("localStorage.getItem('questionModeSettings')")
            print(f"localStorage settings: {settings}")
            
            # 학생화면으로 전환
            print("Switching to student mode...")
            await page.evaluate("showUserMode()")
            await page.wait_for_timeout(2000)
            
            # 모드 버튼 상태 확인
            print("Checking student mode button states...")
            mode_buttons = page.locator(".mode-btn:not(.admin-mode-btn)")
            button_count = await mode_buttons.count()
            
            for i in range(button_count):
                button = mode_buttons.nth(i)
                button_text = await button.text_content()
                button_class = await button.get_attribute("class")
                button_opacity = await button.evaluate("el => getComputedStyle(el).opacity")
                button_pointer_events = await button.evaluate("el => getComputedStyle(el).pointerEvents")
                
                is_disabled = "disabled" in button_class if button_class else False
                
                print(f"Button '{button_text}':")
                print(f"  - Class: {button_class}")
                print(f"  - Opacity: {button_opacity}")
                print(f"  - Pointer Events: {button_pointer_events}")
                print(f"  - Disabled: {is_disabled}")
                print()
            
            # JavaScript로 updateStudentModeButtons 함수 직접 호출
            print("Calling updateStudentModeButtons directly...")
            await page.evaluate("updateStudentModeButtons()")
            await page.wait_for_timeout(1000)
            
            # 다시 버튼 상태 확인
            print("Checking button states after direct call...")
            for i in range(button_count):
                button = mode_buttons.nth(i)
                button_text = await button.text_content()
                button_class = await button.get_attribute("class")
                button_opacity = await button.evaluate("el => getComputedStyle(el).opacity")
                button_pointer_events = await button.evaluate("el => getComputedStyle(el).pointerEvents")
                
                is_disabled = "disabled" in button_class if button_class else False
                
                print(f"Button '{button_text}':")
                print(f"  - Class: {button_class}")
                print(f"  - Opacity: {button_opacity}")
                print(f"  - Pointer Events: {button_pointer_events}")
                print(f"  - Disabled: {is_disabled}")
                print()
            
            print("Test completed!")
            
        except Exception as e:
            print(f"Error: {e}")
            await page.screenshot(path="student_buttons_error.png")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_student_buttons())



