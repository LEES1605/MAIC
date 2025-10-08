#!/usr/bin/env python3
"""
토글 동기화 문제 테스트
"""

import asyncio
from playwright.async_api import async_playwright
import json

async def test_toggle_sync_issue():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            print("Toggle sync issue test start")
            
            # 앱 로드
            await page.goto("http://localhost:8080/neumorphism_app.html")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(3000)
            
            # 현재 localStorage 상태 확인
            print("1. 초기 localStorage 상태 확인...")
            settings = await page.evaluate("localStorage.getItem('questionModeSettings')")
            print(f"   localStorage: {settings}")
            
            # 관리자 로그인
            print("2. 관리자 로그인...")
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
            print("3. 질문모드로 이동...")
            question_btn = page.locator("button:has-text('질문모드')")
            await question_btn.click()
            await page.wait_for_timeout(2000)
            
            # 현재 토글 상태 확인
            print("4. 현재 토글 상태 확인...")
            grammar_checked = await page.evaluate("document.getElementById('grammar-mode-toggle').checked")
            sentence_checked = await page.evaluate("document.getElementById('sentence-mode-toggle').checked")
            passage_checked = await page.evaluate("document.getElementById('passage-mode-toggle').checked")
            
            print(f"   문법학습: {grammar_checked}")
            print(f"   문장분석: {sentence_checked}")
            print(f"   지문설명: {passage_checked}")
            
            # 문법학습 토글을 활성화로 변경
            print("5. 문법학습 토글을 활성화로 변경...")
            await page.evaluate("""
                document.getElementById('grammar-mode-toggle').checked = true;
                document.getElementById('grammar-mode-status').textContent = '활성화';
            """)
            await page.wait_for_timeout(1000)
            
            # 변경된 토글 상태 확인
            grammar_checked_after = await page.evaluate("document.getElementById('grammar-mode-toggle').checked")
            print(f"   변경 후 문법학습: {grammar_checked_after}")
            
            # 설정 저장
            print("6. 설정 저장...")
            await page.evaluate("saveQuestionModeSettings()")
            await page.wait_for_timeout(1000)
            
            # localStorage 확인
            settings_after = await page.evaluate("localStorage.getItem('questionModeSettings')")
            print(f"   저장 후 localStorage: {settings_after}")
            
            # 학생화면으로 전환
            print("7. 학생화면으로 전환...")
            await page.evaluate("showUserMode()")
            await page.wait_for_timeout(2000)
            
            # 학생화면 모드 버튼 상태 확인
            print("8. 학생화면 모드 버튼 상태 확인...")
            mode_buttons = page.locator(".mode-btn:not(.admin-mode-btn)")
            button_count = await mode_buttons.count()
            
            for i in range(button_count):
                button = mode_buttons.nth(i)
                button_text = await button.text_content()
                button_class = await button.get_attribute("class")
                is_disabled = "disabled" in button_class if button_class else False
                
                print(f"   {button_text}: {'비활성화' if is_disabled else '활성화'}")
            
            # 다시 관리자 모드로 돌아가서 토글 상태 재확인
            print("9. 관리자 모드로 돌아가서 토글 상태 재확인...")
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
            print("10. 토글 상태 재확인...")
            grammar_checked_restored = await page.evaluate("document.getElementById('grammar-mode-toggle').checked")
            sentence_checked_restored = await page.evaluate("document.getElementById('sentence-mode-toggle').checked")
            passage_checked_restored = await page.evaluate("document.getElementById('passage-mode-toggle').checked")
            
            print(f"   복원 후 문법학습: {grammar_checked_restored}")
            print(f"   복원 후 문장분석: {sentence_checked_restored}")
            print(f"   복원 후 지문설명: {passage_checked_restored}")
            
            print("Test completed!")
            
        except Exception as e:
            print(f"Error: {e}")
            await page.screenshot(path="toggle_sync_issue_error.png")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_toggle_sync_issue())



