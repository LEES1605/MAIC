# 간단한 코드 검증 스크립트
import os
import re

def check_app_py():
    """app.py 파일 검사"""
    if not os.path.exists("app.py"):
        print("app.py 파일이 없습니다.")
        return
    
    with open("app.py", 'r', encoding='utf-8') as f:
        content = f.read()
    
    # UI 관련 코드 검사
    ui_patterns = [
        r'st\.markdown\s*\(\s*["\'].*<style>',
        r'st\.components\.v1\.',
        r'st\.button\s*\(',
        r'st\.text_input\s*\(',
        r'from.*ui.*import',
    ]
    
    violations = []
    for pattern in ui_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            violations.append(f"UI 코드 발견: {pattern} - {len(matches)}개 매치")
    
    if violations:
        print("ERROR: app.py 위반 사항:")
        for violation in violations:
            print(f"  - {violation}")
        print("SUGGESTION: UI 코드를 src/ui/ 디렉토리로 이동하세요")
    else:
        print("SUCCESS: app.py 검사 통과!")

def check_src_ui_structure():
    """src/ui/ 구조 검사"""
    required_files = [
        "src/ui/header_component.py",
        "src/ui/chat_panel.py",
        "src/ui/components/",
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        print("ERROR: 누락된 파일:")
        for file in missing_files:
            print(f"  - {file}")
    else:
        print("SUCCESS: src/ui/ 구조 검사 통과!")

if __name__ == "__main__":
    print("코드 검증 리포트")
    print("=" * 40)
    check_app_py()
    print()
    check_src_ui_structure()
    print("=" * 40)



