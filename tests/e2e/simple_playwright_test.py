#!/usr/bin/env python3
"""
간단한 Playwright 테스트 - 단계별 버튼 클릭
"""

import asyncio
from playwright.async_api import async_playwright

async def simple_button_test():
    """간단한 버튼 테스트"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            print("앱 접속 중...")
            await page.goto("http://localhost:8501")
            await page.wait_for_load_state("networkidle")
            print("앱 로딩 완료")
            
            # 초기 스크린샷
            await page.screenshot(path="step1_initial.png")
            print("초기 상태 스크린샷 저장")
            
            # 관리자 모드 토글 찾기
            print("관리자 모드 토글 찾는 중...")
            checkboxes = page.locator('input[type="checkbox"]')
            checkbox_count = await checkboxes.count()
            print(f"체크박스 개수: {checkbox_count}")
            
            if checkbox_count > 0:
                first_checkbox = checkboxes.first
                is_checked = await first_checkbox.is_checked()
                print(f"첫 번째 체크박스 상태: {is_checked}")
                
                if not is_checked:
                    await first_checkbox.click()
                    print("관리자 모드 활성화")
                    await page.wait_for_timeout(2000)
                
                # 관리자 모드 후 스크린샷
                await page.screenshot(path="step2_admin_mode.png")
                print("관리자 모드 스크린샷 저장")
            
            # 인덱스 복원 버튼 찾기
            print("인덱스 복원 버튼 찾는 중...")
            restore_buttons = page.locator('button:has-text("인덱스 복원")')
            restore_count = await restore_buttons.count()
            print(f"인덱스 복원 버튼 개수: {restore_count}")
            
            if restore_count > 0:
                first_restore = restore_buttons.first
                await first_restore.click()
                print("인덱스 복원 버튼 클릭")
                
                # 복원 진행 대기
                print("복원 진행 중... (10초 대기)")
                await page.wait_for_timeout(10000)
                
                # 복원 후 스크린샷
                await page.screenshot(path="step3_after_restore.png")
                print("복원 후 스크린샷 저장")
            
            # 통계 버튼 찾기
            print("통계 버튼 찾는 중...")
            stats_buttons = page.locator('button:has-text("통계")')
            stats_count = await stats_buttons.count()
            print(f"통계 버튼 개수: {stats_count}")
            
            if stats_count > 0:
                first_stats = stats_buttons.first
                await first_stats.click()
                print("통계 버튼 클릭")
                await page.wait_for_timeout(2000)
            
            # 최종 스크린샷
            await page.screenshot(path="step4_final.png")
            print("최종 상태 스크린샷 저장")
            
            print("테스트 완료!")
            return True
            
        except Exception as e:
            print(f"오류: {e}")
            await page.screenshot(path="error.png")
            return False
            
        finally:
            await page.wait_for_timeout(2000)
            await browser.close()

if __name__ == "__main__":
    result = asyncio.run(simple_button_test())
    if result:
        print("테스트 성공")
    else:
        print("테스트 실패")

