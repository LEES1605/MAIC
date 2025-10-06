#!/usr/bin/env python3
"""자동 테스트 실행기 - 사용자 요청 없이 자동으로 테스트 실행 및 결과 보고"""

import subprocess
import sys
import time
from pathlib import Path

def run_command(command, description):
    """명령어 실행 및 결과 반환"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, encoding='utf-8')
        return {
            "success": result.returncode == 0,
            "description": description,
            "output": result.stdout.strip(),
            "error": result.stderr.strip() if result.stderr else None
        }
    except Exception as e:
        return {
            "success": False,
            "description": description,
            "output": "",
            "error": str(e)
        }

def check_git_status():
    """Git 상태 확인"""
    return run_command("git status", "Git 상태 확인")

def test_imports():
    """Import 테스트"""
    try:
        from src.ui.ops.indexing_panel import render_admin_indexing_panel
        from src.ui.header import render
        return {
            "success": True,
            "description": "Import 테스트",
            "output": "모든 모듈 정상 import",
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "description": "Import 테스트",
            "output": "",
            "error": str(e)
        }

def test_syntax():
    """문법 테스트"""
    files = ["src/ui/ops/indexing_panel.py", "src/ui/header.py", "app.py"]
    results = []
    
    for file in files:
        if Path(file).exists():
            result = run_command(f"python -m py_compile {file}", f"{file} 문법 검사")
            results.append(result)
    
    return results

def check_streamlit_app():
    """Streamlit 앱 실행 상태 확인"""
    return run_command("netstat -an | findstr :8501", "Streamlit 앱 실행 상태")

def run_playwright_test():
    """Playwright 테스트 실행"""
    return run_command("python tests/e2e/simple_playwright_test.py", "Playwright 앱 실행 테스트")

def generate_test_report():
    """테스트 결과 보고서 생성"""
    print("[INFO] 자동 테스트 실행 시작")
    print("=" * 50)
    
    # 1. Git 상태 확인
    git_result = check_git_status()
    print(f"[TEST] {git_result['description']}: {'[OK] 통과' if git_result['success'] else '[ERROR] 실패'}")
    if git_result['error']:
        print(f"   오류: {git_result['error']}")
    
    # 2. Import 테스트
    import_result = test_imports()
    print(f"[TEST] {import_result['description']}: {'[OK] 통과' if import_result['success'] else '[ERROR] 실패'}")
    if import_result['error']:
        print(f"   오류: {import_result['error']}")
    
    # 3. 문법 테스트
    syntax_results = test_syntax()
    print(f"[TEST] 문법 검사:")
    for result in syntax_results:
        print(f"   {result['description']}: {'[OK] 통과' if result['success'] else '[ERROR] 실패'}")
        if result['error']:
            print(f"     오류: {result['error']}")
    
    # 4. Streamlit 앱 상태 확인
    app_result = check_streamlit_app()
    print(f"[TEST] {app_result['description']}: {'[OK] 실행 중' if app_result['success'] else '[ERROR] 실행 안됨'}")
    if app_result['output']:
        print(f"   상태: {app_result['output']}")
    
    # 5. Playwright 테스트
    playwright_result = run_playwright_test()
    print(f"[TEST] {playwright_result['description']}: {'[OK] 성공' if playwright_result['success'] else '[ERROR] 실패'}")
    if playwright_result['output']:
        print(f"   결과: {playwright_result['output']}")
    if playwright_result['error']:
        print(f"   오류: {playwright_result['error']}")
    
    print("=" * 50)
    
    # 전체 결과 요약
    all_tests = [git_result, import_result] + syntax_results + [app_result, playwright_result]
    passed = sum(1 for test in all_tests if test['success'])
    total = len(all_tests)
    
    print(f"[SUMMARY] 테스트 결과 요약: {passed}/{total} 통과")
    
    if passed == total:
        print("[SUCCESS] 모든 테스트 통과! 온라인 배포 준비 완료")
        return True
    else:
        print("[WARNING] 일부 테스트 실패. 문제 해결 필요")
        return False

if __name__ == "__main__":
    success = generate_test_report()
    sys.exit(0 if success else 1)
