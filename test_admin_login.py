#!/usr/bin/env python3
"""관리자 로그인 자동 테스트"""

import asyncio
from playwright.async_api import async_playwright
import time

async def test_admin_login():
    """관리자 로그인 테스트"""
    print("=== 관리자 로그인 테스트 시작 ===")
    
    async with async_playwright() as p:
        # 브라우저 시작
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        page = await browser.new_page()
        
        try:
            # 앱 접속
            print("1. 앱 접속 중...")
            await page.goto("http://localhost:8501")
            await page.wait_for_load_state("networkidle")
            print("   [OK] 앱 접속 완료")
            
            # 페이지 로딩 대기
            await page.wait_for_timeout(3000)
            
            # 관리자 버튼 찾기
            print("2. 관리자 버튼 찾는 중...")
            admin_button = page.locator("button:has-text('관리자')")
            
            if await admin_button.count() > 0:
                print("   [OK] 관리자 버튼 발견")
                
                # 관리자 버튼 클릭 (첫 번째 버튼만)
                print("3. 관리자 버튼 클릭...")
                await admin_button.first.click()
                await page.wait_for_timeout(2000)
                
                # 비밀번호 입력 필드 확인
                print("4. 비밀번호 입력 필드 확인...")
                password_input = page.locator("input[type='password']")
                
                if await password_input.count() > 0:
                    print("   [OK] 비밀번호 입력 필드 발견")
                    
                    # 비밀번호 입력
                    print("5. 비밀번호 입력...")
                    await password_input.fill("0000")
                    await page.wait_for_timeout(1000)
                    
                    # 로그인 버튼 클릭
                    print("6. 로그인 버튼 클릭...")
                    login_button = page.locator("button:has-text('로그인')")
                    
                    if await login_button.count() > 0:
                        await login_button.click()
                        await page.wait_for_timeout(3000)
                        
                        # 로그인 성공 확인
                        print("7. 로그인 성공 확인...")
                        
                        # 로그아웃 버튼이 나타나는지 확인
                        logout_button = page.locator("button:has-text('로그아웃')")
                        if await logout_button.count() > 0:
                            print("   [OK] 관리자 로그인 성공!")
                            print("   [OK] 로그아웃 버튼 발견")
                            
                            # 관리자 패널 확인
                            print("8. 관리자 패널 확인...")
                            admin_panel = page.locator("text=인덱스 오케스트레이터")
                            if await admin_panel.count() > 0:
                                print("   [OK] 관리자 패널 표시됨")
                            else:
                                print("   [WARN] 관리자 패널이 표시되지 않음")
                            
                # 로그아웃 테스트 (첫 번째 버튼만)
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
            # 스크린샷 저장
            await page.screenshot(path="admin_login_test_result.png")
            print("   [SCREENSHOT] 테스트 결과 스크린샷 저장: admin_login_test_result.png")
            
            await browser.close()
    
    print("=== 관리자 로그인 테스트 완료 ===")

if __name__ == "__main__":
    asyncio.run(test_admin_login())
