#!/usr/bin/env python3
"""
보안 강화 테스트 스크립트
- SecurityManager 기능 테스트
- 입력 검증 테스트
- 로그인 시도 제한 테스트
- 에러 메시지 정화 테스트
"""

import sys
import time
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_security_manager():
    """SecurityManager 기본 기능 테스트"""
    print("=== SecurityManager 기본 기능 테스트 ===")
    
    try:
        from src.core.security_manager import (
            get_security_manager, 
            InputType, 
            SecurityLevel,
            validate_input,
            sanitize_error_message
        )
        
        sm = get_security_manager()
        print("[OK] SecurityManager 생성 성공")
        
        # 입력 검증 테스트
        print("\n1. 입력 검증 테스트:")
        
        # 유효한 입력
        is_valid, error = validate_input("안녕하세요", InputType.TEXT, "테스트 입력")
        print(f"   유효한 입력: {is_valid}, 에러: {error}")
        
        # 무효한 입력 (너무 긴 텍스트)
        long_text = "a" * 20000
        is_valid, error = validate_input(long_text, InputType.TEXT, "긴 텍스트")
        print(f"   긴 텍스트: {is_valid}, 에러: {error}")
        
        # SQL 인젝션 시도
        sql_injection = "'; DROP TABLE users; --"
        is_valid, error = validate_input(sql_injection, InputType.TEXT, "SQL 입력", SecurityLevel.HIGH)
        print(f"   SQL 인젝션: {is_valid}, 에러: {error}")
        
        # XSS 시도
        xss_attempt = "<script>alert('XSS')</script>"
        is_valid, error = validate_input(xss_attempt, InputType.TEXT, "XSS 입력", SecurityLevel.HIGH)
        print(f"   XSS 시도: {is_valid}, 에러: {error}")
        
        # 비밀번호 검증
        print("\n2. 비밀번호 검증 테스트:")
        
        # 유효한 비밀번호
        is_valid, error = validate_input("SecurePass123!", InputType.PASSWORD, "비밀번호")
        print(f"   유효한 비밀번호: {is_valid}, 에러: {error}")
        
        # 너무 짧은 비밀번호
        is_valid, error = validate_input("123", InputType.PASSWORD, "짧은 비밀번호")
        print(f"   짧은 비밀번호: {is_valid}, 에러: {error}")
        
        # YAML 검증
        print("\n3. YAML 검증 테스트:")
        
        valid_yaml = """
version: 1.0
modes:
  grammar: "문법 모드"
  sentence: "문장 모드"
  passage: "지문 모드"
"""
        is_valid, error = validate_input(valid_yaml, InputType.YAML, "YAML")
        print(f"   유효한 YAML: {is_valid}, 에러: {error}")
        
        invalid_yaml = "invalid: yaml: content: ["
        is_valid, error = validate_input(invalid_yaml, InputType.YAML, "잘못된 YAML")
        print(f"   잘못된 YAML: {is_valid}, 에러: {error}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] SecurityManager 테스트 실패: {e}")
        return False

def test_login_attempts():
    """로그인 시도 제한 테스트"""
    print("\n=== 로그인 시도 제한 테스트 ===")
    
    try:
        from src.core.security_manager import get_security_manager, check_login_attempts, record_login_attempt
        
        sm = get_security_manager()
        test_user = "test_user_123"
        
        # 초기 상태 확인
        is_allowed, error = check_login_attempts(test_user)
        print(f"1. 초기 상태: {is_allowed}, 에러: {error}")
        
        # 실패 시도 기록
        print("\n2. 실패 시도 기록:")
        for i in range(3):
            record_login_attempt(test_user, False)
            is_allowed, error = check_login_attempts(test_user)
            print(f"   시도 {i+1}: {is_allowed}, 에러: {error}")
        
        # 성공 시도 기록 (잠금 해제)
        print("\n3. 성공 시도 기록:")
        record_login_attempt(test_user, True)
        is_allowed, error = check_login_attempts(test_user)
        print(f"   성공 후: {is_allowed}, 에러: {error}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 로그인 시도 제한 테스트 실패: {e}")
        return False

def test_error_sanitization():
    """에러 메시지 정화 테스트"""
    print("\n=== 에러 메시지 정화 테스트 ===")
    
    try:
        from src.core.security_manager import sanitize_error_message
        
        # 민감한 정보가 포함된 에러
        sensitive_error = Exception("Database error: password=secret123, token=abc123, /home/user/file.py")
        sanitized = sanitize_error_message(sensitive_error)
        print(f"1. 민감한 정보 정화:")
        print(f"   원본: {sensitive_error}")
        print(f"   정화: {sanitized}")
        
        # SQL 에러
        sql_error = Exception("SQL error: SELECT * FROM users WHERE password='admin'")
        sanitized = sanitize_error_message(sql_error)
        print(f"\n2. SQL 에러 정화:")
        print(f"   원본: {sql_error}")
        print(f"   정화: {sanitized}")
        
        # 스택 트레이스 에러
        try:
            raise Exception("Test error with traceback")
        except Exception as e:
            sanitized = sanitize_error_message(e)
            print(f"\n3. 스택 트레이스 정화:")
            print(f"   정화: {sanitized}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 에러 메시지 정화 테스트 실패: {e}")
        return False

def test_error_handler_integration():
    """ErrorHandler 보안 통합 테스트"""
    print("\n=== ErrorHandler 보안 통합 테스트 ===")
    
    try:
        from src.core.error_handler import get_error_handler, ErrorLevel
        
        eh = get_error_handler()
        print("[OK] ErrorHandler 생성 성공")
        
        # 보안 에러 로깅
        print("\n1. 보안 에러 로깅:")
        eh.log("SQL injection attempt detected", ErrorLevel.ERROR, "security", context={"ip": "192.168.1.1"})
        eh.log("XSS pattern detected", ErrorLevel.WARN, "security", context={"pattern": "<script>"})
        
        # 에러 요약
        summary = eh.get_error_summary()
        print(f"2. 에러 요약: {summary}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] ErrorHandler 보안 통합 테스트 실패: {e}")
        return False

def test_security_summary():
    """보안 상태 요약 테스트"""
    print("\n=== 보안 상태 요약 테스트 ===")
    
    try:
        from src.core.security_manager import get_security_manager
        
        sm = get_security_manager()
        summary = sm.get_security_summary()
        
        print("보안 상태 요약:")
        for key, value in summary.items():
            print(f"  {key}: {value}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 보안 상태 요약 테스트 실패: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("보안 강화 시스템 테스트 시작")
    print("=" * 50)
    
    tests = [
        ("SecurityManager 기본 기능", test_security_manager),
        ("로그인 시도 제한", test_login_attempts),
        ("에러 메시지 정화", test_error_sanitization),
        ("ErrorHandler 보안 통합", test_error_handler_integration),
        ("보안 상태 요약", test_security_summary),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n[TEST] {test_name} 테스트 중...")
        try:
            result = test_func()
            results.append((test_name, result))
            if result:
                print(f"[OK] {test_name} 테스트 통과")
            else:
                print(f"[FAIL] {test_name} 테스트 실패")
        except Exception as e:
            print(f"[ERROR] {test_name} 테스트 예외: {e}")
            results.append((test_name, False))
    
    # 결과 요약
    print("\n" + "=" * 50)
    print("보안 강화 시스템 테스트 결과")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[OK] 통과" if result else "[FAIL] 실패"
        print(f"{test_name}: {status}")
    
    print(f"\n총 {total}개 테스트 중 {passed}개 통과 ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("모든 보안 테스트 통과!")
        return True
    else:
        print("일부 보안 테스트 실패")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
