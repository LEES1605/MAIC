# 자동 검증 시스템
"""
코드 수정 후 자동으로 검증하는 시스템
- 규칙 준수 확인
- 구조 검증
- 자동 수정 제안
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, List


class AutoValidator:
    """자동 검증 클래스"""
    
    def __init__(self):
        self.rules = {
            "app_py_no_ui": "app.py에는 UI 코드가 없어야 함",
            "src_ui_structure": "src/ui/ 디렉토리 구조 준수",
            "import_paths": "올바른 import 경로 사용",
            "component_isolation": "컴포넌트 격리 원칙"
        }
    
    def validate_before_edit(self, target_file: str) -> Dict[str, Any]:
        """수정 전 검증"""
        result = {
            "can_proceed": True,
            "warnings": [],
            "errors": []
        }
        
        # app.py 수정 시 UI 코드 추가 금지
        if "app.py" in target_file:
            result["errors"].append("❌ app.py에는 UI 코드를 추가할 수 없습니다")
            result["can_proceed"] = False
        
        # src/ui/ 디렉토리 외부에서 UI 코드 추가 금지
        if not target_file.startswith("src/ui/"):
            if any(keyword in target_file for keyword in ["ui", "component", "style"]):
                result["warnings"].append("⚠️ UI 관련 코드는 src/ui/ 디렉토리에 있어야 합니다")
        
        return result
    
    def validate_after_edit(self, target_file: str) -> Dict[str, Any]:
        """수정 후 검증"""
        result = {
            "valid": True,
            "issues": [],
            "suggestions": []
        }
        
        if not os.path.exists(target_file):
            result["issues"].append(f"파일이 존재하지 않음: {target_file}")
            result["valid"] = False
            return result
        
        with open(target_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # app.py UI 코드 검사
        if "app.py" in target_file:
            ui_indicators = [
                "st.markdown", "st.components", "st.button", 
                "st.text_input", "st.columns", "from src.ui"
            ]
            
            for indicator in ui_indicators:
                if indicator in content:
                    result["issues"].append(f"app.py에 UI 코드 발견: {indicator}")
                    result["valid"] = False
        
        # src/ui/ 파일 검사
        if target_file.startswith("src/ui/"):
            # 올바른 import 경로 확인
            if "from app import" in content:
                result["issues"].append("src/ui/ 파일에서 app.py import 금지")
                result["valid"] = False
        
        return result
    
    def suggest_fixes(self, issues: List[str]) -> List[str]:
        """수정 제안"""
        suggestions = []
        
        for issue in issues:
            if "app.py에 UI 코드 발견" in issue:
                suggestions.append("→ UI 코드를 src/ui/ 디렉토리로 이동하세요")
            elif "app.py import 금지" in issue:
                suggestions.append("→ 상대 import 경로를 사용하세요")
            elif "파일이 존재하지 않음" in issue:
                suggestions.append("→ 파일 경로를 확인하세요")
        
        return suggestions


def validate_edit(target_file: str, operation: str = "edit") -> Dict[str, Any]:
    """편집 검증 함수"""
    validator = AutoValidator()
    
    if operation == "before":
        return validator.validate_before_edit(target_file)
    elif operation == "after":
        return validator.validate_after_edit(target_file)
    
    return {"error": "Invalid operation"}


def print_validation_report(result: Dict[str, Any]) -> None:
    """검증 리포트 출력"""
    print("🔍 자동 검증 리포트")
    print("=" * 40)
    
    if result.get("can_proceed") is False:
        print("❌ 수정을 진행할 수 없습니다:")
        for error in result.get("errors", []):
            print(f"  {error}")
        return
    
    if result.get("valid") is False:
        print("❌ 검증 실패:")
        for issue in result.get("issues", []):
            print(f"  {issue}")
        
        if result.get("suggestions"):
            print("💡 수정 제안:")
            for suggestion in result.get("suggestions", []):
                print(f"  {suggestion}")
    else:
        print("✅ 검증 통과!")
    
    print("=" * 40)


