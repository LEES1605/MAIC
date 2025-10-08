"""
범용 검증 도구

이 모듈은 프로젝트 전체 코드베이스를 스캔하여 규칙 위반 여부를
종합적으로 검증하는 범용 검증 도구입니다.
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict
from typing import List, Any, Set

# 현재 디렉토리를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent))

from mandatory_validator import MandatoryValidator, RuleViolationError
from rule_reader import RuleReader


class UniversalValidator:
    """범용 검증 클래스"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.rule_reader = RuleReader()
        self.rules = self.rule_reader.load_all_rules()
        self.mandatory_validator = MandatoryValidator()  # 강제적 검증 추가
    
    def validate_before_code_generation(self, search_term: str) -> Dict[str, Any]:
        """
        코드 생성 전 전체 검증을 수행합니다.
        
        Args:
            search_term (str): 검색 키워드 (생성하려는 파일/기능명)
            
        Returns:
            Dict[str, Any]: 검증 결과
        """
        print(f"[VALIDATE] Code generation validation started: {search_term}")
        
        # 강제적 검증 먼저 실행
        mandatory_result = self._mandatory_validation(search_term)
        
        results = {
            'search_term': search_term,
            'mandatory_validation': mandatory_result,  # 강제적 검증 결과 추가
            'duplicate_check': self._check_duplicates(search_term),
            'architecture_check': self._check_architecture(search_term),
            'naming_check': self._check_naming(search_term),
            'overall_status': 'PASS'
        }
        
        # 전체 상태 결정
        has_issues = (
            results['duplicate_check']['has_issues'] or
            results['architecture_check']['has_issues'] or
            results['naming_check']['has_issues']
        )
        
        if has_issues:
            results['overall_status'] = 'FAIL'
        
        return results
    
    def _mandatory_validation(self, search_term: str) -> Dict[str, Any]:
        """강제적 검증 수행"""
        try:
            # Streamlit 명령어 검증
            if "streamlit run" in search_term.lower():
                result = self.mandatory_validator.validate_streamlit_command(search_term)
                return {
                    "type": "streamlit_command",
                    "result": result,
                    "blocking": result.get("blocking", False)
                }
            
            # 파일 생성 검증
            if any(pattern in search_term.lower() for pattern in ["create", "make", "new", "add"]):
                result = self.mandatory_validator.validate_file_creation(search_term)
                return {
                    "type": "file_creation", 
                    "result": result,
                    "blocking": result.get("blocking", False)
                }
            
            return {
                "type": "general",
                "result": {"valid": True},
                "blocking": False
            }
            
        except RuleViolationError as e:
            return {
                "type": "rule_violation",
                "result": {
                    "valid": False,
                    "error": e.message,
                    "suggestion": e.suggestion
                },
                "blocking": True
            }
    
    def _check_duplicates(self, search_term: str) -> Dict[str, Any]:
        """
        중복 파일 및 함수 검사를 수행합니다.
        
        Args:
            search_term (str): 검색 키워드
            
        Returns:
            Dict[str, Any]: 중복 검사 결과
        """
        print("  📋 중복 검사 중...")
        
        issues = []
        duplicate_files = []
        function_duplicates = []
        
        # 프로젝트 전체 Python 파일 스캔
        python_files = list(self.project_root.rglob("*.py"))
        
        # venv 디렉토리 제외
        python_files = [f for f in python_files if "venv" not in str(f)]
        
        # 파일명 기반 중복 검사
        file_basename = search_term.lower().replace('_', '').replace('-', '')
        
        for py_file in python_files:
            if "venv" in str(py_file):
                continue
                
            file_stem = py_file.stem.lower().replace('_', '').replace('-', '')
            
            # 유사한 파일명 검사 (80% 이상 유사)
            if self._calculate_similarity(file_basename, file_stem) > 0.8:
                if py_file.stem != search_term:  # 정확히 같은 이름이 아닌 경우
                    duplicate_files.append(str(py_file))
                    issues.append(f"유사한 파일명 발견: {py_file.stem}")
        
        # 함수 중복 검사
        for py_file in python_files:
            if "venv" in str(py_file):
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 함수 정의 찾기
                function_patterns = re.findall(r'def\s+(\w+)\s*\(', content)
                
                for func_name in function_patterns:
                    func_basename = func_name.lower().replace('_', '')
                    if self._calculate_similarity(file_basename, func_basename) > 0.8:
                        function_duplicates.append(f"{py_file.stem}.{func_name}")
                        issues.append(f"유사한 함수명 발견: {func_name} in {py_file.stem}")
            
            except Exception as e:
                print(f"    ⚠️ 파일 읽기 오류: {py_file} - {e}")
        
        return {
            'has_issues': len(issues) > 0,
            'issues': issues,
            'duplicate_files': duplicate_files,
            'function_duplicates': function_duplicates
        }
    
    def _check_architecture(self, search_term: str) -> Dict[str, Any]:
        """
        아키텍처 일관성 검사를 수행합니다.
        
        Args:
            search_term (str): 검색 키워드
            
        Returns:
            Dict[str, Any]: 아키텍처 검사 결과
        """
        print("  🏗️ 아키텍처 검사 중...")
        
        issues = []
        functional_files_outside_src = []
        ui_files_outside = []
        test_files_outside = []
        
        # 프로젝트 전체 Python 파일 스캔
        python_files = list(self.project_root.rglob("*.py"))
        
        # venv 디렉토리 제외
        python_files = [f for f in python_files if "venv" not in str(f)]
        
        for py_file in python_files:
            if "venv" in str(py_file):
                continue
                
            file_path = str(py_file)
            relative_path = py_file.relative_to(self.project_root)
            
            # src/ 디렉토리 외부의 기능 파일 검사
            if not str(relative_path).startswith('src/') and not str(relative_path).startswith('tests/'):
                # UI 관련 파일인지 확인
                if any(keyword in file_path.lower() for keyword in ['ui', 'component', 'template', 'layout']):
                    ui_files_outside.append(file_path)
                    issues.append(f"UI 파일이 src/ui/ 외부에 위치: {relative_path}")
                
                # 테스트 파일인지 확인
                elif any(keyword in file_path.lower() for keyword in ['test', 'spec']):
                    test_files_outside.append(file_path)
                    issues.append(f"테스트 파일이 tests/ 외부에 위치: {relative_path}")
                
                # 일반 기능 파일인지 확인
                elif not any(keyword in file_path.lower() for keyword in ['config', 'setup', 'init', 'main', 'app']):
                    functional_files_outside_src.append(file_path)
                    issues.append(f"기능 파일이 src/ 외부에 위치: {relative_path}")
        
        # src/ 디렉토리 구조 확인
        src_dir = self.project_root / "src"
        if not src_dir.exists():
            issues.append("src/ 디렉토리가 존재하지 않습니다.")
        
        return {
            'has_issues': len(issues) > 0,
            'issues': issues,
            'functional_files_outside_src': functional_files_outside_src,
            'ui_files_outside': ui_files_outside,
            'test_files_outside': test_files_outside
        }
    
    def _check_naming(self, search_term: str) -> Dict[str, Any]:
        """
        명명 규칙 검사를 수행합니다.
        
        Args:
            search_term (str): 검색 키워드
            
        Returns:
            Dict[str, Any]: 명명 규칙 검사 결과
        """
        print("  📝 명명 규칙 검사 중...")
        
        issues = []
        
        # 검색 키워드 자체의 명명 규칙 검사
        if not re.match(r'^[a-z][a-z0-9_]*$', search_term):
            issues.append(f"검색 키워드가 snake_case 규칙을 위반: {search_term}")
        
        # 프로젝트 전체 Python 파일의 명명 규칙 검사
        python_files = list(self.project_root.rglob("*.py"))
        
        # venv 디렉토리 제외
        python_files = [f for f in python_files if "venv" not in str(f)]
        
        for py_file in python_files:
            if "venv" in str(py_file):
                continue
                
            file_stem = py_file.stem
            
            # 파일명 snake_case 검사
            if not re.match(r'^[a-z][a-z0-9_]*$', file_stem):
                issues.append(f"파일명이 snake_case 규칙을 위반: {file_stem}")
            
            # 클래스명 PascalCase 검사
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 클래스 정의 찾기
                class_patterns = re.findall(r'class\s+(\w+)\s*\(', content)
                
                for class_name in class_patterns:
                    if not re.match(r'^[A-Z][a-zA-Z0-9]*$', class_name):
                        issues.append(f"클래스명이 PascalCase 규칙을 위반: {class_name} in {file_stem}")
                
                # 함수명 snake_case 검사
                function_patterns = re.findall(r'def\s+(\w+)\s*\(', content)
                
                for func_name in function_patterns:
                    if not re.match(r'^[a-z][a-z0-9_]*$', func_name):
                        issues.append(f"함수명이 snake_case 규칙을 위반: {func_name} in {file_stem}")
            
            except Exception as e:
                print(f"    ⚠️ 파일 읽기 오류: {py_file} - {e}")
        
        return {
            'has_issues': len(issues) > 0,
            'issues': issues
        }
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        두 문자열의 유사도를 계산합니다.
        
        Args:
            str1 (str): 첫 번째 문자열
            str2 (str): 두 번째 문자열
            
        Returns:
            float: 유사도 (0.0 ~ 1.0)
        """
        if not str1 or not str2:
            return 0.0
        
        # 간단한 Jaccard 유사도 계산
        set1 = set(str1.lower())
        set2 = set(str2.lower())
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """
        검증 결과를 리포트 형식으로 생성합니다.
        
        Args:
            results (Dict[str, Any]): 검증 결과
            
        Returns:
            str: 생성된 리포트
        """
        report = []
        report.append("=" * 60)
        report.append("🔍 코드 생성 전 검증 리포트")
        report.append("=" * 60)
        report.append(f"검색 키워드: {results['search_term']}")
        report.append(f"전체 상태: {results['overall_status']}")
        report.append("")
        
        # 중복 검사 결과
        dup_check = results['duplicate_check']
        report.append("📋 중복 검사 결과:")
        if dup_check['has_issues']:
            report.append("  ❌ 중복 문제 발견")
            for issue in dup_check['issues']:
                report.append(f"    - {issue}")
            
            if dup_check['duplicate_files']:
                report.append("  📁 중복 파일들:")
                for file in dup_check['duplicate_files']:
                    report.append(f"    - {file}")
            
            if dup_check['function_duplicates']:
                report.append("  ⚙️ 중복 함수들:")
                for func in dup_check['function_duplicates']:
                    report.append(f"    - {func}")
        else:
            report.append("  ✅ 중복 문제 없음")
        
        report.append("")
        
        # 아키텍처 검사 결과
        arch_check = results['architecture_check']
        report.append("🏗️ 아키텍처 검사 결과:")
        if arch_check['has_issues']:
            report.append("  ❌ 아키텍처 문제 발견")
            for issue in arch_check['issues']:
                report.append(f"    - {issue}")
            
            if arch_check['functional_files_outside_src']:
                report.append("  📁 src/ 외부 기능 파일들:")
                for file in arch_check['functional_files_outside_src']:
                    report.append(f"    - {file}")
            
            if arch_check['ui_files_outside']:
                report.append("  🎨 src/ui 외부 UI 파일들:")
                for file in arch_check['ui_files_outside']:
                    report.append(f"    - {file}")
            
            if arch_check['test_files_outside']:
                report.append("  🧪 tests/ 외부 테스트 파일들:")
                for file in arch_check['test_files_outside']:
                    report.append(f"    - {file}")
        else:
            report.append("  ✅ 아키텍처 문제 없음")
        
        report.append("")
        
        # 명명 규칙 검사 결과
        naming_check = results['naming_check']
        report.append("📝 명명 규칙 검사 결과:")
        if naming_check['has_issues']:
            report.append("  ❌ 명명 규칙 위반 발견")
            for issue in naming_check['issues']:
                report.append(f"    - {issue}")
        else:
            report.append("  ✅ 명명 규칙 준수")
        
        report.append("")
        
        # 최종 권고사항
        if results['overall_status'] == 'FAIL':
            report.append("🚨 권고사항:")
            report.append("  1. 중복 파일들을 src/ 디렉토리로 이동")
            report.append("  2. UI 파일들을 src/ui/ 디렉토리로 이동")
            report.append("  3. 테스트 파일들을 tests/ 디렉토리로 이동")
            report.append("  4. 파일명을 snake_case로 변경")
            report.append("  5. 정리 후 다시 코드 생성 요청")
        else:
            report.append("✅ 모든 검증 통과! 코드 생성 가능")
        
        report.append("=" * 60)
        
        return "\n".join(report)


if __name__ == "__main__":
    # 테스트 코드
    validator = UniversalValidator()
    
    print("[TEST] Universal Validator Test")
    print("=" * 50)
    
    # 예시 검증
    test_terms = ["user_service", "admin_panel", "test_component"]
    
    for term in test_terms:
        print(f"\n[VALIDATE] '{term}' 검증 중...")
        results = validator.validate_before_code_generation(term)
        report = validator.generate_report(results)
        print(report)
        print("\n" + "=" * 50)
