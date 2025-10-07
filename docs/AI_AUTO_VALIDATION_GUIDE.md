# AI 자동 검증 시스템 사용 가이드

## 🚀 개요

이 문서는 MAIC 프로젝트에 통합된 AI 자동 검증 시스템의 작동 방식과 사용 방법을 설명합니다. 이 시스템은 AI 어시스턴트가 코드를 생성하기 전에 프로젝트의 코딩 규칙, 아키텍처 일관성, 중복 여부 등을 자동으로 검증하고, 사용자 승인 후에만 실제 코드 생성을 진행하도록 설계되었습니다.

## 🎯 시스템 목표

- **재발 방지**: AI 어시스턴트의 코드 생성으로 인한 중복, 아키텍처 불일치, 규칙 위반 등의 문제 재발 방지.
- **코드 품질 향상**: 모든 생성 코드가 프로젝트의 표준과 일관성을 유지하도록 보장.
- **개발 효율성 증대**: 불필요한 수정 및 디버깅 시간 단축.
- **사용자 통제 강화**: AI의 코드 생성에 대한 최종 결정권을 사용자에게 부여.

## 🔧 시스템 구성 요소

### 1. 규칙 파일 (`docs/rules/`)

Markdown 형식으로 작성된 규칙 파일들은 프로젝트의 코딩 표준을 정의합니다.

- `coding_rules.md`: 일반적인 코딩 규칙 (명명 규칙, 코드 정리 등)
- `architecture_rules.md`: 프로젝트의 아키텍처 구조 및 코드 배치 규칙 (`src/` 디렉토리 구조 등)
- `duplication_rules.md`: 코드 중복 방지 규칙 (파일, 함수, 클래스 중복 등)

### 2. 규칙 읽기 도구 (`tools/rule_reader.py`)

규칙 파일들을 읽고 파싱하여 검증 시스템이 활용할 수 있는 형태로 제공합니다.

- `load_all_rules()`: `docs/rules/` 디렉토리의 모든 규칙 파일을 로드.
- `get_rule_summary(rule_type)`: 특정 규칙 타입의 요약 정보를 반환.
- `validate_against_rules(action, context)`: 특정 액션과 컨텍스트에 대해 규칙 위반 여부를 검증.

### 3. 범용 검증 도구 (`tools/universal_validator.py`)

프로젝트 전체 코드베이스를 스캔하여 규칙 위반 여부를 종합적으로 검증합니다.

- `validate_before_code_generation(search_term)`: 코드 생성 전 중복, 아키텍처, 명명 규칙을 검사.
- `_check_duplicates(search_term)`: 파일 및 함수 중복 검사.
- `_check_architecture(search_term)`: `src/` 디렉토리 구조 준수 여부, 기능/UI/테스트 파일 배치 검사.
- `_check_naming(search_term)`: 파일명 명명 규칙 준수 여부 검사.
- `generate_report(results)`: 검증 결과를 보기 쉬운 리포트 형식으로 생성.

### 4. AI 자동 검증 시스템 (`tools/ai_auto_validator.py`)

AI 어시스턴트의 코드 생성 요청을 받아 `universal_validator`를 실행하고, 그 결과를 바탕으로 사용자에게 승인을 요청합니다.

- `auto_validate_before_code_generation(search_term, code_generator_func, user_request_context)`:
  - `universal_validator`를 호출하여 자동 검증 실행.
  - 검증 결과를 리포트 형식으로 출력.
  - 규칙 위반 시 코드 생성을 차단하고 해결 방안 제시.
  - 검증 통과 시 사용자에게 코드 생성 승인 요청.
  - 사용자 승인 시 `code_generator_func`를 호출하여 실제 코드 생성 진행.

### 5. AI 어시스턴트 최종 통합 (`tools/ai_integration_final.py`)

AI 어시스턴트의 내부 로직에 `ai_auto_validator`를 통합하여, 모든 코드 생성 요청이 이 시스템을 거치도록 합니다.

