#!/usr/bin/env python3
"""
질문모드 토글 저장 기능 테스트
- 관리자 로그인
- 질문모드로 이동
- 토글 상태 변경
- 설정 저장
- localStorage 확인
- 학생화면으로 전환하여 모드 버튼 상태 확인
"""

import asyncio
from playwright.async_api import async_playwright
import json

async def test_question_mode_toggle():
    async with async_playwright() as p:
        # 브라우저 시작
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            print("질문모드 토글 저장 기능 테스트 시작")
            
            # 1. 앱 로드
            print("앱 로드 중...")
            await page.goto("http://localhost:8080/neumorphism_app.html")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000)
            
            # 2. 관리자 로그인
            print("관리자 로그인 중...")
            admin_login_btn = page.locator("#admin-login-btn")
            await admin_login_btn.click()
            await page.wait_for_timeout(1000)
            
            # 비밀번호 입력
            password_input = page.locator("#password-input")
            await password_input.fill("admin123")
            await page.wait_for_timeout(500)
            
            # 로그인 버튼 클릭
            login_btn = page.locator("#modal-login-btn")
            await login_btn.click()
            await page.wait_for_timeout(2000)
            
            # 3. 질문모드 버튼 클릭
            print("질문모드로 이동 중...")
            question_mode_btn = page.locator("button:has-text('질문모드')")
            await question_mode_btn.click()
            await page.wait_for_timeout(2000)
            
            # 4. 현재 토글 상태 확인
            print("현재 토글 상태 확인...")
            grammar_toggle = page.locator("#grammar-mode-toggle")
            sentence_toggle = page.locator("#sentence-mode-toggle")
            passage_toggle = page.locator("#passage-mode-toggle")
            
            grammar_checked = await grammar_toggle.is_checked()
            sentence_checked = await sentence_toggle.is_checked()
            passage_checked = await passage_toggle.is_checked()
            
            print(f"   문법학습: {'활성화' if grammar_checked else '비활성화'}")
            print(f"   문장분석: {'활성화' if sentence_checked else '비활성화'}")
            print(f"   지문설명: {'활성화' if passage_checked else '비활성화'}")
            
            # 5. 토글 상태 변경 (문장분석 비활성화)
            print("토글 상태 변경 중...")
            await sentence_toggle.click()
            await page.wait_for_timeout(1000)
            
            # 변경된 상태 확인
            sentence_checked_after = await sentence_toggle.is_checked()
            print(f"   문장분석 변경 후: {'활성화' if sentence_checked_after else '비활성화'}")
            
            # 6. 설정 저장
            print("설정 저장 중...")
            save_btn = page.locator("button:has-text('설정 저장')")
            await save_btn.click()
            await page.wait_for_timeout(1000)
            
            # 7. localStorage 확인
            print("localStorage 확인 중...")
            settings = await page.evaluate("localStorage.getItem('questionModeSettings')")
            if settings:
                settings_obj = json.loads(settings)
                print(f"   localStorage 저장된 설정: {settings_obj}")
            else:
                print("   localStorage에 설정이 저장되지 않음!")
            
            # 8. 학생화면으로 전환
            print("학생화면으로 전환 중...")
            logout_btn = page.locator("button:has-text('로그아웃')")
            await logout_btn.click()
            await page.wait_for_timeout(2000)
            
            # 9. 학생화면 모드 버튼 상태 확인
            print("학생화면 모드 버튼 상태 확인...")
            mode_buttons = page.locator(".mode-btn:not(.admin-mode-btn)")
            button_count = await mode_buttons.count()
            
            for i in range(button_count):
                button = mode_buttons.nth(i)
                button_text = await button.text_content()
                button_class = await button.get_attribute("class")
                is_disabled = "disabled" in button_class if button_class else False
                
                print(f"   {button_text}: {'비활성화' if is_disabled else '활성화'}")
            
            # 10. 다시 관리자 모드로 돌아가서 설정 복원 확인
            print("관리자 모드로 돌아가서 설정 복원 확인...")
            admin_login_btn = page.locator("#admin-login-btn")
            await admin_login_btn.click()
            await page.wait_for_timeout(1000)
            
            password_input = page.locator("#password-input")
            await password_input.fill("admin123")
            await page.wait_for_timeout(500)
            
            login_btn = page.locator("#modal-login-btn")
            await login_btn.click()
            await page.wait_for_timeout(2000)
            
            # 질문모드로 이동
            question_mode_btn = page.locator("button:has-text('질문모드')")
            await question_mode_btn.click()
            await page.wait_for_timeout(2000)
            
            # 토글 상태 재확인
            print("설정 복원 확인...")
            sentence_toggle_restored = page.locator("#sentence-mode-toggle")
            sentence_checked_restored = await sentence_toggle_restored.is_checked()
            print(f"   문장분석 복원 후: {'활성화' if sentence_checked_restored else '비활성화'}")
            
            if sentence_checked_after == sentence_checked_restored:
                print("설정이 올바르게 저장되고 복원되었습니다!")
            else:
                print("설정 저장/복원에 문제가 있습니다!")
            
            print("테스트 완료!")
            
        except Exception as e:
            print(f"테스트 중 오류 발생: {e}")
            await page.screenshot(path="error_screenshot.png")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_question_mode_toggle())
