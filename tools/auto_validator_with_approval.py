# tools/auto_validator_with_approval.py

from typing import Dict, Callable
from rule_reader import RuleReader
from universal_validator import UniversalValidator

def auto_validate_with_user_approval(search_term: str, code_generator_func: Callable) -> bool:
    """
    자동 검증 + 사용자 승인 시스템
    """
    print("🔍 코드 생성 전 자동 검증 시작...")
    
    # 1. 자동 검증 실행
    validator = UniversalValidator()
    results = validator.validate_before_code_generation(search_term)
    
    # 2. 검증 결과 자동 보고
    report = validator.generate_report(results)
    print(report)
    
    # 3. 위반 시 자동 차단
    if results['overall_status'] == 'FAIL':
        print("❌ 규칙 위반으로 인해 코드 생성이 차단되었습니다.")
        print("📋 해결 방안:")
        _show_resolution_plan(results)
        return False
    
    # 4. 통과 시 사용자 승인 요청
    print("✅ 모든 검증 통과!")
    print("🤔 코드 생성을 진행하시겠습니까?")
    print("   [Y] 예 - 코드 생성 진행")
    print("   [N] 아니오 - 취소")
    
    # 5. 사용자 승인 대기
    approval = input("승인 여부를 입력하세요 (Y/N): ").strip().upper()
    
    if approval == 'Y':
        print("🎉 사용자 승인 완료: 코드 생성 진행")
        try:
            code_generator_func()
            print("✅ 코드 생성 완료")
            return True
        except Exception as e:
            print(f"❌ 코드 생성 실패: {e}")
            return False
    else:
        print("🚫 사용자 승인 거부: 코드 생성 취소")
        return False

def _show_resolution_plan(results: Dict):
    """해결 방안 제시"""
    print("\n📋 해결 방안:")
    
    if results['duplicate_check']['has_issues']:
        print("1. 중복 파일 정리:")
        for issue in results['duplicate_check']['issues']:
            print(f"   - {issue}")
    
    if results['architecture_check']['has_issues']:
        print("2. 아키텍처 일관성 유지:")
        for issue in results['architecture_check']['issues']:
            print(f"   - {issue}")
    
    if results['naming_check']['has_issues']:
        print("3. 명명 규칙 준수:")
        for issue in results['naming_check']['issues']:
            print(f"   - {issue}")
    
    print("\n💡 정리 후 다시 요청해주세요.")

# 사용 예시
def generate_new_component():
    """새 컴포넌트 생성 함수"""
    print("새 컴포넌트 생성 중...")
    # 실제 컴포넌트 생성 로직

if __name__ == "__main__":
    # 자동 검증 + 사용자 승인
    success = auto_validate_with_user_approval("new_component", generate_new_component)
    print(f"코드 생성 성공 여부: {success}")
