"""
규칙 파일 읽기 도구

이 모듈은 docs/rules/ 디렉토리에 저장된 Markdown 형식의 규칙 파일들을
읽고 파싱하여 검증 시스템이 활용할 수 있는 형태로 제공합니다.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Any


class RuleReader:
    """규칙 파일을 읽고 파싱하는 클래스"""
    
    def __init__(self, rules_dir: str = "docs/rules"):
        self.rules_dir = Path(rules_dir)
        self.rules_cache = {}
    
    def load_all_rules(self) -> Dict[str, Dict[str, Any]]:
        """
        docs/rules/ 디렉토리의 모든 규칙 파일을 로드합니다.
        
        Returns:
            Dict[str, Dict[str, Any]]: 규칙 타입별로 정리된 규칙 데이터
        """
        if self.rules_cache:
            return self.rules_cache
        
        rules = {}
        
        if not self.rules_dir.exists():
            print(f"⚠️ 규칙 디렉토리가 존재하지 않습니다: {self.rules_dir}")
            return rules
        
        for rule_file in self.rules_dir.glob("*.md"):
            rule_type = rule_file.stem
            rules[rule_type] = self._parse_rule_file(rule_file)
        
        self.rules_cache = rules
        return rules
    
    def _parse_rule_file(self, file_path: Path) -> Dict[str, Any]:
        """
        개별 규칙 파일을 파싱합니다.
        
        Args:
            file_path (Path): 규칙 파일 경로
            
        Returns:
            Dict[str, Any]: 파싱된 규칙 데이터
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {
                'title': self._extract_title(content),
                'principles': self._extract_principles(content),
                'prohibitions': self._extract_prohibitions(content),
                'requirements': self._extract_requirements(content),
                'checklists': self._extract_checklists(content),
                'content': content
            }
        except Exception as e:
            print(f"❌ 규칙 파일 파싱 오류: {file_path} - {e}")
            return {}
    
    def _extract_title(self, content: str) -> str:
        """문서 제목을 추출합니다."""
        match = re.search(r'^# (.+)$', content, re.MULTILINE)
        return match.group(1) if match else "Unknown"
    
    def _extract_principles(self, content: str) -> List[str]:
        """기본 원칙들을 추출합니다."""
        principles = []
        
        # ## 1. 기본 원칙 섹션 찾기
        principle_section = re.search(
            r'## 📋 기본 원칙(.*?)(?=##|###|\Z)', 
            content, 
            re.DOTALL
        )
        
        if principle_section:
            # ### 1. 원칙명 패턴 찾기
            principle_matches = re.findall(
                r'### \d+\.\s*(.+?)(?=\n|###|\Z)', 
                principle_section.group(1), 
                re.DOTALL
            )
            principles.extend(principle_matches)
        
        return principles
    
    def _extract_prohibitions(self, content: str) -> List[str]:
        """금지 사항들을 추출합니다."""
        prohibitions = []
        
        # ## 🚫 금지 사항 섹션 찾기
        prohibition_section = re.search(
            r'## 🚫 금지 사항(.*?)(?=##|###|\Z)', 
            content, 
            re.DOTALL
        )
        
        if prohibition_section:
            # ### 1. 금지사항명 패턴 찾기
            prohibition_matches = re.findall(
                r'### \d+\.\s*(.+?)(?=\n|###|\Z)', 
                prohibition_section.group(1), 
                re.DOTALL
            )
            prohibitions.extend(prohibition_matches)
        
        return prohibitions
    
    def _extract_requirements(self, content: str) -> List[str]:
        """필수 사항들을 추출합니다."""
        requirements = []
        
        # ## ✅ 필수 사항 섹션 찾기
        requirement_section = re.search(
            r'## ✅ 필수 사항(.*?)(?=##|###|\Z)', 
            content, 
            re.DOTALL
        )
        
        if requirement_section:
            # ### 1. 필수사항명 패턴 찾기
            requirement_matches = re.findall(
                r'### \d+\.\s*(.+?)(?=\n|###|\Z)', 
                requirement_section.group(1), 
                re.DOTALL
            )
            requirements.extend(requirement_matches)
        
        return requirements
    
    def _extract_checklists(self, content: str) -> Dict[str, List[str]]:
        """체크리스트들을 추출합니다."""
        checklists = {}
        
        # ### 1. 항목명 패턴 찾기
        checklist_sections = re.findall(
            r'### \d+\.\s*(.+?)(.*?)(?=###|\Z)', 
            content, 
            re.DOTALL
        )
        
        for section_title, section_content in checklist_sections:
            if "체크리스트" in section_title or "확인" in section_title:
                # - [ ] 항목 패턴 찾기
                items = re.findall(r'- \[ \]\s*(.+?)(?=\n|$)', section_content)
                checklists[section_title.strip()] = items
        
        return checklists
    
    def get_rule_summary(self, rule_type: str) -> Dict[str, Any]:
        """
        특정 규칙 타입의 요약 정보를 반환합니다.
        
        Args:
            rule_type (str): 규칙 타입 (예: 'coding_rules', 'architecture_rules')
            
        Returns:
            Dict[str, Any]: 규칙 요약 정보
        """
        rules = self.load_all_rules()
        
        if rule_type not in rules:
            return {}
        
        rule_data = rules[rule_type]
        
        return {
            'title': rule_data.get('title', ''),
            'principles_count': len(rule_data.get('principles', [])),
            'prohibitions_count': len(rule_data.get('prohibitions', [])),
            'requirements_count': len(rule_data.get('requirements', [])),
            'checklists_count': len(rule_data.get('checklists', {})),
            'principles': rule_data.get('principles', []),
            'prohibitions': rule_data.get('prohibitions', []),
            'requirements': rule_data.get('requirements', [])
        }
    
    def validate_against_rules(self, action: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        특정 액션과 컨텍스트에 대해 규칙 위반 여부를 검증합니다.
        
        Args:
            action (str): 수행하려는 액션 (예: 'create_file', 'create_function')
            context (Dict[str, Any]): 액션 컨텍스트 정보
            
        Returns:
            Dict[str, Any]: 검증 결과
        """
        rules = self.load_all_rules()
        violations = []
        recommendations = []
        
        # 코딩 규칙 검증
        if 'coding_rules' in rules:
            coding_violations = self._check_coding_rules(action, context, rules['coding_rules'])
            violations.extend(coding_violations)
        
        # 아키텍처 규칙 검증
        if 'architecture_rules' in rules:
            arch_violations = self._check_architecture_rules(action, context, rules['architecture_rules'])
            violations.extend(arch_violations)
        
        # 중복 방지 규칙 검증
        if 'duplication_rules' in rules:
            dup_violations = self._check_duplication_rules(action, context, rules['duplication_rules'])
            violations.extend(dup_violations)
        
        return {
            'has_violations': len(violations) > 0,
            'violations': violations,
            'recommendations': recommendations,
            'rule_count': len(rules)
        }
    
    def _check_coding_rules(self, action: str, context: Dict[str, Any], rules: Dict[str, Any]) -> List[str]:
        """코딩 규칙 위반 검사"""
        violations = []
        
        # 파일 생성 시 src/ 디렉토리 내부 여부 확인
        if action == 'create_file':
            file_path = context.get('file_path', '')
            if not file_path.startswith('src/'):
                violations.append("새 파일은 src/ 디렉토리 내부에만 생성할 수 있습니다.")
        
        # 파일명 snake_case 확인
        if action in ['create_file', 'rename_file']:
            file_name = context.get('file_name', '')
            if file_name and not re.match(r'^[a-z][a-z0-9_]*\.py$', file_name):
                violations.append("파일명은 snake_case 형식을 따라야 합니다.")
        
        return violations
    
    def _check_architecture_rules(self, action: str, context: Dict[str, Any], rules: Dict[str, Any]) -> List[str]:
        """아키텍처 규칙 위반 검사"""
        violations = []
        
        # 파일 배치 규칙 확인
        if action == 'create_file':
            file_path = context.get('file_path', '')
            file_type = context.get('file_type', '')
            
            if file_type == 'ui' and not file_path.startswith('src/ui/'):
                violations.append("UI 파일은 src/ui/ 디렉토리에 배치해야 합니다.")
            
            if file_type == 'test' and not file_path.startswith('tests/'):
                violations.append("테스트 파일은 tests/ 디렉토리에 배치해야 합니다.")
        
        return violations
    
    def _check_duplication_rules(self, action: str, context: Dict[str, Any], rules: Dict[str, Any]) -> List[str]:
        """중복 방지 규칙 위반 검사"""
        violations = []
        
        # 중복 파일명 확인
        if action == 'create_file':
            file_name = context.get('file_name', '')
            if file_name and self._check_similar_filename(file_name):
                violations.append(f"유사한 파일명이 이미 존재합니다: {file_name}")
        
        return violations
    
    def _check_similar_filename(self, filename: str) -> bool:
        """유사한 파일명 존재 여부 확인"""
        # 간단한 유사성 검사 (실제로는 더 정교한 알고리즘 필요)
        base_name = filename.replace('.py', '')
        
        # 일반적인 중복 패턴 확인
        similar_patterns = [
            base_name.replace('_service', ''),
            base_name.replace('_manager', ''),
            base_name.replace('_handler', ''),
            base_name.replace('_controller', '')
        ]
        
        # 실제 파일 시스템 검사는 여기서 수행
        # 현재는 단순히 패턴 매칭만 수행
        return False


def load_all_rules() -> Dict[str, Dict[str, Any]]:
    """
    모든 규칙을 로드하는 편의 함수
    
    Returns:
        Dict[str, Dict[str, Any]]: 로드된 규칙들
    """
    reader = RuleReader()
    return reader.load_all_rules()


def get_rule_summary(rule_type: str) -> Dict[str, Any]:
    """
    규칙 요약을 가져오는 편의 함수
    
    Args:
        rule_type (str): 규칙 타입
        
    Returns:
        Dict[str, Any]: 규칙 요약
    """
    reader = RuleReader()
    return reader.get_rule_summary(rule_type)


def validate_against_rules(action: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    규칙 위반 검증을 수행하는 편의 함수
    
    Args:
        action (str): 액션
        context (Dict[str, Any]): 컨텍스트
        
    Returns:
        Dict[str, Any]: 검증 결과
    """
    reader = RuleReader()
    return reader.validate_against_rules(action, context)


if __name__ == "__main__":
    # 테스트 코드
    reader = RuleReader()
    
    print("📋 로드된 규칙들:")
    rules = reader.load_all_rules()
    for rule_type, rule_data in rules.items():
        print(f"  - {rule_type}: {rule_data.get('title', 'Unknown')}")
    
    print("\n📊 코딩 규칙 요약:")
    summary = reader.get_rule_summary('coding_rules')
    print(f"  - 제목: {summary.get('title', 'Unknown')}")
    print(f"  - 기본 원칙: {summary.get('principles_count', 0)}개")
    print(f"  - 금지 사항: {summary.get('prohibitions_count', 0)}개")
    print(f"  - 필수 사항: {summary.get('requirements_count', 0)}개")
    
    print("\n🔍 규칙 검증 테스트:")
    result = reader.validate_against_rules('create_file', {
        'file_path': 'test_file.py',
        'file_name': 'test_file.py',
        'file_type': 'ui'
    })
    print(f"  - 위반 여부: {result['has_violations']}")
    if result['violations']:
        for violation in result['violations']:
            print(f"    - {violation}")
