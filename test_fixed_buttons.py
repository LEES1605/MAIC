#!/usr/bin/env python3
"""
버튼 수정 후 테스트
"""

import asyncio
from playwright.async_api import async_playwright

async def test_fixed_buttons():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            print("Neumorphism 앱 테스트 시작...")
            
            # 페이지 로드
            await page.goto("http://localhost:8080/neumorphism_app.html")
            await page.wait_for_load_state("networkidle")
            
            print("페이지 로드 완료")
            
            # JavaScript 함수들이 정의되어 있는지 확인
            functions = await page.evaluate("""
                () => {
                    return {
                        adminLogin: typeof adminLogin,
                        selectMode: typeof selectMode,
                        askQuestion: typeof askQuestion,
                        studentLogin: typeof studentLogin,
                        checkPassword: typeof checkPassword,
                        closeModal: typeof closeModal,
                        adminLogout: typeof adminLogout
                    };
                }
            """)
            
            print("JavaScript 함수 상태:")
            for func_name, func_type in functions.items():
                status = "OK" if func_type == "function" else "FAIL"
                print(f"  {status} {func_name}: {func_type}")
            
            # 관리자 로그인 버튼 클릭 테스트
            print("\n관리자 로그인 버튼 테스트...")
            admin_btn = page.locator('button[title="관리자 로그인"]')
            await admin_btn.click()
            
            # 모달이 나타나는지 확인
            modal = page.locator('#passwordModal')
            await modal.wait_for(state="visible", timeout=5000)
            print("관리자 로그인 모달 표시됨")
            
            # 비밀번호 입력
            password_input = page.locator('#adminPassword')
            await password_input.fill('admin123')
            
            # 로그인 버튼 클릭
            login_btn = page.locator('#modal-login-btn')
            await login_btn.click()
            
            # 관리자 모드로 전환되는지 확인
            await page.wait_for_timeout(1000)
            status_text = page.locator('.status-text')
            status_content = await status_text.text_content()
            print(f"상태 텍스트: {status_content}")
            
            # 모달 닫기
            cancel_btn = page.locator('#modal-cancel-btn')
            await cancel_btn.click()
            await modal.wait_for(state="hidden", timeout=3000)
            print("모달 닫기 성공")
            
            # 모드 선택 버튼 테스트
            print("\n모드 선택 버튼 테스트...")
            grammar_btn = page.locator('button:has-text("문법 학습")')
            await grammar_btn.click()
            
            # active 클래스가 추가되는지 확인
            is_active = await grammar_btn.evaluate("el => el.classList.contains('active')")
            print(f"문법 학습 버튼 활성화: {is_active}")
            
            # 질문하기 버튼 테스트
            print("\n질문하기 버튼 테스트...")
            question_input = page.locator('#question-input')
            await question_input.fill('테스트 질문입니다')
            
            ask_btn = page.locator('.ask-button')
            await ask_btn.click()
            
            # 응답이 나타나는지 확인
            await page.wait_for_timeout(1000)
            response_area = page.locator('#response-area')
            response_content = await response_area.text_content()
            print(f"응답 영역 내용: {response_content[:100]}...")
            
            print("\n모든 테스트 완료!")
            
        except Exception as e:
            print(f"테스트 실패: {e}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_fixed_buttons())
