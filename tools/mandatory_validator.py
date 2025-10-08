"""
🚨 강제적 규칙 검증 시스템
AI가 무시할 수 없는 강제적 규칙 적용 메커니즘
"""

import re
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import hashlib

class MandatoryValidator:
    """AI가 무시할 수 없는 강제적 규칙 검증기"""
    
    def __init__(self):
        self.rules_file = Path("docs/AI_RULES.md")
        self.critical_rules = self._load_critical_rules()
        self.blocking = True  # 규칙 위반 시 실행 차단
    
    def _load_critical_rules(self) -> Dict:
        """중요한 규칙들 로드"""
        return {
            "port_usage": {
                "allowed_ports": [8501],
                "forbidden_patterns": [
                    r"--server\.port\s+\d+",
                    r"port\s*=\s*[0-9]+",
                    r"localhost:[0-9]+"
                ],
                "required_patterns": [
                    r"streamlit run app\.py(?!\s+--server\.port)"
                ]
            },
            "file_creation": {
                "forbidden_locations": ["."],  # 루트 디렉토리
                "allowed_locations": ["src/", "docs/", "tools/", "tests/"],
                "forbidden_patterns": [
                    r"test_.*\.py",
                    r"simple_.*\.py", 
                    r".*_neumorphism\.py",
                    r".*_test\.py"
                ]
            },
            "ui_enforcement": {
                "canonical_html": "src/ui/neumorphism_app.html",
                "forbidden_html": [
                    "static/maic_app.html",
                    "legacy/maic_neumorphism_app.html",
                ],
            },
            "app_fingerprint": {
                "path": "app.py",
                # 현재 승인된 최소 엔트리 템플릿 해시(실시간 계산값)
                "sha256": "f8abe5207fff0c1a1e8d3147890bd792a990cd4079cfb56db30ea68b4c75b4a2",
            },
        }
    
    def validate_streamlit_command(self, command: str) -> Dict:
        """Streamlit 명령어 강제 검증"""
        if not command or "streamlit run" not in command:
            return {"valid": True, "action": None}
        
        # 포트 지정 확인
        port_patterns = self.critical_rules["port_usage"]["forbidden_patterns"]
        for pattern in port_patterns:
            if re.search(pattern, command):
                return {
                    "valid": False,
                    "error": "[RULE VIOLATION] 포트 지정 금지",
                    "suggestion": "streamlit run app.py",
                    "rule": "포트 8501만 사용 가능",
                    "blocking": True
                }
        
        # 올바른 패턴 확인
        required_patterns = self.critical_rules["port_usage"]["required_patterns"]
        for pattern in required_patterns:
            if re.search(pattern, command):
                return {
                    "valid": True,
                    "action": "[OK] 포트 규칙 준수",
                    "suggestion": "사용자에게 http://localhost:8501 안내"
                }
        
        return {
            "valid": False,
            "error": "[RULE VIOLATION] 올바르지 않은 명령어",
            "suggestion": "streamlit run app.py",
            "rule": "기본 포트 8501 사용 필수",
            "blocking": True
        }
    
    def validate_file_creation(self, file_path: str) -> Dict:
        """파일 생성 강제 검증"""
        path = Path(file_path)
        
        # 루트 디렉토리 확인
        if path.parent == Path("."):
            forbidden_patterns = self.critical_rules["file_creation"]["forbidden_patterns"]
            for pattern in forbidden_patterns:
                if re.search(pattern, path.name):
                    return {
                        "valid": False,
                        "error": f"[RULE VIOLATION] 루트에 {path.name} 생성 금지",
                        "suggestion": f"src/{path.name} 또는 적절한 디렉토리에 생성",
                        "rule": "루트에 파일 생성 금지",
                        "blocking": True
                    }
        
        return {"valid": True, "action": "✅ 파일 생성 규칙 준수"}
    
    def validate_before_execution(self, action_type: str, details: str) -> Dict:
        """실행 전 강제 검증"""
        if action_type == "streamlit_run":
            return self.validate_streamlit_command(details)
        elif action_type == "file_creation":
            return self.validate_file_creation(details)
        elif action_type == "file_modification":
            return self._validate_file_modification(details)
        elif action_type == "ui_render_path":
            return self._validate_ui_render_path(details)
        
        return {"valid": True, "action": "✅ 일반 작업"}
    
    def _validate_file_modification(self, file_path: str) -> Dict:
        """파일 수정 강제 검증"""
        if file_path == "app.py":
            # app.py 템플릿 해시 검증
            rule = self.critical_rules.get("app_fingerprint", {})
            expected = rule.get("sha256")
            path = Path(rule.get("path", "app.py"))
            if expected and path.exists():
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
                if actual != expected:
                    return {
                        "valid": False,
                        "error": "[RULE VIOLATION] app.py 템플릿 위반(허용된 최소 엔트리와 불일치)",
                        "suggestion": "app.py를 승인된 최소 엔트리 템플릿으로 되돌리세요",
                        "blocking": True,
                    }
            # 통과 시에도 경고로 단순 엔트리 유지 안내
            return {
                "valid": True,
                "warning": "[WARNING] app.py는 최소 엔트리만 허용됩니다",
                "suggestion": "실제 로직/렌더러는 src/ 디렉토리에서 호출"
            }

        return {"valid": True, "action": "[OK] 파일 수정 허용"}

    def _validate_ui_render_path(self, render_path: str) -> Dict:
        """UI 렌더 경로 강제 검증"""
        ui = self.critical_rules.get("ui_enforcement", {})
        canonical = ui.get("canonical_html")
        forbidden = set(ui.get("forbidden_html", []))
        if render_path and render_path.replace("\\", "/") != canonical:
            return {
                "valid": False,
                "error": "[RULE VIOLATION] 정본 UI 외 렌더 금지",
                "suggestion": f"렌더 경로를 '{canonical}'로 고정",
                "blocking": True,
            }
        if render_path in forbidden:
            return {
                "valid": False,
                "error": "[RULE VIOLATION] 금지된 UI 경로입니다",
                "suggestion": f"렌더 경로를 '{canonical}'로 변경",
                "blocking": True,
            }
        
        return {"valid": True, "action": "[OK] 정본 UI 렌더 승인"}
    
    def get_validation_summary(self) -> str:
        """검증 규칙 요약"""
        return """
[CRITICAL] 강제적 규칙 검증 시스템 활성화

필수 규칙:
1. 포트 사용: 8501만 허용 (--server.port 옵션 금지)
2. 파일 생성: 루트 디렉토리 금지
3. 명명 규칙: test_*, simple_*, *_neumorphism.py 금지

[WARNING] 규칙 위반 시 실행 차단됨
[OK] 모든 작업은 규칙 준수 후 실행
        """

