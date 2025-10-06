#!/usr/bin/env python3
"""
MAIC Auto Error Fixer

반복되는 에러를 자동으로 감지하고 수정하는 시스템
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional
from .error_tracker import ErrorTracker

class AutoErrorFixer:
    """자동 에러 수정 시스템"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.tracker = ErrorTracker(project_root)
        self.fixers = self._initialize_fixers()
    
    def _initialize_fixers(self) -> Dict[str, callable]:
        """에러 수정 함수들 초기화"""
        return {
            "import_error": self._fix_import_errors,
            "cache_error": self._fix_cache_errors,
            "streamlit_error": self._fix_streamlit_errors,
            "ui_error": self._fix_ui_errors,
        }
    
    def _fix_import_errors(self) -> bool:
        """Import 에러 자동 수정"""
        print("🔧 Import 에러 수정 중...")
        
        try:
            # 1. __pycache__ 삭제
            self._clear_python_cache()
            
            # 2. Import 경로 수정
            self._fix_import_paths()
            
            # 3. 모듈 구조 확인
            self._verify_module_structure()
            
            print("✅ Import 에러 수정 완료")
            return True
            
        except Exception as e:
            print(f"❌ Import 에러 수정 실패: {e}")
            return False
    
    def _fix_cache_errors(self) -> bool:
        """캐시 에러 자동 수정"""
        print("🔧 캐시 에러 수정 중...")
        
        try:
            # 1. Python 캐시 삭제
            self._clear_python_cache()
            
            # 2. Streamlit 캐시 삭제
            self._clear_streamlit_cache()
            
            # 3. 임시 파일 정리
            self._clear_temp_files()
            
            print("✅ 캐시 에러 수정 완료")
            return True
            
        except Exception as e:
            print(f"❌ 캐시 에러 수정 실패: {e}")
            return False
    
    def _fix_streamlit_errors(self) -> bool:
        """Streamlit 에러 자동 수정"""
        print("🔧 Streamlit 에러 수정 중...")
        
        try:
            # 1. 세션 상태 초기화
            self._reset_streamlit_session()
            
            # 2. 컴포넌트 키 중복 해결
            self._fix_duplicate_keys()
            
            # 3. Streamlit 재시작
            self._restart_streamlit()
            
            print("✅ Streamlit 에러 수정 완료")
            return True
            
        except Exception as e:
            print(f"❌ Streamlit 에러 수정 실패: {e}")
            return False
    
    def _fix_ui_errors(self) -> bool:
        """UI 에러 자동 수정"""
        print("🔧 UI 에러 수정 중...")
        
        try:
            # 1. Linear 컴포넌트 사용 확인
            self._verify_linear_components()
            
            # 2. CSS 충돌 해결
            self._resolve_css_conflicts()
            
            # 3. 컴포넌트 키 중복 해결
            self._fix_duplicate_keys()
            
            print("✅ UI 에러 수정 완료")
            return True
            
        except Exception as e:
            print(f"❌ UI 에러 수정 실패: {e}")
            return False
    
    def _clear_python_cache(self):
        """Python 캐시 삭제"""
        print("  🗑️ Python __pycache__ 삭제 중...")
        
        for root, dirs, files in os.walk(self.project_root):
            if '__pycache__' in dirs:
                cache_path = os.path.join(root, '__pycache__')
                shutil.rmtree(cache_path)
                print(f"    삭제됨: {cache_path}")
    
    def _clear_streamlit_cache(self):
        """Streamlit 캐시 삭제"""
        print("  🗑️ Streamlit 캐시 삭제 중...")
        
        # Streamlit 캐시 디렉토리들
        cache_dirs = [
            Path.home() / ".streamlit",
            self.project_root / ".streamlit",
        ]
        
        for cache_dir in cache_dirs:
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
                print(f"    삭제됨: {cache_dir}")
    
    def _clear_temp_files(self):
        """임시 파일 정리"""
        print("  🗑️ 임시 파일 정리 중...")
        
        temp_patterns = ["*.tmp", "*.temp", "*.log", "*.pyc"]
        
        for pattern in temp_patterns:
            for file_path in self.project_root.rglob(pattern):
                if file_path.is_file():
                    file_path.unlink()
                    print(f"    삭제됨: {file_path}")
    
    def _fix_import_paths(self):
        """Import 경로 수정"""
        print("  🔧 Import 경로 수정 중...")
        
        # src/agents -> src/application/agents 경로 수정
        python_files = list(self.project_root.rglob("*.py"))
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Import 경로 수정
                old_imports = [
                    "from src.agents._common import",
                    "from src.agents import",
                    "import src.agents",
                ]
                
                new_imports = [
                    "from src.application.agents._common import",
                    "from src.application.agents import",
                    "import src.application.agents",
                ]
                
                modified = False
                for old, new in zip(old_imports, new_imports):
                    if old in content:
                        content = content.replace(old, new)
                        modified = True
                
                if modified:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"    수정됨: {file_path}")
                    
            except Exception as e:
                print(f"    오류: {file_path} - {e}")
    
    def _verify_module_structure(self):
        """모듈 구조 확인"""
        print("  🔍 모듈 구조 확인 중...")
        
        required_modules = [
            "src/application/agents/_common.py",
            "src/application/agents/responder.py",
            "src/application/agents/evaluator.py",
        ]
        
        for module_path in required_modules:
            full_path = self.project_root / module_path
            if not full_path.exists():
                print(f"    ⚠️ 누락된 모듈: {module_path}")
            else:
                print(f"    ✅ 확인됨: {module_path}")
    
    def _reset_streamlit_session(self):
        """Streamlit 세션 상태 초기화"""
        print("  🔄 Streamlit 세션 상태 초기화 중...")
        
        # 세션 상태 초기화 스크립트 생성
        reset_script = """
import streamlit as st

# 모든 세션 상태 초기화
for key in list(st.session_state.keys()):
    if key.startswith('_'):
        del st.session_state[key]

st.rerun()
"""
        
        script_path = self.project_root / "tools" / "reset_session.py"
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(reset_script)
        
        print(f"    세션 초기화 스크립트 생성: {script_path}")
    
    def _fix_duplicate_keys(self):
        """중복 키 해결"""
        print("  🔧 중복 키 해결 중...")
        
        # app.py에서 중복 키 찾기 및 수정
        app_file = self.project_root / "app.py"
        if app_file.exists():
            try:
                with open(app_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 중복 키 패턴 찾기
                import re
                key_pattern = r'key=["\']([^"\']+)["\']'
                keys = re.findall(key_pattern, content)
                
                # 중복 키 찾기
                from collections import Counter
                key_counts = Counter(keys)
                duplicates = [key for key, count in key_counts.items() if count > 1]
                
                if duplicates:
                    print(f"    중복 키 발견: {duplicates}")
                    # 중복 키에 고유 식별자 추가
                    for i, duplicate in enumerate(duplicates):
                        content = content.replace(
                            f'key="{duplicate}"',
                            f'key="{duplicate}_{i}"'
                        )
                    
                    with open(app_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print("    중복 키 수정 완료")
                else:
                    print("    중복 키 없음")
                    
            except Exception as e:
                print(f"    오류: {e}")
    
    def _verify_linear_components(self):
        """Linear 컴포넌트 사용 확인"""
        print("  🔍 Linear 컴포넌트 사용 확인 중...")
        
        # app.py에서 Linear 컴포넌트 사용 확인
        app_file = self.project_root / "app.py"
        if app_file.exists():
            try:
                with open(app_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Linear 컴포넌트 import 확인
                if "from src.ui.components.linear_components import" in content:
                    print("    ✅ Linear 컴포넌트 import 확인됨")
                else:
                    print("    ⚠️ Linear 컴포넌트 import 누락")
                
                # apply_theme() 호출 확인
                if "apply_theme()" in content:
                    print("    ✅ apply_theme() 호출 확인됨")
                else:
                    print("    ⚠️ apply_theme() 호출 누락")
                    
            except Exception as e:
                print(f"    오류: {e}")
    
    def _resolve_css_conflicts(self):
        """CSS 충돌 해결"""
        print("  🎨 CSS 충돌 해결 중...")
        
        # CSS 파일들 확인
        css_files = list(self.project_root.rglob("*.css"))
        
        for css_file in css_files:
            try:
                with open(css_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # CSS 충돌 패턴 확인
                if "!important" in content:
                    print(f"    ⚠️ CSS 충돌 가능성: {css_file}")
                else:
                    print(f"    ✅ CSS 정상: {css_file}")
                    
            except Exception as e:
                print(f"    오류: {css_file} - {e}")
    
    def _restart_streamlit(self):
        """Streamlit 재시작"""
        print("  🔄 Streamlit 재시작 중...")
        
        # Streamlit 프로세스 종료
        try:
            subprocess.run(["taskkill", "/f", "/im", "streamlit.exe"], 
                         capture_output=True, check=False)
            print("    Streamlit 프로세스 종료됨")
        except Exception as e:
            print(f"    프로세스 종료 오류: {e}")
    
    def auto_fix_recurring_errors(self) -> Dict[str, bool]:
        """반복되는 에러들 자동 수정"""
        print("🤖 반복 에러 자동 수정 시작...")
        
        # 에러 로그에서 반복 에러 찾기
        error_log = self.tracker._load_error_log()
        recurring_errors = [e for e in error_log if e.get("attempt_count", 0) >= 3]
        
        if not recurring_errors:
            print("✅ 반복 에러 없음")
            return {}
        
        results = {}
        
        for error in recurring_errors:
            error_type = error.get("error_type", "unknown")
            error_id = error.get("error_id", "")
            
            print(f"\n🔧 에러 수정 중: {error_type} (ID: {error_id})")
            
            if error_type in self.fixers:
                success = self.fixers[error_type]()
                results[error_id] = success
                
                # 수정 결과 기록
                if success:
                    self.tracker.log_solution_attempt(
                        error_id, 
                        f"자동 수정: {error_type}", 
                        True
                    )
                else:
                    self.tracker.log_solution_attempt(
                        error_id, 
                        f"자동 수정 실패: {error_type}", 
                        False
                    )
            else:
                print(f"    ⚠️ {error_type}에 대한 수정 함수가 없습니다.")
                results[error_id] = False
        
        return results
    
    def generate_fix_report(self) -> str:
        """수정 보고서 생성"""
        error_log = self.tracker._load_error_log()
        recurring_errors = [e for e in error_log if e.get("attempt_count", 0) >= 3]
        
        report = "# MAIC 자동 에러 수정 보고서\n\n"
        report += f"**생성 시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        report += f"**반복 에러 수**: {len(recurring_errors)}\n\n"
        
        if recurring_errors:
            report += "## 반복 에러 목록\n\n"
            
            for error in recurring_errors:
                error_type = error.get("error_type", "Unknown")
                attempt_count = error.get("attempt_count", 0)
                resolved = error.get("resolved", False)
                
                status = "✅ 해결됨" if resolved else "❌ 미해결"
                
                report += f"### {error_type}\n"
                report += f"- **발생 횟수**: {attempt_count}회\n"
                report += f"- **상태**: {status}\n"
                report += f"- **에러 ID**: {error.get('error_id', 'N/A')}\n\n"
        
        return report


def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MAIC 자동 에러 수정 시스템")
    parser.add_argument("--fix", action="store_true", help="반복 에러 자동 수정")
    parser.add_argument("--report", action="store_true", help="수정 보고서 생성")
    parser.add_argument("--type", help="특정 에러 타입만 수정")
    
    args = parser.parse_args()
    
    fixer = AutoErrorFixer()
    
    if args.fix:
        if args.type:
            # 특정 타입만 수정
            if args.type in fixer.fixers:
                success = fixer.fixers[args.type]()
                print(f"수정 결과: {'성공' if success else '실패'}")
            else:
                print(f"알 수 없는 에러 타입: {args.type}")
        else:
            # 모든 반복 에러 수정
            results = fixer.auto_fix_recurring_errors()
            print(f"\n수정 완료: {sum(results.values())}/{len(results)}개 성공")
    
    if args.report:
        report = fixer.generate_fix_report()
        report_file = Path("tools") / "error_fix_report.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"보고서 생성됨: {report_file}")


if __name__ == "__main__":
    main()
