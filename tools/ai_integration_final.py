"""
AI 어시스턴트 통합 최종 모듈

이 모듈은 AI 어시스턴트의 코드 생성 워크플로우에 자동 검증 시스템을
완전히 통합하는 최종 통합 모듈입니다.
"""

from typing import Callable, Any
from tools.ai_auto_validator import auto_validate_before_code_generation


class AIAssistantCore:
    """AI 어시스턴트의 핵심 클래스"""
    
    def __init__(self):
        print("AI 어시스턴트 코어 초기화 완료.")

    def _actual_code_generation_logic(self, request_details: str):
        """실제 코드 생성 로직 (예시)"""
        print(f"⚙️ 실제 코드 생성 중: {request_details}")
        # 여기에 사용자의 요청에 따른 실제 코드 생성 및 파일 수정 로직이 들어갑니다.
        # 예: create_file("src/new_feature/example.py", "print('Hello, new feature!')")
        print("✅ 코드 생성 완료!")
        return True

    def handle_user_request(self, user_request: str, search_term: str):
        """
        사용자 요청을 처리하고 자동 검증 및 승인 절차를 거칩니다.
        
        Args:
            user_request (str): 사용자 요청 내용
            search_term (str): 검색 키워드
        """
        print(f"\n--- 사용자 요청 수신: '{user_request}' ---")

        # 코드 생성 함수를 래핑하여 auto_validate_before_code_generation에 전달
        def wrapped_code_generator():
            return self._actual_code_generation_logic(user_request)

        # 자동 검증 및 사용자 승인 시스템 실행
        validation_and_approval_successful = auto_validate_before_code_generation(
            search_term,
            wrapped_code_generator,
            user_request
        )

        if validation_and_approval_successful:
            # auto_validate_before_code_generation 내부에서 사용자 승인 후
            # wrapped_code_generator가 호출되므로, 여기서는 추가 호출이 필요 없습니다.
            print("✨ 사용자 승인에 따라 코드 생성 프로세스가 완료되었습니다.")
        else:
            print("🚫 사용자 승인 거부 또는 검증 실패로 코드 생성이 취소되었습니다.")


def integrate_ai_assistant_workflow(user_request: str, code_generation_logic: Callable):
    """
    AI 어시스턴트 워크플로우에 자동 검증을 통합합니다.
    
    Args:
        user_request (str): 사용자 요청
        code_generation_logic (Callable): 코드 생성 로직
    """
    print("🤖 AI 어시스턴트 워크플로우 통합 시작...")
    
    # 검색 키워드 추출 (간단한 예시)
    search_term = _extract_search_term(user_request)
    
    # 자동 검증 및 사용자 승인 시스템 실행
    validation_successful = auto_validate_before_code_generation(
        search_term,
        code_generation_logic,
        user_request
    )
    
    if validation_successful:
        print("✅ 통합 워크플로우 완료!")
        return True
    else:
        print("❌ 통합 워크플로우 실패!")
        return False


def _extract_search_term(user_request: str) -> str:
    """
    사용자 요청에서 검색 키워드를 추출합니다.
    
    Args:
        user_request (str): 사용자 요청
        
    Returns:
        str: 추출된 검색 키워드
    """
    # 간단한 키워드 추출 로직
    keywords = user_request.lower().split()
    
    # 일반적인 파일/기능 관련 키워드 찾기
    for keyword in keywords:
        if any(term in keyword for term in ['service', 'component', 'handler', 'manager', 'controller']):
            return keyword
    
    # 첫 번째 단어를 검색 키워드로 사용
    return keywords[0] if keywords else "unknown"


# AI 어시스턴트 사용 예시
if __name__ == "__main__":
    assistant = AIAssistantCore()

    # 시나리오 1: 규칙 위반이 없는 코드 생성 요청
    # assistant.handle_user_request("새로운 유틸리티 함수를 src/shared/에 생성해줘", "new_utility_function")

    # 시나리오 2: 규칙 위반이 있는 코드 생성 요청 (예: src/ 외부에 파일 생성 시도)
    # assistant.handle_user_request("루트 디렉토리에 temp_script.py 파일을 만들어줘", "temp_script")

    # 시나리오 3: 현재 프로젝트 상태에서 검증 테스트 (예시 컴포넌트)
    # 이 시나리오는 현재 프로젝트의 아키텍처 및 명명 규칙 위반을 감지할 것입니다.
    assistant.handle_user_request("예시 컴포넌트를 생성해줘", "example_component")
