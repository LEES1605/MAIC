#!/usr/bin/env python3
"""
특정 텍스트를 검색하는 Playwright 테스트
"""

import asyncio
from playwright.async_api import async_playwright

async def search_text_test():
    """특정 텍스트 검색 테스트"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            print("앱 접속 중...")
            await page.goto("http://localhost:8504")
            await page.wait_for_timeout(10000)
            await page.wait_for_load_state("networkidle")
            print("앱 로딩 완료")
            
            # 특정 텍스트들 검색
            search_texts = [
                "관리자",
                "인덱스",
                "복원",
                "오케스트레이터",
                "관리 도구",
                "시스템 상태"
            ]
            
            for text in search_texts:
                elements = page.locator(f'text={text}')
                count = await elements.count()
                print(f"'{text}' 텍스트 개수: {count}")
                
                if count > 0:
                    for i in range(min(count, 3)):
                        try:
                            element_text = await elements.nth(i).text_content()
                            print(f"  - {i}: '{element_text}'")
                        except:
                            print(f"  - {i}: 텍스트 읽기 실패")
            
            # 페이지 전체 텍스트 가져오기
            page_text = await page.text_content('body')
            print(f"페이지 전체 텍스트 길이: {len(page_text)}")
            
            # 인덱스 관련 텍스트가 있는지 확인
            if "인덱스" in page_text:
                print("✅ '인덱스' 텍스트 발견!")
            else:
                print("❌ '인덱스' 텍스트 없음")
            
            if "복원" in page_text:
                print("✅ '복원' 텍스트 발견!")
            else:
                print("❌ '복원' 텍스트 없음")
            
            # 스크린샷 저장
            await page.screenshot(path="search_test.png")
            print("스크린샷 저장: search_test.png")
            
            return True
            
        except Exception as e:
            print(f"오류: {e}")
            await page.screenshot(path="search_error.png")
            return False
            
        finally:
            await page.wait_for_timeout(3000)
            await browser.close()

if __name__ == "__main__":
    result = asyncio.run(search_text_test())
    if result:
        print("검색 테스트 완료")
    else:
        print("검색 테스트 실패")