class RuleViolationError(Exception):
    """규칙 위반 시 발생하는 예외"""
    def __init__(self, message: str, suggestion: str = ""):
        self.message = message
        self.suggestion = suggestion
        super().__init__(f"{message}\n{suggestion}")

def enforce_mandatory_validation(action_type: str, details: str) -> Dict:
    """강제적 검증 실행"""
    validator = MandatoryValidator()
    result = validator.validate_before_execution(action_type, details)
    
    if not result.get("valid", True) and result.get("blocking", False):
        raise RuleViolationError(
            result.get("error", "규칙 위반"),
            result.get("suggestion", "")
        )
    
    return result

if __name__ == "__main__":
    # 테스트
    validator = MandatoryValidator()
    
    # 테스트 케이스들
    test_cases = [
        ("streamlit run app.py", "streamlit_run"),
        ("streamlit run app.py --server.port 8520", "streamlit_run"),
        ("streamlit run app.py --server.port 8501", "streamlit_run"),
        ("test_new_file.py", "file_creation"),
        ("src/new_file.py", "file_creation"),
    ]
    
    print(validator.get_validation_summary())
    print("\n[TEST] 테스트 실행:")
    
    for command, action_type in test_cases:
        try:
            result = validator.validate_before_execution(action_type, command)
            status = "[OK] 통과" if result.get("valid", True) else "[FAIL] 실패"
            print(f"{status}: {command}")
            if not result.get("valid", True):
                print(f"   오류: {result.get('error', '')}")
                print(f"   제안: {result.get('suggestion', '')}")
        except RuleViolationError as e:
            print(f"[BLOCK] 차단: {command}")
            print(f"   오류: {e.message}")
            print(f"   제안: {e.suggestion}")
