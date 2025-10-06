#!/usr/bin/env python3
"""
MAIC Error Tracker 테스트 스크립트
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.error_tracker import ErrorTracker
from tools.auto_error_fixer import AutoErrorFixer

def test_error_tracker():
    """에러 추적 시스템 테스트"""
    print("🧪 에러 추적 시스템 테스트 시작...")
    
    # 에러 추적기 초기화
    tracker = ErrorTracker()
    
    # 테스트 에러 로그
    test_errors = [
        "ModuleNotFoundError: No module named 'src.agents'",
        "StreamlitDuplicateElementKey: Duplicate key 'admin_restore_index'",
        "ImportError: cannot import name 'stream_llm'",
        "ModuleNotFoundError: No module named 'src.agents'",  # 중복 에러
        "ModuleNotFoundError: No module named 'src.agents'",  # 3회째
    ]
    
    print("\n📝 테스트 에러 로그 기록 중...")
    for i, error_msg in enumerate(test_errors, 1):
        error_id = tracker.log_error(error_msg, {"test": True, "iteration": i})
        print(f"  {i}. 에러 ID: {error_id}")
    
    # 에러 요약 확인
    print("\n📊 에러 요약:")
    summary = tracker.get_error_summary()
    print(f"  총 에러 수: {summary['total_errors']}")
    print(f"  미해결 에러: {summary['unresolved_errors']}")
    print(f"  반복 에러: {summary['recurring_errors']}")
    print(f"  에러 타입: {list(summary['error_types'].keys())}")
    
    # 자동 수정 테스트
    print("\n🔧 자동 수정 시스템 테스트...")
    fixer = AutoErrorFixer()
    
    # Import 에러 수정 테스트
    print("  Import 에러 수정 테스트:")
    success = fixer._fix_import_errors()
    print(f"    결과: {'성공' if success else '실패'}")
    
    # 캐시 에러 수정 테스트
    print("  캐시 에러 수정 테스트:")
    success = fixer._fix_cache_errors()
    print(f"    결과: {'성공' if success else '실패'}")
    
    print("\n✅ 에러 추적 시스템 테스트 완료!")

def test_import_fix():
    """Import 에러 수정 테스트"""
    print("\n🔧 Import 에러 수정 테스트...")
    
    try:
        # 현재 디렉토리를 Python 경로에 추가
        import sys
        sys.path.insert(0, '.')
        
        # Import 테스트
        from src.application.agents.responder import answer_stream
        print("✅ responder.py import 성공")
        
        from src.application.agents.evaluator import evaluate_stream
        print("✅ evaluator.py import 성공")
        
        from src.application.agents._common import stream_llm
        print("✅ _common.py import 성공")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import 실패: {e}")
        return False

if __name__ == "__main__":
    test_error_tracker()
    test_import_fix()
