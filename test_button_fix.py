#!/usr/bin/env python3
"""
버튼 수정 후 테스트
"""

import asyncio
from playwright.async_api import async_playwright

async def test_button_fix():
    """버튼 수정 후 테스트"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        page = await browser.new_page()
        
        try:
            print("페이지 로드 중...")
            await page.goto('http://localhost:8080/neumorphism_app.html')
            await page.wait_for_load_state('networkidle')
            
            # 콘솔 메시지 수집
            console_messages = []
            page.on('console', lambda msg: console_messages.append(msg.text))
            
            await page.wait_for_timeout(2000)
            
            print("콘솔 메시지:")
            for msg in console_messages:
                print(f"  - {msg}")
            
            # 관리자 로그인 버튼 테스트
            print("\n관리자 로그인 버튼 테스트...")
            admin_btn = page.locator('button[title="관리자 로그인"]')
            await admin_btn.click()
            
            await page.wait_for_timeout(1000)
            
            # 모달 확인
            modal = page.locator('#passwordModal')
            is_visible = await modal.is_visible()
            print(f"모달 표시됨: {is_visible}")
            
            if is_visible:
                # 비밀번호 입력
                password_input = page.locator('#adminPassword')
                await password_input.fill('admin123')
                
                # 로그인 버튼 클릭
                login_btn = page.locator('#modal-login-btn')
                await login_btn.click()
                
                await page.wait_for_timeout(2000)
                
                # 관리자 버튼 확인
                admin_buttons = page.locator('.admin-mode-btn')
                button_count = await admin_buttons.count()
                print(f"관리자 버튼 개수: {button_count}")
                
                if button_count > 0:
                    print("관리자 모드 진입 성공!")
                    
                    # 첫 번째 관리자 버튼 클릭 테스트
                    first_btn = admin_buttons.first
                    btn_text = await first_btn.text_content()
                    print(f"첫 번째 버튼 클릭: {btn_text}")
                    await first_btn.click()
                    
                    await page.wait_for_timeout(2000)
                    
                    # 응답 영역 확인
                    response_area = page.locator('#response-area')
                    response_text = await response_area.text_content()
                    print(f"응답 영역 내용: {response_text[:100]}...")
                    
                else:
                    print("관리자 모드 진입 실패")
            else:
                print("모달이 표시되지 않음")
            
            # 일반 모드 버튼 테스트
            print("\n일반 모드 버튼 테스트...")
            mode_buttons = page.locator('.mode-btn')
            mode_count = await mode_buttons.count()
            print(f"모드 버튼 개수: {mode_count}")
            
            if mode_count > 0:
                first_mode_btn = mode_buttons.first
                mode_text = await first_mode_btn.text_content()
                print(f"첫 번째 모드 버튼 클릭: {mode_text}")
                await first_mode_btn.click()
                
                await page.wait_for_timeout(1000)
                
                # 질문 입력 테스트
                question_input = page.locator('#question-input')
                await question_input.fill('테스트 질문입니다')
                
                # 질문하기 버튼 클릭
                ask_btn = page.locator('.ask-button')
                await ask_btn.click()
                
                await page.wait_for_timeout(2000)
                
                print("질문하기 버튼 클릭 완료")
            
        except Exception as e:
            print(f"오류 발생: {e}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_button_fix())


