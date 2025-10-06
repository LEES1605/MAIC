# ===== [01] PURPOSE ==========================================================
# 통합 데이터 파서 - JSON/YAML 파싱을 단일 모듈로 통합
# 의존성 체크 및 폴백 로직, 보안 검증 통합, 에러 처리 표준화

# ===== [02] IMPORTS ==========================================================
from __future__ import annotations

import json
import base64
from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None

# ===== [03] CONFIGURATION ====================================================
@dataclass
class ParserConfig:
    """데이터 파서 설정"""
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    max_yaml_size: int = 100 * 1024  # 100KB
    max_json_size: int = 50 * 1024  # 50KB
    allow_unicode: bool = True
    safe_load: bool = True
    default_encoding: str = "utf-8"
    
    # 보안 설정
    allow_script_tags: bool = False
    allow_eval: bool = False
    allow_import: bool = False
    max_nesting_depth: int = 10

class ParserType(Enum):
    """파서 타입"""
    JSON = "json"
    YAML = "yaml"
    AUTO = "auto"

class ParserError(Exception):
    """파서 에러"""
    def __init__(self, message: str, parser_type: ParserType, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.parser_type = parser_type
        self.original_error = original_error

# ===== [04] SECURITY VALIDATION ==============================================
class SecurityValidator:
    """보안 검증 클래스"""
    
    def __init__(self, config: ParserConfig):
        self.config = config
    
    def validate_content(self, content: str, parser_type: ParserType) -> Tuple[bool, List[str]]:
        """콘텐츠 보안 검증"""
        errors = []
        
        # 1. 크기 검증
        if parser_type == ParserType.YAML and len(content) > self.config.max_yaml_size:
            errors.append(f"YAML 파일이 너무 큽니다. {self.config.max_yaml_size} 바이트 이하로 제한됩니다.")
        elif parser_type == ParserType.JSON and len(content) > self.config.max_json_size:
            errors.append(f"JSON 파일이 너무 큽니다. {self.config.max_json_size} 바이트 이하로 제한됩니다.")
        
        # 2. 위험한 패턴 검증
        dangerous_patterns = []
        if not self.config.allow_script_tags:
            dangerous_patterns.extend([
                "<script", "</script>", "javascript:", "vbscript:",
                "onload=", "onerror=", "onclick=", "onmouseover="
            ])
        
        if not self.config.allow_eval:
            dangerous_patterns.extend([
                "eval(", "Function(", "setTimeout(", "setInterval(",
                "__import__", "exec(", "compile("
            ])
        
        if not self.config.allow_import:
            dangerous_patterns.extend([
                "import ", "from ", "__import__", "reload("
            ])
        
        for pattern in dangerous_patterns:
            if pattern.lower() in content.lower():
                errors.append(f"위험한 패턴이 발견되었습니다: {pattern}")
        
        # 3. 중첩 깊이 검증 (간단한 추정)
        if content.count("{") + content.count("[") > self.config.max_nesting_depth * 10:
            errors.append(f"중첩 깊이가 너무 깊습니다. {self.config.max_nesting_depth} 레벨 이하로 제한됩니다.")
        
        return len(errors) == 0, errors
    
    def sanitize_content(self, content: str) -> str:
        """콘텐츠 정화 (위험한 패턴 제거)"""
        # 기본적인 정화 (더 정교한 정화는 필요에 따라 추가)
        sanitized = content
        
        # 스크립트 태그 제거
        if not self.config.allow_script_tags:
            import re
            sanitized = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
            sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
            sanitized = re.sub(r'vbscript:', '', sanitized, flags=re.IGNORECASE)
        
        return sanitized

# ===== [05] DATA PARSER CLASS ================================================
class DataParser:
    """통합 데이터 파서"""
    
    def __init__(self, config: Optional[ParserConfig] = None):
        self.config = config or ParserConfig()
        self.security_validator = SecurityValidator(self.config)
    
    def _detect_format(self, content: str) -> ParserType:
        """콘텐츠 형식 자동 감지"""
        content = content.strip()
        
        # JSON 감지
        if (content.startswith("{") and content.endswith("}")) or \
           (content.startswith("[") and content.endswith("]")):
            return ParserType.JSON
        
        # YAML 감지 (간단한 휴리스틱)
        if ":" in content and ("---" in content or "\n" in content):
            return ParserType.YAML
        
        # 기본값은 YAML (더 관대함)
        return ParserType.YAML
    
    def _parse_json(self, content: str) -> Dict[str, Any]:
        """JSON 파싱"""
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ParserError(f"JSON 파싱 실패: {e}", ParserType.JSON, e)
    
    def _parse_yaml(self, content: str) -> Dict[str, Any]:
        """YAML 파싱"""
        if not YAML_AVAILABLE:
            # PyYAML이 없으면 JSON으로 폴백 시도
            try:
                return self._parse_json(content)
            except ParserError:
                raise ParserError(
                    "YAML 파서(PyYAML)가 없습니다. 의존성에 'pyyaml>=6'을 추가하세요.",
                    ParserType.YAML
                )
        
        try:
            if self.config.safe_load:
                return yaml.safe_load(content) or {}
            else:
                return yaml.load(content) or {}
        except yaml.YAMLError as e:
            raise ParserError(f"YAML 파싱 실패: {e}", ParserType.YAML, e)
    
    def parse(
        self,
        content: str,
        parser_type: ParserType = ParserType.AUTO,
        validate_security: bool = True,
        sanitize: bool = False
    ) -> Dict[str, Any]:
        """
        데이터 파싱
        
        Args:
            content: 파싱할 콘텐츠
            parser_type: 파서 타입 (AUTO면 자동 감지)
            validate_security: 보안 검증 여부
            sanitize: 콘텐츠 정화 여부
        
        Returns:
            파싱된 데이터
        """
        # 1. 콘텐츠 정화
        if sanitize:
            content = self.security_validator.sanitize_content(content)
        
        # 2. 형식 감지
        if parser_type == ParserType.AUTO:
            parser_type = self._detect_format(content)
        
        # 3. 보안 검증
        if validate_security:
            is_valid, errors = self.security_validator.validate_content(content, parser_type)
            if not is_valid:
                raise ParserError(f"보안 검증 실패: {', '.join(errors)}", parser_type)
        
        # 4. 파싱 실행
        try:
            if parser_type == ParserType.JSON:
                return self._parse_json(content)
            elif parser_type == ParserType.YAML:
                return self._parse_yaml(content)
            else:
                raise ParserError(f"지원하지 않는 파서 타입: {parser_type}", parser_type)
        except ParserError:
            raise
        except Exception as e:
            raise ParserError(f"파싱 중 예상치 못한 오류: {e}", parser_type, e)
    
    def parse_file(
        self,
        file_path: Union[str, Path],
        parser_type: ParserType = ParserType.AUTO,
        encoding: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """파일에서 데이터 파싱"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise ParserError(f"파일이 존재하지 않습니다: {file_path}", parser_type)
        
        if file_path.stat().st_size > self.config.max_file_size:
            raise ParserError(f"파일이 너무 큽니다: {file_path.stat().st_size} > {self.config.max_file_size}", parser_type)
        
        try:
            content = file_path.read_text(encoding=encoding or self.config.default_encoding)
            return self.parse(content, parser_type, **kwargs)
        except UnicodeDecodeError as e:
            raise ParserError(f"파일 인코딩 오류: {e}", parser_type, e)
        except Exception as e:
            raise ParserError(f"파일 읽기 오류: {e}", parser_type, e)
    
    def parse_base64(
        self,
        base64_content: str,
        parser_type: ParserType = ParserType.AUTO,
        **kwargs
    ) -> Dict[str, Any]:
        """Base64 인코딩된 콘텐츠 파싱"""
        try:
            decoded = base64.b64decode(base64_content.encode("utf-8"))
            content = decoded.decode("utf-8")
            return self.parse(content, parser_type, **kwargs)
        except Exception as e:
            raise ParserError(f"Base64 디코딩 오류: {e}", parser_type, e)
    
    def dump(
        self,
        data: Dict[str, Any],
        parser_type: ParserType = ParserType.YAML,
        **kwargs
    ) -> str:
        """데이터를 문자열로 직렬화"""
        try:
            if parser_type == ParserType.JSON:
                return json.dumps(data, ensure_ascii=not self.config.allow_unicode, **kwargs)
            elif parser_type == ParserType.YAML:
                if not YAML_AVAILABLE:
                    # PyYAML이 없으면 JSON으로 폴백
                    return json.dumps(data, ensure_ascii=not self.config.allow_unicode, **kwargs)
                
                return yaml.safe_dump(
                    data,
                    allow_unicode=self.config.allow_unicode,
                    sort_keys=False,
                    **kwargs
                )
            else:
                raise ParserError(f"지원하지 않는 직렬화 타입: {parser_type}", parser_type)
        except Exception as e:
            raise ParserError(f"직렬화 오류: {e}", parser_type, e)
    
    def dump_file(
        self,
        data: Dict[str, Any],
        file_path: Union[str, Path],
        parser_type: ParserType = ParserType.YAML,
        encoding: Optional[str] = None,
        **kwargs
    ) -> None:
        """데이터를 파일로 저장"""
        file_path = Path(file_path)
        
        try:
            content = self.dump(data, parser_type, **kwargs)
            file_path.write_text(content, encoding=encoding or self.config.default_encoding)
        except Exception as e:
            raise ParserError(f"파일 저장 오류: {e}", parser_type, e)

# ===== [06] CONVENIENCE FUNCTIONS ============================================
def parse_yaml(content: str, **kwargs) -> Dict[str, Any]:
    """YAML 파싱 편의 함수"""
    parser = DataParser()
    return parser.parse(content, ParserType.YAML, **kwargs)

def parse_json(content: str, **kwargs) -> Dict[str, Any]:
    """JSON 파싱 편의 함수"""
    parser = DataParser()
    return parser.parse(content, ParserType.JSON, **kwargs)

def parse_auto(content: str, **kwargs) -> Dict[str, Any]:
    """자동 형식 감지 파싱 편의 함수"""
    parser = DataParser()
    return parser.parse(content, ParserType.AUTO, **kwargs)

def load_yaml_file(file_path: Union[str, Path], **kwargs) -> Dict[str, Any]:
    """YAML 파일 로딩 편의 함수"""
    parser = DataParser()
    return parser.parse_file(file_path, ParserType.YAML, **kwargs)

def load_json_file(file_path: Union[str, Path], **kwargs) -> Dict[str, Any]:
    """JSON 파일 로딩 편의 함수"""
    parser = DataParser()
    return parser.parse_file(file_path, ParserType.JSON, **kwargs)

def load_auto_file(file_path: Union[str, Path], **kwargs) -> Dict[str, Any]:
    """자동 형식 감지 파일 로딩 편의 함수"""
    parser = DataParser()
    return parser.parse_file(file_path, ParserType.AUTO, **kwargs)

def dump_yaml(data: Dict[str, Any], **kwargs) -> str:
    """YAML 직렬화 편의 함수"""
    parser = DataParser()
    return parser.dump(data, ParserType.YAML, **kwargs)

def dump_json(data: Dict[str, Any], **kwargs) -> str:
    """JSON 직렬화 편의 함수"""
    parser = DataParser()
    return parser.dump(data, ParserType.JSON, **kwargs)

def save_yaml_file(data: Dict[str, Any], file_path: Union[str, Path], **kwargs) -> None:
    """YAML 파일 저장 편의 함수"""
    parser = DataParser()
    parser.dump_file(data, file_path, ParserType.YAML, **kwargs)

def save_json_file(data: Dict[str, Any], file_path: Union[str, Path], **kwargs) -> None:
    """JSON 파일 저장 편의 함수"""
    parser = DataParser()
    parser.dump_file(data, file_path, ParserType.JSON, **kwargs)

# ===== [07] SINGLETON PATTERN ================================================
_data_parser_instance: Optional[DataParser] = None

def get_data_parser() -> DataParser:
    """데이터 파서 싱글톤 인스턴스 반환"""
    global _data_parser_instance
    if _data_parser_instance is None:
        _data_parser_instance = DataParser()
    return _data_parser_instance

# ===== [08] LEGACY COMPATIBILITY =============================================
def _yaml_load(text: str) -> Dict[str, Any]:
    """레거시 호환성을 위한 YAML 로딩 함수"""
    return parse_yaml(text)

def _safe_yaml_load(content: str) -> Optional[Dict[str, Any]]:
    """레거시 호환성을 위한 안전한 YAML 로딩 함수"""
    try:
        return parse_yaml(content)
    except ParserError:
        return None

def _safe_load_yaml(file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
    """레거시 호환성을 위한 안전한 YAML 파일 로딩 함수"""
    try:
        return load_yaml_file(file_path)
    except ParserError:
        return None

# ===== [09] END ==============================================================
