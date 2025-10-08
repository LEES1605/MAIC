"""
🤖 AI 행동 패턴 강제 변경 시스템
AI가 코드 생성 전에 반드시 규칙을 검증하도록 강제하는 시스템
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
from mandatory_validator import MandatoryValidator, RuleViolationError

class AIBehaviorEnforcer:
    """AI 행동 패턴을 강제로 변경하는 시스템"""
    
    def __init__(self):
        self.validator = MandatoryValidator()
        self.rules_file = Path("docs/AI_RULES.md")
        self.enforcement_active = True
        
    def pre_execution_hook(self, action_type: str, details: str) -> Dict:
        """실행 전 훅 - AI가 무시할 수 없는 검증"""
        if not self.enforcement_active:
            return {"valid": True, "action": "검증 비활성화"}
        
        print("🔍 강제적 규칙 검증 시작...")
        
        try:
            # 1. 규칙 파일 존재 확인
            if not self.rules_file.exists():
                raise RuleViolationError(
                    "🚨 규칙 파일 없음",
                    "docs/AI_RULES.md 파일이 존재하지 않습니다"
                )
            
            # 2. 강제적 검증 실행
            result = self.validator.validate_before_execution(action_type, details)
            
            if not result.get("valid", True):
                if result.get("blocking", False):
                    # 차단적 오류
                    raise RuleViolationError(
                        result.get("error", "규칙 위반"),
                        result.get("suggestion", "")
                    )
                else:
                    # 경고
                    print(f"⚠️ 경고: {result.get('error', '')}")
                    print(f"💡 제안: {result.get('suggestion', '')}")
            
            print("✅ 규칙 검증 통과")
            return result
            
        except RuleViolationError as e:
            print(f"🚨 규칙 위반으로 실행 차단:")
            print(f"   오류: {e.message}")
            print(f"   제안: {e.suggestion}")
            print("\n📋 해결 방법:")
            print("1. docs/AI_RULES.md를 읽고 규칙을 확인하세요")
            print("2. 제안된 수정 사항을 적용하세요")
            print("3. 다시 시도하세요")
            raise
    
    def enforce_port_rule(self, command: str) -> str:
        """포트 규칙 강제 적용"""
        if "streamlit run" in command:
            # 포트 지정 제거
            import re
            cleaned_command = re.sub(r'\s+--server\.port\s+\d+', '', command)
            
            if cleaned_command != command:
                print(f"🔧 명령어 수정: {command} → {cleaned_command}")
                print("💡 포트 8501 사용으로 자동 수정됨")
                return cleaned_command
        
        return command
    
    def enforce_file_creation_rule(self, file_path: str) -> str:
        """파일 생성 규칙 강제 적용"""
        path = Path(file_path)
        
        # 루트 디렉토리에서 생성 시도 시 src/로 리다이렉트
        if path.parent == Path("."):
            forbidden_patterns = [
                r"test_.*\.py",
                r"simple_.*\.py", 
                r".*_neumorphism\.py",
                r".*_test\.py"
            ]
            
            import re
            for pattern in forbidden_patterns:
                if re.search(pattern, path.name):
                    suggested_path = f"src/{path.name}"
                    print(f"🔧 파일 경로 수정: {file_path} → {suggested_path}")
                    print("💡 src/ 디렉토리로 자동 리다이렉트됨")
                    return suggested_path
        
        return file_path
    
    def get_mandatory_prompt(self) -> str:
        """AI에게 전달할 강제 프롬프트"""
        return """
🚨 AI 어시스턴트 필수 규칙

코드 생성 전에 반드시 다음을 확인하세요:

1. docs/AI_RULES.md 파일을 읽고 규칙을 확인하세요
2. 포트 사용: streamlit run app.py (포트 지정 금지)
3. 파일 생성: src/ 디렉토리에만 생성
4. 규칙 위반 시 실행을 중단하고 사용자에게 보고하세요

⚠️ 이 규칙들을 무시하면 실행이 차단됩니다.
✅ 모든 작업은 규칙 준수 후에만 실행됩니다.
        """

class AIBehaviorController:
    """AI 행동을 제어하는 메인 컨트롤러"""
    
    def __init__(self):
        self.enforcer = AIBehaviorEnforcer()
        self.rule_violations = []
        
    def validate_and_execute(self, action_type: str, details: str, executor_func):
        """검증 후 실행"""
        try:
            # 1. 사전 검증
            validation_result = self.enforcer.pre_execution_hook(action_type, details)
            
            # 2. 명령어 수정
            if action_type == "streamlit_run":
                details = self.enforcer.enforce_port_rule(details)
            elif action_type == "file_creation":
                details = self.enforcer.enforce_file_creation_rule(details)
            
            # 3. 실행
            if validation_result.get("valid", True):
                print(f"🚀 실행 허용: {details}")
                return executor_func(details)
            else:
                print(f"⏸️ 실행 보류: {details}")
                return None
                
        except RuleViolationError as e:
            self.rule_violations.append({
                "action_type": action_type,
                "details": details,
                "error": e.message,
                "suggestion": e.suggestion
            })
            print(f"🚫 실행 차단: {e.message}")
            return None
    
    def get_violation_summary(self) -> str:
        """위반 사항 요약"""
        if not self.rule_violations:
            return "✅ 규칙 위반 없음"
        
        summary = f"🚨 규칙 위반 {len(self.rule_violations)}건:\n"
        for i, violation in enumerate(self.rule_violations, 1):
            summary += f"{i}. {violation['error']}\n"
            summary += f"   제안: {violation['suggestion']}\n"
        
        return summary

# 전역 AI 행동 컨트롤러
ai_controller = AIBehaviorController()

def enforce_ai_behavior(action_type: str, details: str, executor_func):
    """AI 행동 강제 적용"""
    return ai_controller.validate_and_execute(action_type, details, executor_func)

def get_ai_mandatory_prompt():
    """AI 필수 프롬프트 반환"""
    return ai_controller.enforcer.get_mandatory_prompt()

if __name__ == "__main__":
    # 테스트
    print("🤖 AI 행동 패턴 강제 변경 시스템 테스트")
    print("=" * 50)
    
    # 강제 프롬프트 출력
    print("\n📋 AI 필수 프롬프트:")
    print(get_ai_mandatory_prompt())
    
    # 테스트 실행
    test_actions = [
        ("streamlit_run", "streamlit run app.py --server.port 8520"),
        ("streamlit_run", "streamlit run app.py"),
        ("file_creation", "test_new.py"),
        ("file_creation", "src/new_file.py"),
    ]
    
    print("\n🧪 행동 강제 적용 테스트:")
    for action_type, details in test_actions:
        print(f"\n테스트: {action_type} - {details}")
        try:
            # 더미 실행 함수
            def dummy_executor(cmd):
                return f"실행됨: {cmd}"
            
            result = enforce_ai_behavior(action_type, details, dummy_executor)
            if result:
                print(f"✅ 결과: {result}")
            else:
                print("❌ 실행 차단됨")
        except Exception as e:
            print(f"🚨 오류: {e}")
    
    # 위반 사항 요약
    print(f"\n📊 위반 사항 요약:")
    print(ai_controller.get_violation_summary())
