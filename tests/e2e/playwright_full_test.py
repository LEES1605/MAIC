#!/usr/bin/env python3
"""
Playwright를 이용한 전체 UI 자동 테스트
모든 버튼을 직접 클릭하여 기능 검증
"""

import asyncio
import time
from playwright.async_api import async_playwright

async def test_all_buttons():
    """모든 버튼을 순차적으로 테스트"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # 브라우저 창 표시
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            print("[INFO] Streamlit 앱 접속 중...")
            await page.goto("http://localhost:8501")
            await page.wait_for_load_state("networkidle")
            print("[OK] 앱 로딩 완료")
            
            # 스크린샷 저장
            await page.screenshot(path="test_initial_state.png")
            print("[SCREENSHOT] 초기 상태 저장: test_initial_state.png")
            
            # 1. 관리자 모드 토글 찾기 및 활성화
            print("[TEST 1] 관리자 모드 토글 테스트")
            admin_toggle = page.locator('input[type="checkbox"]').first()
            
            if await admin_toggle.count() > 0:
                is_checked = await admin_toggle.is_checked()
                if not is_checked:
                    await admin_toggle.click()
                    print("[OK] 관리자 모드 활성화")
                    await page.wait_for_timeout(2000)
                else:
                    print("[INFO] 관리자 모드가 이미 활성화됨")
                
                # 관리자 모드 활성화 후 스크린샷
                await page.screenshot(path="test_admin_mode.png")
                print("[SCREENSHOT] 관리자 모드 상태 저장: test_admin_mode.png")
            else:
                print("[ERROR] 관리자 모드 토글을 찾을 수 없습니다")
                return False
            
            # 2. 디버그 패널 버튼들 테스트
            print("[TEST 2] 디버그 패널 버튼들 테스트")
            
            debug_buttons = [
                "복원 테스트",
                "상태 확인", 
                "GitHub 릴리스 확인",
                "SequentialReleaseManager 테스트",
                "수동 복원 테스트",
                "인덱싱 상태 확인",
                "인덱싱 상태 초기화",
                "새 파일 스캔 테스트"
            ]
            
            for button_text in debug_buttons:
                try:
                    print(f"[CLICK] {button_text} 버튼 클릭")
                    button = page.locator(f'button:has-text("{button_text}")')
                    
                    if await button.count() > 0 and await button.is_visible():
                        await button.click()
                        await page.wait_for_timeout(1000)  # 1초 대기
                        print(f"[OK] {button_text} 버튼 클릭 완료")
                    else:
                        print(f"[WARN] {button_text} 버튼을 찾을 수 없습니다")
                except Exception as e:
                    print(f"[ERROR] {button_text} 버튼 클릭 실패: {e}")
            
            # 3. 인덱스 복원 버튼 테스트
            print("[TEST 3] 인덱스 복원 버튼 테스트")
            restore_button = page.locator('button:has-text("인덱스 복원")')
            
            if await restore_button.count() > 0 and await restore_button.is_visible():
                print("[CLICK] 인덱스 복원 버튼 클릭")
                await restore_button.click()
                
                # 복원 진행 대기 (30초)
                print("[WAIT] 복원 진행 중... (30초 대기)")
                await page.wait_for_timeout(30000)
                
                # 복원 후 스크린샷
                await page.screenshot(path="test_after_restore.png")
                print("[SCREENSHOT] 복원 후 상태 저장: test_after_restore.png")
                
                # 성공/실패 메시지 확인
                success_msg = page.locator('text=인덱스 복원이 완료되었습니다!')
                error_msg = page.locator('text=복원 실패')
                
                if await success_msg.count() > 0:
                    print("[SUCCESS] 인덱스 복원 성공 메시지 확인됨")
                elif await error_msg.count() > 0:
                    error_text = await error_msg.text_content()
                    print(f"[ERROR] 인덱스 복원 실패: {error_text}")
                else:
                    print("[WARN] 복원 결과 메시지를 찾을 수 없습니다")
            else:
                print("[ERROR] 인덱스 복원 버튼을 찾을 수 없습니다")
            
            # 4. 다른 관리 도구 버튼들 테스트
            print("[TEST 4] 기타 관리 도구 버튼들 테스트")
            
            other_buttons = [
                "통계",
                "인덱싱", 
                "업로드"
            ]
            
            for button_text in other_buttons:
                try:
                    print(f"[CLICK] {button_text} 버튼 클릭")
                    button = page.locator(f'button:has-text("{button_text}")')
                    
                    if await button.count() > 0 and await button.is_visible():
                        await button.click()
                        await page.wait_for_timeout(2000)  # 2초 대기
                        print(f"[OK] {button_text} 버튼 클릭 완료")
                    else:
                        print(f"[WARN] {button_text} 버튼을 찾을 수 없습니다")
                except Exception as e:
                    print(f"[ERROR] {button_text} 버튼 클릭 실패: {e}")
            
            # 5. 최종 상태 확인
            print("[TEST 5] 최종 상태 확인")
            await page.screenshot(path="test_final_state.png")
            print("[SCREENSHOT] 최종 상태 저장: test_final_state.png")
            
            # 인덱스 상태 확인
            status_elements = page.locator('text=복원필요, text=준비완료, text=로컬사용')
            if await status_elements.count() > 0:
                status_text = await status_elements.first.text_content()
                print(f"[STATUS] 현재 인덱스 상태: {status_text}")
            else:
                print("[WARN] 인덱스 상태를 찾을 수 없습니다")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] 테스트 중 오류 발생: {e}")
            await page.screenshot(path="test_error.png")
            return False
            
        finally:
            # 브라우저 종료 전 잠시 대기
            await page.wait_for_timeout(3000)
            await browser.close()

async def main():
    """메인 테스트 함수"""
    print("[START] Playwright 전체 UI 자동 테스트 시작")
    print("=" * 60)
    
    result = await test_all_buttons()
    
    print("=" * 60)
    if result:
        print("[SUCCESS] 모든 테스트가 완료되었습니다!")
        print("[INFO] 스크린샷 파일들을 확인하여 결과를 검토하세요:")
        print("  - test_initial_state.png: 초기 상태")
        print("  - test_admin_mode.png: 관리자 모드 활성화 후")
        print("  - test_after_restore.png: 복원 후 상태")
        print("  - test_final_state.png: 최종 상태")
    else:
        print("[FAILED] 테스트 중 오류가 발생했습니다.")
        print("[INFO] test_error.png 파일을 확인하세요.")
    
    return result

if __name__ == "__main__":
    asyncio.run(main())
