#!/usr/bin/env python3
"""
콘솔 로그 확인 테스트
"""

import asyncio
from playwright.async_api import async_playwright

async def test_console_logs():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        context = await browser.new_context()
        page = await context.new_page()
        
        # 콘솔 로그 수집
        logs = []
        page.on("console", lambda msg: logs.append(f"{msg.type}: {msg.text}"))
        
        try:
            print("Console logs test start")
            
            # 앱 로드
            await page.goto("http://localhost:8080/neumorphism_app.html")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(3000)
            
            # 관리자 로그인
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
            await page.evaluate("""
                document.getElementById('grammar-mode-toggle').checked = false;
                document.getElementById('grammar-mode-status').textContent = '비활성화';
            """)
            await page.wait_for_timeout(1000)
            
            # 설정 저장
            await page.evaluate("saveQuestionModeSettings()")
            await page.wait_for_timeout(1000)
            
            # 학생화면으로 전환
            await page.evaluate("showUserMode()")
            await page.wait_for_timeout(2000)
            
            # updateStudentModeButtons 직접 호출
            await page.evaluate("updateStudentModeButtons()")
            await page.wait_for_timeout(1000)
            
            # 콘솔 로그 출력
            print("Console logs:")
            for log in logs:
                if "updateStudentModeButtons" in log or "버튼" in log or "모드" in log:
                    print(log)
            
            print("Test completed!")
            
        except Exception as e:
            print(f"Error: {e}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_console_logs())
