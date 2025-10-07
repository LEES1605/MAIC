"""
AI 자동 검증 시스템

이 모듈은 AI 어시스턴트의 코드 생성 요청을 받아 자동으로 검증을 수행하고,
사용자 승인 후에만 실제 코드 생성을 진행하는 시스템입니다.
"""

from typing import Callable, Dict, Any
from tools.universal_validator import UniversalValidator


def auto_validate_before_code_generation(
    search_term: str,
    code_generator_func: Callable[[], Any],
    user_request_context: str
) -> bool:
    """
    AI 어시스턴트의 코드 생성 전 자동 검증 및 사용자 승인 시스템.
    
    Args:
        search_term (str): 검색 키워드 (생성하려는 파일/기능명)
        code_generator_func (Callable): 실제 코드 생성 함수
        user_request_context (str): 사용자 요청 컨텍스트
        
    Returns:
        bool: 검증 및 승인 성공 여부
    """
    print("🔍 AI 자동 검증 시스템 시작...")
    print(f"검색 키워드: {search_term}")
    print(f"컨텍스트: {user_request_context}\n")

    # 1. 자동 검증 실행
    validator = UniversalValidator()
    results = validator.validate_before_code_generation(search_term)

    # 2. 검증 결과 자동 보고
    report = validator.generate_report(results)
    print(report)

    # 3. 위반 시 자동 차단
    if results['overall_status'] == 'FAIL':
        print("\n❌ 규칙 위반으로 인해 코드 생성이 자동 차단되었습니다.")
        print("=" * 60)
        print("📋 상세 해결 방안")
        print("=" * 60)
        _show_resolution_plan(results)
        print("\n" + "=" * 60)
        print("💡 문제를 해결한 후 다시 요청해주세요.")
        print("=" * 60 + "\n")
        return False

    # 4. 통과 시 사용자 승인 요청
    print("\n✅ 모든 검증 통과!")
    print("🤔 실제 코드 생성을 진행하시겠습니까?")
    print("   [Y] 예 - 코드 생성 진행")
    print("   [N] 아니오 - 취소")

    # 5. 사용자 승인 대기 (이 부분은 실제 AI 어시스턴트 환경에서 사용자 입력으로 대체됩니다)
    # 현재는 시뮬레이션을 위해 임시로 'Y'로 가정하거나, 실제 사용자 입력을 받도록 구현해야 합니다.
    # 여기서는 사용자 승인을 기다리는 로직이 필요합니다.
    # 예: approval = input("승인 여부를 입력하세요 (Y/N): ").strip().upper()
    
    # AI 어시스턴트의 내부 로직이므로, 실제 사용자 입력은 외부에서 처리됩니다.
    # 이 함수는 '승인 요청' 단계까지 진행하고, 실제 코드 생성은 외부 로직에서 사용자 승인 후 호출합니다.
    print("\n➡️ 사용자 승인 대기 중...")
    # 실제 AI 어시스턴트에서는 이 시점에서 사용자에게 승인 여부를 묻고 응답을 기다립니다.
    # 여기서는 시뮬레이션을 위해 True를 반환하여 다음 단계로 진행한다고 가정합니다.
    return True  # 이 부분은 실제 통합 시 사용자 승인 결과에 따라 달라집니다.


def _show_resolution_plan(results: Dict):
    """해결 방안 제시"""
    if results['duplicate_check']['has_issues']:
        print("\n1. 중복 파일 정리:")
        for issue in results['duplicate_check']['issues']:
            print(f"   - {issue}")
        if results['duplicate_check'].get('duplicate_files'):
            print("   📁 중복 파일들:")
            for f in results['duplicate_check']['duplicate_files']:
                print(f"      - {f}")
        if results['duplicate_check'].get('function_duplicates'):
            print("   ⚙️ 중복 함수들:")
            for f in results['duplicate_check']['function_duplicates']:
                print(f"      - {f}")

    if results['architecture_check']['has_issues']:
        print("\n2. 아키텍처 일관성 유지:")
        for issue in results['architecture_check']['issues']:
            print(f"   - {issue}")
        if results['architecture_check'].get('functional_files_outside_src'):
            print("   📁 src/ 외부 기능 파일들:")
            for f in results['architecture_check']['functional_files_outside_src']:
                print(f"      - {f}")
        if results['architecture_check'].get('ui_files_outside'):
            print("   🎨 src/ui 외부 UI 파일들:")
            for f in results['architecture_check']['ui_files_outside']:
                print(f"      - {f}")
        if results['architecture_check'].get('test_files_outside'):
            print("   🧪 tests/ 외부 테스트 파일들:")
            for f in results['architecture_check']['test_files_outside']:
                print(f"      - {f}")

    if results['naming_check']['has_issues']:
        print("\n3. 명명 규칙 준수:")
        for issue in results['naming_check']['issues']:
            print(f"   - {issue}")
    
    print("\n" + "=" * 60)
    print("💡 권장 해결 순서:")
    print("1. 중복 파일들을 src/ 디렉토리로 이동")
    print("2. UI 파일들을 src/ui/ 디렉토리로 이동")
    print("3. 테스트 파일들을 tests/ 디렉토리로 이동")
    print("4. 파일명을 snake_case로 변경")
    print("5. 정리 후 다시 코드 생성 요청")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    # 예시 코드 생성 함수
    def example_code_generator():
        print("실제 예시 컴포넌트 코드 생성 중...")
        # 여기에 실제 코드 생성 로직이 들어갑니다.
        pass

    # AI 어시스턴트가 사용자 요청을 처리하는 방식 시뮬레이션
    # 이 함수는 검증을 수행하고, 사용자 승인 단계까지 진행합니다.
    # 실제 코드 생성은 이 함수의 반환값(True)을 받은 후 외부에서 호출됩니다.
    validation_successful = auto_validate_before_code_generation(
        "example_component",
        example_code_generator,
        "예시 컴포넌트 생성 테스트"
    )

    if validation_successful:
        # 이 부분은 AI 어시스턴트의 외부 로직에서 사용자 승인 후 호출됩니다.
        print("사용자 승인 후 코드 생성 함수 호출 (시뮬레이션)")
        # example_code_generator() # 실제 통합 시 이 함수가 호출됩니다.
    else:
        print("코드 생성 취소됨.")
