# 코드 가드 시스템
"""
개발자의 반복적인 실수를 방지하는 가드 시스템
- 규칙 위반 감지
- 구조 검증
- 자동 수정 제안
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Any


class CodeGuard:
    """코드 가드 클래스"""
    
    def __init__(self):
        self.violations = []
        self.suggestions = []
    
    def check_app_py_violations(self, file_path: str = "app.py") -> List[str]:
        """app.py 파일의 UI 코드 위반 검사"""
        violations = []
        
        if not os.path.exists(file_path):
            return violations
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # UI 관련 코드 패턴 검사
        ui_patterns = [
            r'st\.markdown\s*\(\s*["\'].*<style>',
            r'st\.components\.v1\.',
            r'st\.button\s*\(',
            r'st\.text_input\s*\(',
            r'st\.selectbox\s*\(',
            r'st\.columns\s*\(',
            r'from.*ui.*import',
            r'import.*ui',
        ]
        
        for pattern in ui_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                violations.append(f"UI 코드 발견: {pattern} - {len(matches)}개 매치")
        
        return violations
    
    def check_src_ui_structure(self) -> Dict[str, Any]:
        """src/ui/ 디렉토리 구조 검증"""
        structure = {
            "valid": True,
            "missing_files": [],
            "incorrect_imports": [],
            "suggestions": []
        }
        
        required_files = [
            "src/ui/header_component.py",
            "src/ui/chat_panel.py",
            "src/ui/components/",
        ]
        
        for file_path in required_files:
            if not os.path.exists(file_path):
                structure["missing_files"].append(file_path)
                structure["valid"] = False
        
        return structure
    
    def suggest_fixes(self, violations: List[str]) -> List[str]:
        """위반 사항에 대한 수정 제안"""
        suggestions = []
        
        for violation in violations:
            if "UI 코드 발견" in violation:
                suggestions.append("ERROR: app.py에서 UI 코드를 제거하고 src/ui/ 디렉토리로 이동하세요")
            elif "missing_files" in violation:
                suggestions.append("ERROR: 누락된 파일을 생성하거나 올바른 경로로 이동하세요")
        
        return suggestions
    
    def auto_fix_app_py(self, file_path: str = "app.py") -> bool:
        """app.py 파일 자동 수정"""
        if not os.path.exists(file_path):
            return False
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # UI 관련 코드 제거
        ui_removal_patterns = [
            r'# 메인 앱 컴포넌트 사용.*?_render_body\(\)',
            r'from src\.ui\.components\.main_app import.*?\n',
            r'render_main_app\(\)',
        ]
        
        original_content = content
        for pattern in ui_removal_patterns:
            content = re.sub(pattern, '_render_body()', content, flags=re.DOTALL)
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
    
    def validate_ui_imports(self, file_path: str) -> List[str]:
        """UI 관련 import 검증"""
        violations = []
        
        if not os.path.exists(file_path):
            return violations
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # app.py에서 UI import 금지
        if "app.py" in file_path:
            ui_imports = re.findall(r'from src\.ui\..*import|import.*ui', content)
            if ui_imports:
                violations.append(f"app.py에서 UI import 금지: {ui_imports}")
        
        return violations
    
    def run_full_check(self) -> Dict[str, Any]:
        """전체 검사 실행"""
        result = {
            "app_py_violations": self.check_app_py_violations(),
            "src_ui_structure": self.check_src_ui_structure(),
            "suggestions": [],
            "auto_fixes": []
        }
        
        # 수정 제안 생성
        if result["app_py_violations"]:
            result["suggestions"].extend(self.suggest_fixes(result["app_py_violations"]))
        
        # 자동 수정 실행
        if result["app_py_violations"]:
            if self.auto_fix_app_py():
                result["auto_fixes"].append("app.py에서 UI 코드 자동 제거 완료")
        
        return result


def run_code_guard() -> Dict[str, Any]:
    """코드 가드 실행 함수"""
    guard = CodeGuard()
    return guard.run_full_check()


def print_guard_report(result: Dict[str, Any]) -> None:
    """가드 리포트 출력"""
    print("코드 가드 리포트")
    print("=" * 50)
    
    if result["app_py_violations"]:
        print("ERROR: app.py 위반 사항:")
        for violation in result["app_py_violations"]:
            print(f"  - {violation}")
    
    if result["src_ui_structure"]["missing_files"]:
        print("ERROR: 누락된 파일:")
        for file in result["src_ui_structure"]["missing_files"]:
            print(f"  - {file}")
    
    if result["suggestions"]:
        print("SUGGESTION: 수정 제안:")
        for suggestion in result["suggestions"]:
            print(f"  - {suggestion}")
    
    if result["auto_fixes"]:
        print("SUCCESS: 자동 수정 완료:")
        for fix in result["auto_fixes"]:
            print(f"  - {fix}")
    
    if not result["app_py_violations"] and result["src_ui_structure"]["valid"]:
        print("SUCCESS: 모든 검사 통과!")
    
    print("=" * 50)
