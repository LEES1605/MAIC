#!/usr/bin/env python3
"""
MAIC Error Tracking and Auto-Documentation System

이 시스템은 반복되는 에러와 수정 과정을 자동으로 추적하고
DEVELOPMENT_HISTORY.md에 기록합니다.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import hashlib
import re

class ErrorTracker:
    """에러 추적 및 자동 문서화 시스템"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.error_log_file = self.project_root / "tools" / "error_log.json"
        self.history_file = self.project_root / "docs" / "DEVELOPMENT_HISTORY.md"
        self.error_patterns = self._load_error_patterns()
        self.current_session = self._get_session_id()
        
    def _get_session_id(self) -> str:
        """현재 세션 ID 생성"""
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def _load_error_patterns(self) -> Dict[str, Dict]:
        """알려진 에러 패턴 로드"""
        return {
            "import_error": {
                "patterns": [
                    r"ModuleNotFoundError: No module named 'src\.agents'",
                    r"ModuleNotFoundError: No module named 'src\.common'",
                    r"ModuleNotFoundError: No module named 'src\.core'",
                    r"ImportError: cannot import name",
                ],
                "category": "Import Path Issues",
                "common_solutions": [
                    "Python __pycache__ 삭제",
                    "Import 경로 수정",
                    "모듈 구조 확인"
                ]
            },
            "streamlit_error": {
                "patterns": [
                    r"StreamlitDuplicateElementKey",
                    r"missing ScriptRunContext",
                    r"Session state does not function",
                ],
                "category": "Streamlit Issues",
                "common_solutions": [
                    "고유 키 설정",
                    "세션 상태 관리 개선",
                    "컴포넌트 재구성"
                ]
            },
            "cache_error": {
                "patterns": [
                    r"__pycache__",
                    r"cached",
                    r"import.*cache",
                ],
                "category": "Cache Issues",
                "common_solutions": [
                    "__pycache__ 폴더 삭제",
                    "Python 프로세스 재시작",
                    "캐시 정리 스크립트 실행"
                ]
            },
            "ui_error": {
                "patterns": [
                    r"linear_button",
                    r"linear_card",
                    r"CSS.*conflict",
                    r"style.*override",
                ],
                "category": "UI Component Issues",
                "common_solutions": [
                    "Linear 컴포넌트 사용 확인",
                    "CSS 우선순위 조정",
                    "컴포넌트 키 중복 확인"
                ]
            }
        }
    
    def detect_error_type(self, error_message: str) -> Optional[str]:
        """에러 메시지에서 에러 타입 감지"""
        for error_type, config in self.error_patterns.items():
            for pattern in config["patterns"]:
                if re.search(pattern, error_message, re.IGNORECASE):
                    return error_type
        return None
    
    def log_error(self, error_message: str, context: Dict[str, Any] = None) -> str:
        """에러 로그 기록"""
        error_id = self._generate_error_id(error_message)
        error_type = self.detect_error_type(error_message)
        
        error_entry = {
            "error_id": error_id,
            "timestamp": datetime.now().isoformat(),
            "session_id": self.current_session,
            "error_type": error_type,
            "error_message": error_message,
            "context": context or {},
            "attempt_count": 1,
            "resolved": False,
            "solutions_tried": [],
            "final_solution": None
        }
        
        # 기존 에러 로그 로드
        error_log = self._load_error_log()
        
        # 동일한 에러가 있는지 확인
        existing_error = self._find_similar_error(error_log, error_message)
        if existing_error:
            existing_error["attempt_count"] += 1
            existing_error["last_occurrence"] = datetime.now().isoformat()
            error_entry = existing_error
        else:
            error_log.append(error_entry)
        
        # 에러 로그 저장
        self._save_error_log(error_log)
        
        # 3회 이상 반복된 에러인지 확인
        if error_entry["attempt_count"] >= 3:
            self._auto_document_recurring_error(error_entry)
        
        return error_id
    
    def log_solution_attempt(self, error_id: str, solution: str, success: bool):
        """해결 시도 기록"""
        error_log = self._load_error_log()
        
        for error in error_log:
            if error["error_id"] == error_id:
                error["solutions_tried"].append({
                    "solution": solution,
                    "success": success,
                    "timestamp": datetime.now().isoformat()
                })
                
                if success:
                    error["resolved"] = True
                    error["final_solution"] = solution
                    error["resolved_at"] = datetime.now().isoformat()
                    
                    # 성공적으로 해결된 경우 문서 업데이트
                    self._update_solution_documentation(error)
                
                break
        
        self._save_error_log(error_log)
    
    def _generate_error_id(self, error_message: str) -> str:
        """에러 ID 생성"""
        # 에러 메시지의 핵심 부분만 추출하여 해시 생성
        clean_message = re.sub(r'File ".*?"', 'File "..."', error_message)
        clean_message = re.sub(r'line \d+', 'line X', clean_message)
        return hashlib.md5(clean_message.encode()).hexdigest()[:8]
    
    def _find_similar_error(self, error_log: List[Dict], error_message: str) -> Optional[Dict]:
        """유사한 에러 찾기"""
        current_error_id = self._generate_error_id(error_message)
        
        for error in error_log:
            if error["error_id"] == current_error_id:
                return error
        return None
    
    def _load_error_log(self) -> List[Dict]:
        """에러 로그 로드"""
        if self.error_log_file.exists():
            try:
                with open(self.error_log_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return []
        return []
    
    def _save_error_log(self, error_log: List[Dict]):
        """에러 로그 저장"""
        self.error_log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.error_log_file, 'w', encoding='utf-8') as f:
            json.dump(error_log, f, indent=2, ensure_ascii=False)
    
    def _auto_document_recurring_error(self, error_entry: Dict):
        """반복되는 에러 자동 문서화"""
        error_type = error_entry.get("error_type", "Unknown")
        error_message = error_entry["error_message"]
        attempt_count = error_entry["attempt_count"]
        
        # DEVELOPMENT_HISTORY.md에 추가할 내용 생성
        documentation = self._generate_error_documentation(error_entry)
        
        # 파일에 추가
        self._append_to_history_file(documentation)
        
        print(f"🚨 반복 에러 감지: {error_type} ({attempt_count}회 발생)")
        print(f"📝 DEVELOPMENT_HISTORY.md에 자동 기록됨")
    
    def _generate_error_documentation(self, error_entry: Dict) -> str:
        """에러 문서화 내용 생성"""
        error_type = error_entry.get("error_type", "Unknown")
        error_message = error_entry["error_message"]
        attempt_count = error_entry["attempt_count"]
        solutions_tried = error_entry.get("solutions_tried", [])
        
        # 에러 패턴에서 정보 가져오기
        error_config = self.error_patterns.get(error_type, {})
        category = error_config.get("category", "Unknown Category")
        common_solutions = error_config.get("common_solutions", [])
        
        documentation = f"""
### 🔴 반복 에러 감지: {category}

**발생 횟수**: {attempt_count}회  
**에러 타입**: {error_type}  
**발생 시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**에러 메시지**:
```
{error_message[:200]}{'...' if len(error_message) > 200 else ''}
```

**시도한 해결책**:
"""
        
        for i, solution in enumerate(solutions_tried, 1):
            status = "✅ 성공" if solution["success"] else "❌ 실패"
            documentation += f"{i}. {solution['solution']} - {status}\n"
        
        if not solutions_tried:
            documentation += "아직 해결책을 시도하지 않음\n"
        
        documentation += f"""
**권장 해결책**:
"""
        for i, solution in enumerate(common_solutions, 1):
            documentation += f"{i}. {solution}\n"
        
        documentation += f"""
**자동화 제안**:
- 이 에러의 자동 해결 스크립트 개발 필요
- 예방 조치 구현 필요
- 모니터링 시스템 강화 필요

---
"""
        
        return documentation
    
    def _append_to_history_file(self, documentation: str):
        """DEVELOPMENT_HISTORY.md에 내용 추가"""
        if not self.history_file.exists():
            print("⚠️ DEVELOPMENT_HISTORY.md 파일이 없습니다.")
            return
        
        # 파일 읽기
        with open(self.history_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # "자주 반복된 실수들" 섹션 찾기
        section_marker = "### 🔄 자주 반복된 실수들"
        if section_marker in content:
            # 섹션 시작 부분에 추가
            insert_pos = content.find(section_marker) + len(section_marker)
            new_content = content[:insert_pos] + documentation + content[insert_pos:]
        else:
            # 파일 끝에 추가
            new_content = content + "\n\n" + documentation
        
        # 파일 쓰기
        with open(self.history_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
    
    def _update_solution_documentation(self, error_entry: Dict):
        """해결된 에러의 문서 업데이트"""
        error_type = error_entry.get("error_type", "Unknown")
        final_solution = error_entry.get("final_solution", "")
        
        print(f"✅ 에러 해결됨: {error_type}")
        print(f"💡 최종 해결책: {final_solution}")
        
        # 해결된 에러 통계 업데이트
        self._update_resolution_stats(error_entry)
    
    def _update_resolution_stats(self, error_entry: Dict):
        """해결 통계 업데이트"""
        stats_file = self.project_root / "tools" / "error_stats.json"
        
        if stats_file.exists():
            with open(stats_file, 'r', encoding='utf-8') as f:
                stats = json.load(f)
        else:
            stats = {
                "total_errors": 0,
                "resolved_errors": 0,
                "recurring_errors": 0,
                "error_types": {}
            }
        
        stats["total_errors"] += 1
        stats["resolved_errors"] += 1
        
        error_type = error_entry.get("error_type", "Unknown")
        if error_type not in stats["error_types"]:
            stats["error_types"][error_type] = {"count": 0, "resolved": 0}
        
        stats["error_types"][error_type]["count"] += 1
        stats["error_types"][error_type]["resolved"] += 1
        
        if error_entry["attempt_count"] >= 3:
            stats["recurring_errors"] += 1
        
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
    
    def get_error_summary(self) -> Dict:
        """에러 요약 정보 반환"""
        error_log = self._load_error_log()
        
        summary = {
            "total_errors": len(error_log),
            "unresolved_errors": len([e for e in error_log if not e.get("resolved", False)]),
            "recurring_errors": len([e for e in error_log if e.get("attempt_count", 0) >= 3]),
            "error_types": {},
            "recent_errors": error_log[-5:] if error_log else []
        }
        
        for error in error_log:
            error_type = error.get("error_type", "Unknown")
            if error_type not in summary["error_types"]:
                summary["error_types"][error_type] = 0
            summary["error_types"][error_type] += 1
        
        return summary
    
    def generate_auto_fix_script(self, error_type: str) -> str:
        """자동 수정 스크립트 생성"""
        scripts = {
            "import_error": """
# Import 에러 자동 수정 스크립트
import os
import shutil

def fix_import_errors():
    # __pycache__ 삭제
    for root, dirs, files in os.walk('.'):
        if '__pycache__' in dirs:
            shutil.rmtree(os.path.join(root, '__pycache__'))
    
    # import 경로 수정 (예시)
    # 실제로는 더 정교한 로직 필요
    
    print("✅ Import 에러 수정 완료")

if __name__ == "__main__":
    fix_import_errors()
""",
            "cache_error": """
# 캐시 에러 자동 수정 스크립트
import os
import shutil

def clear_cache():
    # __pycache__ 삭제
    for root, dirs, files in os.walk('.'):
        if '__pycache__' in dirs:
            shutil.rmtree(os.path.join(root, '__pycache__'))
    
    print("✅ 캐시 정리 완료")

if __name__ == "__main__":
    clear_cache()
""",
            "streamlit_error": """
# Streamlit 에러 자동 수정 스크립트
import streamlit as st

def fix_streamlit_errors():
    # 세션 상태 초기화
    if 'error_count' in st.session_state:
        del st.session_state['error_count']
    
    # 페이지 새로고침
    st.rerun()
    
    print("✅ Streamlit 에러 수정 완료")

if __name__ == "__main__":
    fix_streamlit_errors()
"""
        }
        
        return scripts.get(error_type, "# 해당 에러 타입에 대한 자동 수정 스크립트가 없습니다.")


def main():
    """메인 함수 - CLI 인터페이스"""
    import sys
    
    tracker = ErrorTracker()
    
    if len(sys.argv) < 2:
        print("사용법: python error_tracker.py <command> [args]")
        print("명령어:")
        print("  log <error_message>     - 에러 로그 기록")
        print("  summary                 - 에러 요약 표시")
        print("  auto-fix <error_type>   - 자동 수정 스크립트 생성")
        return
    
    command = sys.argv[1]
    
    if command == "log" and len(sys.argv) > 2:
        error_message = " ".join(sys.argv[2:])
        error_id = tracker.log_error(error_message)
        print(f"에러 로그 기록됨: {error_id}")
    
    elif command == "summary":
        summary = tracker.get_error_summary()
        print("📊 에러 요약:")
        print(f"  총 에러 수: {summary['total_errors']}")
        print(f"  미해결 에러: {summary['unresolved_errors']}")
        print(f"  반복 에러: {summary['recurring_errors']}")
        print("\n에러 타입별 통계:")
        for error_type, count in summary['error_types'].items():
            print(f"  {error_type}: {count}회")
    
    elif command == "auto-fix" and len(sys.argv) > 2:
        error_type = sys.argv[2]
        script = tracker.generate_auto_fix_script(error_type)
        script_file = f"tools/auto_fix_{error_type}.py"
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(script)
        print(f"자동 수정 스크립트 생성됨: {script_file}")
    
    else:
        print("잘못된 명령어입니다.")


if __name__ == "__main__":
    main()
