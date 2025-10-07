#!/usr/bin/env python3
"""
관리자 로그인 테스트 및 Playwright 앱 실행 테스트
"""

import asyncio
from playwright.async_api import async_playwright
import time

async def test_admin_login():
    """관리자 로그인 기능 테스트"""
    async with async_playwright() as p:
        # 브라우저 시작
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        page = await browser.new_page()
        
        try:
            print("Neumorphism 앱에 접속 중...")
            await page.goto('http://localhost:8080/neumorphism_app.html')
            await page.wait_for_load_state('networkidle')
            
            print("페이지 로드 완료")
            
            # 관리자 로그인 버튼 클릭
            print("관리자 로그인 버튼 클릭...")
            admin_btn = page.locator('button[title="관리자 로그인"]')
            await admin_btn.click()
            
            # 모달이 나타나는지 확인
            print("비밀번호 모달 확인...")
            modal = page.locator('#passwordModal')
            await modal.wait_for(state='visible', timeout=5000)
            
            # 비밀번호 입력
            print("비밀번호 입력...")
            password_input = page.locator('#adminPassword')
            await password_input.fill('admin123')
            
            # 로그인 버튼 클릭
            print("로그인 버튼 클릭...")
            login_btn = page.locator('button:has-text("로그인")')
            await login_btn.click()
            
            # 관리자 모드 진입 확인
            print("관리자 모드 진입 확인...")
            await page.wait_for_timeout(2000)
            
            # 관리자 버튼들이 나타나는지 확인
            admin_buttons = page.locator('.admin-mode-btn')
            button_count = await admin_buttons.count()
            print(f"관리자 버튼 개수: {button_count}")
            
            if button_count > 0:
                print("관리자 모드 진입 성공!")
                
                # 각 관리자 버튼 테스트
                for i in range(button_count):
                    button_text = await admin_buttons.nth(i).text_content()
                    print(f"관리자 버튼 {i+1}: {button_text}")
                    await admin_buttons.nth(i).click()
                    await page.wait_for_timeout(1000)
                
                # 로그아웃 테스트
                print("로그아웃 테스트...")
                logout_btn = page.locator('button[title="관리자 로그아웃"]')
                if await logout_btn.count() > 0:
                    await logout_btn.click()
                    await page.wait_for_timeout(1000)
                    print("로그아웃 성공!")
                
            else:
                print("관리자 모드 진입 실패 - 버튼이 없습니다")
                
        except Exception as e:
            print(f"테스트 중 오류 발생: {e}")
            
        finally:
            await browser.close()

async def test_app_functionality():
    """앱 전체 기능 테스트"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        page = await browser.new_page()
        
        try:
            print("앱 기능 테스트 시작...")
            await page.goto('http://localhost:8080/neumorphism_app.html')
            await page.wait_for_load_state('networkidle')
            
            # 모드 선택 테스트
            print("모드 선택 테스트...")
            mode_buttons = page.locator('.mode-btn')
            mode_count = await mode_buttons.count()
            print(f"모드 버튼 개수: {mode_count}")
            
            for i in range(min(mode_count, 3)):  # 최대 3개만 테스트
                button_text = await mode_buttons.nth(i).text_content()
                print(f"모드 버튼 클릭: {button_text}")
                await mode_buttons.nth(i).click()
                await page.wait_for_timeout(500)
            
            # 질문 입력 테스트
            print("질문 입력 테스트...")
            question_input = page.locator('#question-input')
            await question_input.fill('테스트 질문입니다')
            
            # 질문하기 버튼 클릭
            ask_btn = page.locator('.ask-button')
            await ask_btn.click()
            await page.wait_for_timeout(2000)
            
            print("앱 기능 테스트 완료!")
            
        except Exception as e:
            print(f"앱 테스트 중 오류 발생: {e}")
            
        finally:
            await browser.close()

async def main():
    """메인 테스트 함수"""
    print("MAIC Neumorphism 앱 테스트 시작")
    print("=" * 50)
    
    # 관리자 로그인 테스트
    print("\n1. 관리자 로그인 테스트")
    await test_admin_login()
    
    print("\n" + "=" * 50)
    
    # 앱 기능 테스트
    print("\n2. 앱 전체 기능 테스트")
    await test_app_functionality()
    
    print("\n" + "=" * 50)
    print("모든 테스트 완료!")

if __name__ == "__main__":
    asyncio.run(main())
