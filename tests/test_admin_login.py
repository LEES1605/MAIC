#!/usr/bin/env python3
"""
관리자 로그인 E2E 테스트
Playwright를 사용하여 관리자 로그인 기능을 테스트합니다.
"""

import asyncio
from playwright.async_api import async_playwright

async def test_admin_login():
    """관리자 로그인 테스트"""
    print("=" * 60)
    print("관리자 로그인 E2E 테스트 시작")
    print("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # 1. 앱 접속
            print("1. 앱 접속...")
            await page.goto("http://localhost:8501")
            await page.wait_for_load_state("networkidle")
            print("   [OK] 앱 접속 성공")
            
            # 2. 관리자 버튼 확인
            print("2. 관리자 버튼 확인...")
            # 모든 버튼 찾기
            all_buttons = page.locator("button")
            button_count = await all_buttons.count()
            print(f"   [DEBUG] 총 {button_count}개의 버튼 발견")
            
            # 버튼 텍스트 확인
            for i in range(button_count):
                button_text = await all_buttons.nth(i).text_content()
                print(f"   [DEBUG] 버튼 {i}: '{button_text}'")
            
            admin_button = page.locator("button").filter(has_text="관리자")
            
            if await admin_button.count() > 0:
                print("   [OK] 관리자 버튼 발견")
                
                # 3. 관리자 버튼 클릭
                print("3. 관리자 버튼 클릭...")
                await admin_button.click()
                await page.wait_for_timeout(2000)
                
                # 4. 비밀번호 입력 필드 확인
                print("4. 비밀번호 입력 필드 확인...")
                password_input = page.locator("input[type='password']")
                
                if await password_input.count() > 0:
                    print("   [OK] 비밀번호 입력 필드 발견")
                    
                    # 5. 비밀번호 입력
                    print("5. 비밀번호 입력...")
                    await password_input.fill("0000")
                    await page.wait_for_timeout(1000)
                    
                    # 6. 로그인 버튼 클릭
                    print("6. 로그인 버튼 클릭...")
                    login_button = page.locator("button:has-text('로그인')")
                    
                    if await login_button.count() > 0:
                        await login_button.click()
                        await page.wait_for_timeout(3000)
                        
                        # 7. 로그인 성공 확인
                        print("7. 로그인 성공 확인...")
                        
                        # 로그아웃 버튼이 나타나는지 확인
                        logout_button = page.locator("button:has-text('로그아웃')")
                        if await logout_button.count() > 0:
                            print("   [OK] 관리자 로그인 성공!")
                            print("   [OK] 로그아웃 버튼 발견")
                            
                            # 8. 관리자 패널 확인
                            print("8. 관리자 패널 확인...")
                            admin_panel = page.locator("text=인덱스 오케스트레이터")
                            if await admin_panel.count() > 0:
                                print("   [OK] 관리자 패널 표시됨")
                            else:
                                print("   [WARN] 관리자 패널이 표시되지 않음")
                            
                            # 9. 로그아웃 테스트
                            print("9. 로그아웃 테스트...")
                            await logout_button.first.click()
                            await page.wait_for_timeout(2000)
                            
                            # 관리자 버튼이 다시 나타나는지 확인
                            admin_button_after = page.locator("button:has-text('관리자')")
                            if await admin_button_after.count() > 0:
                                print("   [OK] 로그아웃 성공!")
                            else:
                                print("   [WARN] 로그아웃 후 관리자 버튼이 나타나지 않음")
                        else:
                            print("   [ERROR] 로그인 실패 - 로그아웃 버튼이 나타나지 않음")
                    else:
                        print("   [ERROR] 로그인 버튼을 찾을 수 없음")
                else:
                    print("   [ERROR] 비밀번호 입력 필드가 나타나지 않음")
            else:
                print("   [ERROR] 관리자 버튼을 찾을 수 없음")
                
        except Exception as e:
            print(f"   [ERROR] 테스트 중 오류 발생: {e}")
            
        finally:
            await browser.close()
    
    print("=" * 60)
    print("관리자 로그인 E2E 테스트 완료")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_admin_login())