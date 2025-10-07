#!/usr/bin/env python3
"""
모달 디버깅 테스트
"""

import asyncio
from playwright.async_api import async_playwright

async def test_modal_debug():
    """모달 디버깅 테스트"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=2000)
        page = await browser.new_page()
        
        try:
            print("페이지 로드 중...")
            await page.goto('http://localhost:8080/neumorphism_app.html')
            await page.wait_for_load_state('networkidle')
            
            # 모달 요소 확인
            modal = page.locator('#passwordModal')
            modal_display = await modal.evaluate('el => getComputedStyle(el).display')
            print(f"모달 초기 display: {modal_display}")
            
            # 관리자 버튼 클릭
            print("관리자 버튼 클릭...")
            admin_btn = page.locator('button[title="관리자 로그인"]')
            
            # 클릭 전에 버튼이 존재하는지 확인
            btn_count = await admin_btn.count()
            print(f"관리자 버튼 개수: {btn_count}")
            
            if btn_count > 0:
                await admin_btn.click()
                
                # 잠시 대기
                await page.wait_for_timeout(1000)
                
                # 모달 상태 다시 확인
                modal_display_after = await modal.evaluate('el => getComputedStyle(el).display')
                print(f"클릭 후 모달 display: {modal_display_after}")
                
                # 모달이 보이는지 확인
                is_visible = await modal.is_visible()
                print(f"모달이 보이는가: {is_visible}")
                
                # JavaScript 오류 확인
                console_messages = []
                page.on('console', lambda msg: console_messages.append(msg.text))
                print(f"콘솔 메시지: {console_messages}")
            else:
                print("관리자 버튼을 찾을 수 없습니다!")
            
            # JavaScript로 직접 adminLogin 함수 호출
            print("JavaScript로 adminLogin 함수 직접 호출...")
            try:
                await page.evaluate('adminLogin()')
            except Exception as e:
                print(f"adminLogin 함수 호출 오류: {e}")
                
                # 함수가 정의되어 있는지 확인
                is_defined = await page.evaluate('typeof adminLogin')
                print(f"adminLogin 함수 정의 상태: {is_defined}")
                
                # 모든 전역 함수 확인
                functions = await page.evaluate('Object.keys(window).filter(key => typeof window[key] === "function")')
                print(f"전역 함수들: {functions[:10]}")  # 처음 10개만 출력
            
            await page.wait_for_timeout(1000)
            
            # 모달 상태 확인
            modal_display_direct = await modal.evaluate('el => getComputedStyle(el).display')
            print(f"직접 호출 후 display: {modal_display_direct}")
            
            # JavaScript로 직접 모달 표시
            print("JavaScript로 모달 강제 표시...")
            await page.evaluate('document.getElementById("passwordModal").style.display = "block"')
            
            await page.wait_for_timeout(1000)
            
            # 다시 확인
            modal_display_force = await modal.evaluate('el => getComputedStyle(el).display')
            print(f"강제 표시 후 display: {modal_display_force}")
            
            is_visible_force = await modal.is_visible()
            print(f"강제 표시 후 보이는가: {is_visible_force}")
            
            # 비밀번호 입력 테스트
            if is_visible_force:
                print("비밀번호 입력 테스트...")
                password_input = page.locator('#adminPassword')
                await password_input.fill('admin123')
                
                # 로그인 버튼 클릭 (모달 내부의 버튼만)
                login_btn = page.locator('#passwordModal button:has-text("로그인")')
                await login_btn.click()
                
                await page.wait_for_timeout(2000)
                
                # 관리자 버튼 확인
                admin_buttons = page.locator('.admin-mode-btn')
                button_count = await admin_buttons.count()
                print(f"관리자 버튼 개수: {button_count}")
                
        except Exception as e:
            print(f"오류 발생: {e}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_modal_debug())
