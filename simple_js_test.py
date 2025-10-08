#!/usr/bin/env python3
"""
간단한 JavaScript 테스트
"""

import asyncio
from playwright.async_api import async_playwright

async def test_js_loading():
    """JavaScript 로딩 테스트"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        page = await browser.new_page()
        
        try:
            print("페이지 로드 중...")
            await page.goto('http://localhost:8080/neumorphism_app.html')
            await page.wait_for_load_state('networkidle')
            
            # JavaScript 함수가 정의되어 있는지 확인
            print("JavaScript 함수 확인...")
            
            # adminLogin 함수 확인
            admin_login_exists = await page.evaluate('typeof adminLogin')
            print(f"adminLogin 함수 존재: {admin_login_exists}")
            
            # selectMode 함수 확인
            select_mode_exists = await page.evaluate('typeof selectMode')
            print(f"selectMode 함수 존재: {select_mode_exists}")
            
            # askQuestion 함수 확인
            ask_question_exists = await page.evaluate('typeof askQuestion')
            print(f"askQuestion 함수 존재: {ask_question_exists}")
            
            # 모든 전역 함수 확인
            all_functions = await page.evaluate('''
                () => {
                    const funcs = [];
                    for (let key in window) {
                        if (typeof window[key] === 'function' && !key.startsWith('_')) {
                            funcs.push(key);
                        }
                    }
                    return funcs.sort();
                }
            ''')
            print(f"전역 함수들: {all_functions[:20]}")  # 처음 20개만 출력
            
            # DOM 요소 확인
            print("\nDOM 요소 확인...")
            admin_btn = await page.evaluate('document.querySelector("button[title=\\"관리자 로그인\\"]")')
            print(f"관리자 버튼: {admin_btn is not None}")
            
            modal = await page.evaluate('document.getElementById("passwordModal")')
            print(f"모달 요소: {modal is not None}")
            
            # 직접 adminLogin 함수 호출
            print("\nadminLogin 함수 직접 호출...")
            try:
                await page.evaluate('adminLogin()')
                print("adminLogin 함수 호출 성공")
                
                # 모달 상태 확인
                modal_display = await page.evaluate('getComputedStyle(document.getElementById("passwordModal")).display')
                print(f"모달 display: {modal_display}")
                
            except Exception as e:
                print(f"adminLogin 함수 호출 실패: {e}")
            
        except Exception as e:
            print(f"오류 발생: {e}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_js_loading())



