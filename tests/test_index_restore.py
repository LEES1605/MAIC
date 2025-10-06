#!/usr/bin/env python3
"""
Playwright를 이용한 인덱스 복원 기능 자동 테스트
"""

import asyncio
import time
from playwright.async_api import async_playwright

async def test_index_restore():
    """인덱스 복원 기능 테스트"""
    
    async with async_playwright() as p:
        # 브라우저 실행
        browser = await p.chromium.launch(headless=False)  # headless=False로 설정하여 브라우저 창 표시
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            print("[INFO] Streamlit 앱 접속 중...")
            await page.goto("http://localhost:8501")
            
            # 페이지 로딩 대기
            await page.wait_for_load_state("networkidle")
            print("[OK] 앱 로딩 완료")
            
            # 관리자 모드 토글 찾기
            print("[SEARCH] 관리자 모드 토글 찾는 중...")
            admin_toggle = page.locator('input[type="checkbox"]').first()
            
            if await admin_toggle.count() > 0 and await admin_toggle.is_visible():
                print("[OK] 관리자 모드 토글 발견")
                
                # 관리자 모드 활성화
                if not await admin_toggle.is_checked():
                    await admin_toggle.click()
                    print("[OK] 관리자 모드 활성화")
                    await page.wait_for_timeout(1000)  # 1초 대기
                else:
                    print("[INFO] 관리자 모드가 이미 활성화됨")
                
                # 관리 도구 섹션 찾기
                print("[SEARCH] 관리 도구 섹션 찾는 중...")
                await page.wait_for_selector('text=관리 도구', timeout=10000)
                print("[OK] 관리 도구 섹션 발견")
                
                # 인덱스 복원 버튼 찾기
                print("[SEARCH] 인덱스 복원 버튼 찾는 중...")
                restore_button = page.locator('button:has-text("인덱스 복원")')
                
                if await restore_button.count() > 0 and await restore_button.is_visible():
                    print("[OK] 인덱스 복원 버튼 발견")
                    
                    # 버튼 클릭
                    print("[CLICK] 인덱스 복원 버튼 클릭...")
                    await restore_button.click()
                    
                    # 스피너 또는 성공 메시지 대기
                    print("[WAIT] 복원 진행 중...")
                    
                    # 성공 메시지 또는 오류 메시지 대기
                    try:
                        success_message = page.locator('text=인덱스 복원이 완료되었습니다!')
                        error_message = page.locator('text=복원 실패')
                        
                        # 30초 동안 성공 또는 오류 메시지 대기
                        await page.wait_for_function(
                            lambda: success_message.is_visible() or error_message.is_visible(),
                            timeout=30000
                        )
                        
                        if await success_message.is_visible():
                            print("[SUCCESS] 인덱스 복원 성공!")
                            return True
                        elif await error_message.is_visible():
                            error_text = await error_message.text_content()
                            print(f"[ERROR] 인덱스 복원 실패: {error_text}")
                            return False
                            
                    except Exception as e:
                        print(f"[WARN] 메시지 대기 중 오류: {e}")
                        # 스크린샷 저장
                        await page.screenshot(path="test_index_restore_error.png")
                        print("[SCREENSHOT] 오류 스크린샷 저장: test_index_restore_error.png")
                        return False
                        
                else:
                    print("[ERROR] 인덱스 복원 버튼을 찾을 수 없습니다")
                    await page.screenshot(path="test_no_restore_button.png")
                    return False
                    
            else:
                print("[ERROR] 관리자 모드 토글을 찾을 수 없습니다")
                await page.screenshot(path="test_no_admin_toggle.png")
                return False
                
        except Exception as e:
            print(f"[ERROR] 테스트 중 오류 발생: {e}")
            await page.screenshot(path="test_error.png")
            return False
            
        finally:
            # 브라우저 종료 전 잠시 대기
            await page.wait_for_timeout(2000)
            await browser.close()

async def main():
    """메인 테스트 함수"""
    print("[START] Playwright 인덱스 복원 테스트 시작")
    print("=" * 50)
    
    # Streamlit 앱이 실행 중인지 확인
    print("[CHECK] Streamlit 앱 상태 확인 중...")
    
    result = await test_index_restore()
    
    print("=" * 50)
    if result:
        print("[SUCCESS] 테스트 성공: 인덱스 복원이 정상적으로 작동합니다!")
    else:
        print("[FAILED] 테스트 실패: 인덱스 복원에 문제가 있습니다.")
    
    return result

if __name__ == "__main__":
    asyncio.run(main())