- `integrate_ai_assistant_workflow(user_request: str, code_generation_logic: Callable)`:
  - 사용자 요청을 처리하기 전에 `auto_validate_before_code_generation`을 호출.
  - 검증 및 사용자 승인 절차를 거친 후 `code_generation_logic`을 실행.

## ⚙️ 작동 방식 (AI 어시스턴트 관점)

1. **사용자 요청 수신**: AI 어시스턴트가 사용자로부터 코드 생성 또는 수정 요청을 받습니다.
2. **자동 검증 시작**: AI 어시스턴트는 `ai_integration_final.py`를 통해 `ai_auto_validator.py`의 `auto_validate_before_code_generation` 함수를 자동으로 호출합니다.
3. **규칙 검사**: `universal_validator.py`가 `docs/rules/`에 정의된 규칙들을 바탕으로 현재 프로젝트 코드베이스를 검사합니다.
   - 중복 파일/함수/클래스
   - `src/` 디렉토리 구조 준수 여부
   - 기능/UI/테스트 파일의 올바른 배치
   - 파일명 명명 규칙
4. **결과 보고**: 검증 결과가 상세한 리포트 형태로 사용자에게 제시됩니다.
5. **자동 차단 (규칙 위반 시)**:
   - 만약 규칙 위반 사항이 발견되면, 코드 생성은 자동으로 차단됩니다.
   - AI 어시스턴트는 사용자에게 문제점과 구체적인 해결 방안을 제시하고, 수정을 요청합니다.
6. **사용자 승인 요청 (검증 통과 시)**:
   - 모든 규칙 검사를 통과하면, AI 어시스턴트는 사용자에게 실제 코드 생성을 진행할지 여부를 명시적으로 묻습니다.
   - 사용자는 `Y` 또는 `N`으로 응답하여 승인 또는 거부할 수 있습니다.
7. **코드 생성 (사용자 승인 시)**:
   - 사용자가 `Y`로 승인하면, `ai_auto_validator.py`는 `code_generator_func`를 호출하여 실제 코드 생성 로직을 실행합니다.
   - 코드가 성공적으로 생성되면 완료 메시지를 출력합니다.
8. **코드 생성 취소 (사용자 거부 시)**:
   - 사용자가 `N`으로 거부하면, 코드 생성은 취소되고 해당 작업은 중단됩니다.

## 💡 사용 예시 (AI 어시스턴트 내부 로직)

```python
# tools/ai_integration_final.py (AI 어시스턴트의 핵심 통합 로직)

from typing import Callable, Any
from tools.ai_auto_validator import auto_validate_before_code_generation

class AIAssistantCore:
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
        """사용자 요청을 처리하고 자동 검증 및 승인 절차를 거칩니다."""
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
```

**참고**: `auto_validate_before_code_generation` 함수는 사용자 승인 여부를 직접 `input()`으로 받지 않고, AI 어시스턴트의 외부 로직에서 사용자 승인 결과를 받아 `code_generator_func`를 호출하도록 설계되었습니다. 위의 `AIAssistantCore` 클래스는 이 통합 방식을 보여줍니다.

## 🛡️ 재발 방지 효과

이 시스템을 통해 다음과 같은 문제들이 효과적으로 방지됩니다:

- **중복 코드**: 기존 코드베이스를 스캔하여 중복을 감지하고 생성을 차단.
- **아키텍처 불일치**: `src/` 디렉토리 구조 및 파일 배치 규칙을 강제하여 일관성 유지.
- **명명 규칙 위반**: 파일명, 함수명 등의 명명 규칙을 자동으로 검사.
- **사용자 통제 부족**: 모든 중요한 코드 변경 전에 사용자 승인을 필수로 요구.

이 가이드를 통해 AI 자동 검증 시스템의 작동 원리와 이점을 이해하고, 안전하고 효율적인 개발 프로세스를 경험하시길 바랍니다.
