#!/usr/bin/env python3
"""
토글 상태 복원 테스트
"""

import asyncio
from playwright.async_api import async_playwright
import json

async def test_toggle_restore():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            print("Toggle restore test start")
            
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
            
            # 문법학습 토글 비활성화
            print("3. 문법학습 토글 비활성화...")
            await page.evaluate("""
                document.getElementById('grammar-mode-toggle').checked = false;
                document.getElementById('grammar-mode-status').textContent = '비활성화';
            """)
            await page.wait_for_timeout(1000)
            
            # 설정 저장
            print("4. 설정 저장...")
            await page.evaluate("saveQuestionModeSettings()")
            await page.wait_for_timeout(1000)
            
            # localStorage 확인
            settings = await page.evaluate("localStorage.getItem('questionModeSettings')")
            print(f"   저장된 설정: {settings}")
            
            # 학생화면으로 전환
            print("5. 학생화면으로 전환...")
            await page.evaluate("showUserMode()")
            await page.wait_for_timeout(2000)
            
            # 학생화면 모드 버튼 상태 확인
            print("6. 학생화면 모드 버튼 상태 확인...")
            mode_buttons = page.locator(".mode-btn:not(.admin-mode-btn)")
            button_count = await mode_buttons.count()
            
            for i in range(button_count):
                button = mode_buttons.nth(i)
                button_text = await button.text_content()
                button_class = await button.get_attribute("class")
                is_disabled = "disabled" in button_class if button_class else False
                
                print(f"   {button_text}: {'비활성화' if is_disabled else '활성화'}")
            
            # 다시 관리자 모드로 돌아가기
            print("7. 관리자 모드로 돌아가기...")
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
            print("8. 질문모드로 이동 (토글 상태 복원 테스트)...")
            question_btn = page.locator("button:has-text('질문모드')")
            await question_btn.click()
            await page.wait_for_timeout(2000)
            
            # 토글 상태 확인 (복원되었는지)
            print("9. 토글 상태 복원 확인...")
            grammar_checked = await page.evaluate("document.getElementById('grammar-mode-toggle').checked")
            sentence_checked = await page.evaluate("document.getElementById('sentence-mode-toggle').checked")
            passage_checked = await page.evaluate("document.getElementById('passage-mode-toggle').checked")
            
            print(f"   문법학습: {grammar_checked} (예상: False)")
            print(f"   문장분석: {sentence_checked} (예상: True)")
            print(f"   지문설명: {passage_checked} (예상: True)")
            
            # 상태 텍스트 확인
            grammar_status = await page.evaluate("document.getElementById('grammar-mode-status').textContent")
            sentence_status = await page.evaluate("document.getElementById('sentence-mode-status').textContent")
            passage_status = await page.evaluate("document.getElementById('passage-mode-status').textContent")
            
            print(f"   문법학습 상태: {grammar_status} (예상: 비활성화)")
            print(f"   문장분석 상태: {sentence_status} (예상: 활성화)")
            print(f"   지문설명 상태: {passage_status} (예상: 활성화)")
            
            # 문법학습 토글을 다시 활성화
            print("10. 문법학습 토글을 활성화로 변경...")
            await page.evaluate("""
                document.getElementById('grammar-mode-toggle').checked = true;
                document.getElementById('grammar-mode-status').textContent = '활성화';
            """)
            await page.wait_for_timeout(1000)
            
            # 학생화면으로 전환하여 즉시 반영 확인
            print("11. 학생화면으로 전환하여 즉시 반영 확인...")
            await page.evaluate("showUserMode()")
            await page.wait_for_timeout(2000)
            
            # 학생화면 모드 버튼 상태 확인
            print("12. 학생화면 모드 버튼 상태 확인 (즉시 반영)...")
            mode_buttons = page.locator(".mode-btn:not(.admin-mode-btn)")
            button_count = await mode_buttons.count()
            
            for i in range(button_count):
                button = mode_buttons.nth(i)
                button_text = await button.text_content()
                button_class = await button.get_attribute("class")
                is_disabled = "disabled" in button_class if button_class else False
                
                print(f"   {button_text}: {'비활성화' if is_disabled else '활성화'}")
            
            print("Test completed!")
            
        except Exception as e:
            print(f"Error: {e}")
            await page.screenshot(path="toggle_restore_error.png")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_toggle_restore())
