#!/usr/bin/env python3
"""
간단한 관리자 로그인 테스트
"""

import asyncio
from playwright.async_api import async_playwright

async def test_simple_admin():
    """간단한 관리자 로그인 테스트"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        page = await browser.new_page()
        
        try:
            print("페이지 로드 중...")
            await page.goto('http://localhost:8080/neumorphism_app.html')
            await page.wait_for_load_state('networkidle')
            
            # JavaScript 함수가 정의되어 있는지 확인
            print("JavaScript 함수 확인...")
            functions = await page.evaluate('''
                () => {
                    const funcs = [];
                    for (let key in window) {
                        if (typeof window[key] === 'function' && key.includes('admin')) {
                            funcs.push(key);
                        }
                    }
                    return funcs;
                }
            ''')
            print(f"관리자 관련 함수들: {functions}")
            
            # adminLogin 함수 직접 정의
            print("adminLogin 함수 직접 정의...")
            await page.evaluate('''
                window.adminLogin = function() {
                    console.log("adminLogin 함수 호출됨!");
                    const modal = document.getElementById("passwordModal");
                    if (modal) {
                        modal.style.display = "block";
                        console.log("모달 표시됨");
                    } else {
                        console.log("모달을 찾을 수 없음");
                    }
                }
            ''')
            
            # 관리자 버튼 클릭
            print("관리자 버튼 클릭...")
            admin_btn = page.locator('button[title="관리자 로그인"]')
            await admin_btn.click()
            
            await page.wait_for_timeout(2000)
            
            # 모달 상태 확인
            modal = page.locator('#passwordModal')
            is_visible = await modal.is_visible()
            print(f"모달이 보이는가: {is_visible}")
            
            if is_visible:
                print("성공! 모달이 표시되었습니다.")
                
                # 비밀번호 입력
                password_input = page.locator('#adminPassword')
                await password_input.fill('admin123')
                
                # 로그인 버튼 클릭
                login_btn = page.locator('#passwordModal button:has-text("로그인")')
                await login_btn.click()
                
                await page.wait_for_timeout(2000)
                
                # 관리자 버튼 확인
                admin_buttons = page.locator('.admin-mode-btn')
                button_count = await admin_buttons.count()
                print(f"관리자 버튼 개수: {button_count}")
                
                if button_count > 0:
                    print("관리자 모드 진입 성공!")
                else:
                    print("관리자 모드 진입 실패")
            else:
                print("실패! 모달이 표시되지 않았습니다.")
                
        except Exception as e:
            print(f"오류 발생: {e}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_simple_admin())


