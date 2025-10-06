#!/usr/bin/env python3
"""
자동 테스트 리포터

코드 수정 후 자동으로 다음 테스트들을 실행하고 결과를 보고합니다:
1. 문법 검사
2. 모듈 임포트 테스트
3. Playwright 테스트
4. HTTP 연결 테스트
"""

import subprocess
import sys
import time
from datetime import datetime


def run_test(test_name, command, description=""):
    """테스트를 실행하고 결과를 반환합니다."""
    print(f"\n[TEST] {test_name} 실행 중...")
    if description:
        print(f"   {description}")
    
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            errors='ignore'
        )
        
        if result.returncode == 0:
            print(f"   [OK] {test_name}: 성공")
            return True, result.stdout
        else:
            print(f"   [ERROR] {test_name}: 실패")
            print(f"   오류: {result.stderr}")
            return False, result.stderr
            
    except Exception as e:
        print(f"   [ERROR] {test_name}: 예외 발생")
        print(f"   오류: {str(e)}")
        return False, str(e)


def main():
    """메인 테스트 실행 함수"""
    print("=" * 60)
    print(f"[AUTO] 자동 테스트 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    test_results = []
    
    # 1. 문법 검사
    success, output = run_test(
        "문법 검사", 
        'python -c "import ast; ast.parse(open(\'app.py\', encoding=\'utf-8\').read()); print(\'app.py syntax OK\')"',
        "app.py 파일의 Python 구문 검사"
    )
    test_results.append(("문법 검사", success))
    
    # 2. UI 스타일 모듈 임포트 테스트
    success, output = run_test(
        "UI 스타일 모듈 임포트", 
        'python -c "from src.ui.styles import inject_base_styles, inject_chat_styles, inject_responsive_styles; print(\'UI style modules imported successfully\')"',
        "새로운 UI 스타일 모듈들의 임포트 테스트"
    )
    test_results.append(("UI 스타일 모듈", success))
    
    # 3. Playwright 테스트
    success, output = run_test(
        "Playwright 관리자 로그인 테스트", 
        "python test_admin_login_fixed.py",
        "관리자 로그인 기능의 E2E 테스트"
    )
    test_results.append(("Playwright 테스트", success))
    
    # 4. HTTP 연결 테스트
    success, output = run_test(
        "HTTP 연결 테스트", 
        "python simple_test.py",
        "Streamlit 앱의 HTTP 연결 및 응답 테스트"
    )
    test_results.append(("HTTP 연결 테스트", success))
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("[SUMMARY] 테스트 결과 요약")
    print("=" * 60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, success in test_results:
        status = "[OK] 성공" if success else "[ERROR] 실패"
        print(f"   {test_name}: {status}")
        if success:
            passed += 1
    
    print(f"\n[RESULT] 전체 결과: {passed}/{total} 테스트 통과")
    
    if passed == total:
        print("[SUCCESS] 모든 테스트가 성공했습니다!")
        return 0
    else:
        print("[WARNING] 일부 테스트가 실패했습니다. 확인이 필요합니다.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
