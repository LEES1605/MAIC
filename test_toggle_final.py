#!/usr/bin/env python3
"""
최종 토글 저장 기능 테스트
"""

import asyncio
from playwright.async_api import async_playwright
import json

async def test_toggle_final():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            print("Final toggle save test start")
            
            # 앱 로드
            await page.goto("http://localhost:8080/neumorphism_app.html")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(3000)
            
            # 모달이 열려있는지 확인하고 닫기
            modal = page.locator("#passwordModal")
            if await modal.count() > 0:
                modal_visible = await modal.is_visible()
                if modal_visible:
                    print("Modal is open, closing it...")
                    await page.evaluate("closeModal()")
                    await page.wait_for_timeout(1000)
            
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
            
            # JavaScript로 토글 상태 확인 및 변경
            print("Checking and modifying toggle states...")
            
            # 현재 토글 상태 확인
            grammar_checked = await page.evaluate("document.getElementById('grammar-mode-toggle').checked")
            sentence_checked = await page.evaluate("document.getElementById('sentence-mode-toggle').checked")
            passage_checked = await page.evaluate("document.getElementById('passage-mode-toggle').checked")
            
            print(f"Initial state - Grammar: {grammar_checked}, Sentence: {sentence_checked}, Passage: {passage_checked}")
            
            # 문장분석 토글 비활성화
            print("Disabling sentence toggle...")
            await page.evaluate("""
                document.getElementById('sentence-mode-toggle').checked = false;
                document.getElementById('sentence-mode-status').textContent = '비활성화';
            """)
            await page.wait_for_timeout(1000)
            
            # 설정 저장 함수 호출
            print("Saving settings...")
            await page.evaluate("saveQuestionModeSettings()")
            await page.wait_for_timeout(1000)
            
            # localStorage 확인
            settings = await page.evaluate("localStorage.getItem('questionModeSettings')")
            print(f"localStorage settings: {settings}")
            
            if settings:
                settings_obj = json.loads(settings)
                print(f"Parsed settings: {settings_obj}")
                
                if settings_obj.get('sentence') == False:
                    print("SUCCESS: Sentence mode correctly saved as disabled!")
                else:
                    print("ERROR: Sentence mode not saved as disabled!")
            else:
                print("ERROR: No settings found in localStorage!")
            
            # 학생화면으로 전환하여 모드 버튼 상태 확인
            print("Switching to student mode...")
            logout_btn = page.locator("button:has-text('로그아웃')")
            await logout_btn.click()
            await page.wait_for_timeout(2000)
            
            # 모드 버튼 상태 확인
            print("Checking student mode button states...")
            mode_buttons = page.locator(".mode-btn:not(.admin-mode-btn)")
            button_count = await mode_buttons.count()
            
            for i in range(button_count):
                button = mode_buttons.nth(i)
                button_text = await button.text_content()
                button_class = await button.get_attribute("class")
                is_disabled = "disabled" in button_class if button_class else False
                
                print(f"Button '{button_text}': {'DISABLED' if is_disabled else 'ENABLED'}")
            
            # 다시 관리자 모드로 돌아가서 설정 복원 확인
            print("Returning to admin mode to verify settings...")
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
            
            # 토글 상태 재확인
            print("Verifying settings restoration...")
            sentence_checked_restored = await page.evaluate("document.getElementById('sentence-mode-toggle').checked")
            print(f"Sentence toggle after restoration: {sentence_checked_restored}")
            
            if sentence_checked_restored == False:
                print("SUCCESS: Settings correctly restored!")
            else:
                print("ERROR: Settings not properly restored!")
            
            print("Test completed successfully!")
            
        except Exception as e:
            print(f"Error: {e}")
            await page.screenshot(path="toggle_final_error.png")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_toggle_final())

