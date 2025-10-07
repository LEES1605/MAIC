#!/usr/bin/env python3
"""
간단한 디버그 테스트
"""

import asyncio
from playwright.async_api import async_playwright

async def test_simple_debug():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            print("Simple debug test start")
            
            # 앱 로드
            await page.goto("http://localhost:8080/neumorphism_app.html")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(3000)
            
            # 버튼들 찾기
            buttons = page.locator("button")
            count = await buttons.count()
            print(f"Total buttons: {count}")
            
            for i in range(count):
                button = buttons.nth(i)
                text = await button.text_content()
                button_id = await button.get_attribute("id")
                print(f"Button {i}: text='{text}', id='{button_id}'")
            
            # 관리자 로그인 버튼 클릭 시도
            admin_btn = page.locator("#admin-login-btn")
            if await admin_btn.count() > 0:
                print("Found admin login button, clicking...")
                await admin_btn.click()
                await page.wait_for_timeout(2000)
                
                # 비밀번호 입력
                password_input = page.locator("#adminPassword")
                if await password_input.count() > 0:
                    print("Found password input, filling...")
                    await password_input.fill("admin123")
                    await page.wait_for_timeout(1000)
                    
                    # 로그인 버튼 클릭
                    login_btn = page.locator("#modal-login-btn")
                    if await login_btn.count() > 0:
                        print("Found login button, clicking...")
                        await login_btn.click()
                        await page.wait_for_timeout(3000)
                        
                        # 질문모드 버튼 찾기
                        question_btn = page.locator("button:has-text('질문모드')")
                        if await question_btn.count() > 0:
                            print("Found question mode button, clicking...")
                            await question_btn.click()
                            await page.wait_for_timeout(2000)
                            
                            # 토글 상태 확인
                            grammar_toggle = page.locator("#grammar-mode-toggle")
                            if await grammar_toggle.count() > 0:
                                checked = await grammar_toggle.is_checked()
                                print(f"Grammar toggle checked: {checked}")
                                
                                # 토글 클릭
                                await grammar_toggle.click()
                                await page.wait_for_timeout(1000)
                                
                                checked_after = await grammar_toggle.is_checked()
                                print(f"Grammar toggle after click: {checked_after}")
                                
                                # 설정 저장
                                save_btn = page.locator("button:has-text('설정 저장')")
                                if await save_btn.count() > 0:
                                    print("Found save button, clicking...")
                                    await save_btn.click()
                                    await page.wait_for_timeout(1000)
                                    
                                    # localStorage 확인
                                    settings = await page.evaluate("localStorage.getItem('questionModeSettings')")
                                    print(f"localStorage settings: {settings}")
                                else:
                                    print("Save button not found")
                            else:
                                print("Grammar toggle not found")
                        else:
                            print("Question mode button not found")
                    else:
                        print("Login button not found")
                else:
                    print("Password input not found")
            else:
                print("Admin login button not found")
            
            print("Test completed")
            
        except Exception as e:
            print(f"Error: {e}")
            await page.screenshot(path="simple_debug_error.png")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_simple_debug())
