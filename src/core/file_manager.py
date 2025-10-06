# ===== [01] PURPOSE ==========================================================
# 통합 파일 매니저 - 파일 읽기/쓰기를 단일 모듈로 통합
# 캐싱 시스템 통합, 에러 처리 표준화, 인코딩 처리 통합

# ===== [02] IMPORTS ==========================================================
from __future__ import annotations

import json
import time
import hashlib
import tempfile
import shutil
from typing import Any, Dict, List, Optional, Union, Tuple, BinaryIO, TextIO
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import threading
from contextlib import contextmanager

# ===== [03] CONFIGURATION ====================================================
@dataclass
class FileManagerConfig:
    """파일 매니저 설정"""
    default_encoding: str = "utf-8"
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    cache_size: int = 1000  # 캐시 항목 수
    cache_ttl: int = 300  # 캐시 TTL (초)
    temp_dir: Optional[Path] = None
    atomic_writes: bool = True
    backup_enabled: bool = True
    backup_count: int = 3
    
    # 성능 설정
    buffer_size: int = 8192
    read_chunk_size: int = 1024 * 1024  # 1MB
    write_chunk_size: int = 1024 * 1024  # 1MB

class FileType(Enum):
    """파일 타입"""
    TEXT = "text"
    BINARY = "binary"
    JSON = "json"
    YAML = "yaml"
    AUTO = "auto"

class FileError(Exception):
    """파일 에러"""
    def __init__(self, message: str, file_path: Optional[Path] = None, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.file_path = file_path
        self.original_error = original_error

# ===== [04] CACHE SYSTEM =====================================================
@dataclass
class CacheEntry:
    """캐시 엔트리"""
    content: Any
    timestamp: float
    size: int
    checksum: str

class FileCache:
    """파일 캐시 시스템"""
    
    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self.max_size = max_size
        self.ttl = ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
    
    def _generate_key(self, file_path: Path, file_type: FileType) -> str:
        """캐시 키 생성"""
        stat = file_path.stat()
        return f"{file_path}:{file_type.value}:{stat.st_mtime}:{stat.st_size}"
    
    def _is_expired(self, entry: CacheEntry) -> bool:
        """캐시 만료 확인"""
        return time.time() - entry.timestamp > self.ttl
    
    def _cleanup(self) -> None:
        """캐시 정리"""
        if len(self._cache) <= self.max_size:
            return
        
        # 만료된 항목 제거
        expired_keys = [
            key for key, entry in self._cache.items()
            if self._is_expired(entry)
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        # 여전히 크기가 크면 오래된 항목 제거
        if len(self._cache) > self.max_size:
            sorted_items = sorted(
                self._cache.items(),
                key=lambda x: x[1].timestamp
            )
            
            remove_count = len(self._cache) - self.max_size
            for key, _ in sorted_items[:remove_count]:
                del self._cache[key]
    
    def get(self, file_path: Path, file_type: FileType) -> Optional[Any]:
        """캐시에서 항목 조회"""
        with self._lock:
            key = self._generate_key(file_path, file_type)
            entry = self._cache.get(key)
            
            if entry is None:
                return None
            
            if self._is_expired(entry):
                del self._cache[key]
                return None
            
            return entry.content
    
    def set(self, file_path: Path, file_type: FileType, content: Any) -> None:
        """캐시에 항목 저장"""
        with self._lock:
            key = self._generate_key(file_path, file_type)
            
            # 콘텐츠 크기 계산
            if isinstance(content, str):
                size = len(content.encode("utf-8"))
            elif isinstance(content, bytes):
                size = len(content)
            else:
                size = len(str(content).encode("utf-8"))
            
            # 체크섬 계산
            if isinstance(content, str):
                checksum = hashlib.md5(content.encode("utf-8")).hexdigest()
            elif isinstance(content, bytes):
                checksum = hashlib.md5(content).hexdigest()
            else:
                checksum = hashlib.md5(str(content).encode("utf-8")).hexdigest()
            
            entry = CacheEntry(
                content=content,
                timestamp=time.time(),
                size=size,
                checksum=checksum
            )
            
            self._cache[key] = entry
            self._cleanup()
    
    def clear(self) -> None:
        """캐시 전체 삭제"""
        with self._lock:
            self._cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        with self._lock:
            total_size = sum(entry.size for entry in self._cache.values())
            return {
                "entries": len(self._cache),
                "total_size": total_size,
                "max_size": self.max_size,
                "ttl": self.ttl
            }

# ===== [05] FILE MANAGER CLASS ===============================================
class FileManager:
    """통합 파일 매니저"""
    
    def __init__(self, config: Optional[FileManagerConfig] = None):
        self.config = config or FileManagerConfig()
        self.cache = FileCache(self.config.cache_size, self.config.cache_ttl)
        self._temp_dir = self.config.temp_dir or Path(tempfile.gettempdir()) / "maic_file_manager"
        self._temp_dir.mkdir(parents=True, exist_ok=True)
    
    def _detect_file_type(self, file_path: Path, content: Optional[str] = None) -> FileType:
        """파일 타입 자동 감지"""
        suffix = file_path.suffix.lower()
        
        if suffix in [".json"]:
            return FileType.JSON
        elif suffix in [".yaml", ".yml"]:
            return FileType.YAML
        elif suffix in [".txt", ".md", ".py", ".js", ".css", ".html", ".xml"]:
            return FileType.TEXT
        elif suffix in [".bin", ".exe", ".dll", ".so", ".dylib", ".jpg", ".png", ".gif", ".pdf"]:
            return FileType.BINARY
        elif content is not None:
            # 콘텐츠 기반 감지
            if content.strip().startswith(("{", "[")):
                return FileType.JSON
            elif ":" in content and ("---" in content or "\n" in content):
                return FileType.YAML
            else:
                return FileType.TEXT
        else:
            return FileType.AUTO
    
    def _validate_file_path(self, file_path: Path) -> None:
        """파일 경로 검증"""
        if not file_path.exists():
            raise FileError(f"파일이 존재하지 않습니다: {file_path}", file_path)
        
        if not file_path.is_file():
            raise FileError(f"파일이 아닙니다: {file_path}", file_path)
        
        if file_path.stat().st_size > self.config.max_file_size:
            raise FileError(
                f"파일이 너무 큽니다: {file_path.stat().st_size} > {self.config.max_file_size}",
                file_path
            )
    
    def _create_backup(self, file_path: Path) -> Optional[Path]:
        """파일 백업 생성"""
        if not self.config.backup_enabled:
            return None
        
        backup_dir = file_path.parent / ".backups"
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = int(time.time())
        backup_path = backup_dir / f"{file_path.name}.{timestamp}.bak"
        
        try:
            shutil.copy2(file_path, backup_path)
            
            # 오래된 백업 정리
            backups = sorted(backup_dir.glob(f"{file_path.name}.*.bak"))
            if len(backups) > self.config.backup_count:
                for old_backup in backups[:-self.config.backup_count]:
                    old_backup.unlink()
            
            return backup_path
        except Exception as e:
            # 백업 실패는 경고만 하고 계속 진행
            pass
        
        return None
    
    def _atomic_write(self, file_path: Path, content: Union[str, bytes], encoding: str) -> None:
        """원자적 파일 쓰기"""
        if not self.config.atomic_writes:
            file_path.write_text(content, encoding=encoding)
            return
        
        # 임시 파일에 쓰기
        temp_file = self._temp_dir / f"temp_{file_path.name}_{int(time.time())}"
        
        try:
            if isinstance(content, str):
                temp_file.write_text(content, encoding=encoding)
            else:
                temp_file.write_bytes(content)
            
            # 원본 파일로 이동
            temp_file.replace(file_path)
        except Exception as e:
            # 임시 파일 정리
            if temp_file.exists():
                temp_file.unlink()
            raise FileError(f"원자적 쓰기 실패: {e}", file_path, e)
    
    def read_text(
        self,
        file_path: Union[str, Path],
        encoding: Optional[str] = None,
        use_cache: bool = True
    ) -> str:
        """텍스트 파일 읽기"""
        file_path = Path(file_path)
        encoding = encoding or self.config.default_encoding
        
        # 캐시 확인
        if use_cache:
            cached_content = self.cache.get(file_path, FileType.TEXT)
            if cached_content is not None:
                return cached_content
        
        # 파일 검증
        self._validate_file_path(file_path)
        
        try:
            content = file_path.read_text(encoding=encoding)
            
            # 캐시에 저장
            if use_cache:
                self.cache.set(file_path, FileType.TEXT, content)
            
            return content
        except UnicodeDecodeError as e:
            raise FileError(f"인코딩 오류: {e}", file_path, e)
        except Exception as e:
            raise FileError(f"파일 읽기 오류: {e}", file_path, e)
    
    def read_binary(
        self,
        file_path: Union[str, Path],
        use_cache: bool = True
    ) -> bytes:
        """바이너리 파일 읽기"""
        file_path = Path(file_path)
        
        # 캐시 확인
        if use_cache:
            cached_content = self.cache.get(file_path, FileType.BINARY)
            if cached_content is not None:
                return cached_content
        
        # 파일 검증
        self._validate_file_path(file_path)
        
        try:
            content = file_path.read_bytes()
            
            # 캐시에 저장
            if use_cache:
                self.cache.set(file_path, FileType.BINARY, content)
            
            return content
        except Exception as e:
            raise FileError(f"파일 읽기 오류: {e}", file_path, e)
    
    def read_json(
        self,
        file_path: Union[str, Path],
        encoding: Optional[str] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """JSON 파일 읽기"""
        file_path = Path(file_path)
        encoding = encoding or self.config.default_encoding
        
        # 캐시 확인
        if use_cache:
            cached_content = self.cache.get(file_path, FileType.JSON)
            if cached_content is not None:
                return cached_content
        
        try:
            content = self.read_text(file_path, encoding, use_cache=False)
            data = json.loads(content)
            
            # 캐시에 저장
            if use_cache:
                self.cache.set(file_path, FileType.JSON, data)
            
            return data
        except json.JSONDecodeError as e:
            raise FileError(f"JSON 파싱 오류: {e}", file_path, e)
        except Exception as e:
            raise FileError(f"JSON 파일 읽기 오류: {e}", file_path, e)
    
    def read_yaml(
        self,
        file_path: Union[str, Path],
        encoding: Optional[str] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """YAML 파일 읽기"""
        file_path = Path(file_path)
        encoding = encoding or self.config.default_encoding
        
        # 캐시 확인
        if use_cache:
            cached_content = self.cache.get(file_path, FileType.YAML)
            if cached_content is not None:
                return cached_content
        
        try:
            from src.core.data_parser import load_yaml_file
            data = load_yaml_file(file_path, encoding=encoding)
            
            # 캐시에 저장
            if use_cache:
                self.cache.set(file_path, FileType.YAML, data)
            
            return data
        except Exception as e:
            raise FileError(f"YAML 파일 읽기 오류: {e}", file_path, e)
    
    def read_auto(
        self,
        file_path: Union[str, Path],
        encoding: Optional[str] = None,
        use_cache: bool = True
    ) -> Union[str, bytes, Dict[str, Any]]:
        """자동 형식 감지 파일 읽기"""
        file_path = Path(file_path)
        file_type = self._detect_file_type(file_path)
        
        if file_type == FileType.JSON:
            return self.read_json(file_path, encoding, use_cache)
        elif file_type == FileType.YAML:
            return self.read_yaml(file_path, encoding, use_cache)
        elif file_type == FileType.TEXT:
            return self.read_text(file_path, encoding, use_cache)
        elif file_type == FileType.BINARY:
            return self.read_binary(file_path, use_cache)
        else:
            # 기본값은 텍스트
            return self.read_text(file_path, encoding, use_cache)
    
    def write_text(
        self,
        file_path: Union[str, Path],
        content: str,
        encoding: Optional[str] = None,
        create_backup: bool = True
    ) -> None:
        """텍스트 파일 쓰기"""
        file_path = Path(file_path)
        encoding = encoding or self.config.default_encoding
        
        # 디렉토리 생성
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 백업 생성
        if create_backup and file_path.exists():
            self._create_backup(file_path)
        
        try:
            self._atomic_write(file_path, content, encoding)
            
            # 캐시 업데이트
            self.cache.set(file_path, FileType.TEXT, content)
        except Exception as e:
            raise FileError(f"텍스트 파일 쓰기 오류: {e}", file_path, e)
    
    def write_binary(
        self,
        file_path: Union[str, Path],
        content: bytes,
        create_backup: bool = True
    ) -> None:
        """바이너리 파일 쓰기"""
        file_path = Path(file_path)
        
        # 디렉토리 생성
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 백업 생성
        if create_backup and file_path.exists():
            self._create_backup(file_path)
        
        try:
            self._atomic_write(file_path, content, "utf-8")
            
            # 캐시 업데이트
            self.cache.set(file_path, FileType.BINARY, content)
        except Exception as e:
            raise FileError(f"바이너리 파일 쓰기 오류: {e}", file_path, e)
    
    def write_json(
        self,
        file_path: Union[str, Path],
        data: Dict[str, Any],
        encoding: Optional[str] = None,
        indent: int = 2,
        create_backup: bool = True
    ) -> None:
        """JSON 파일 쓰기"""
        file_path = Path(file_path)
        encoding = encoding or self.config.default_encoding
        
        try:
            content = json.dumps(data, indent=indent, ensure_ascii=False)
            self.write_text(file_path, content, encoding, create_backup)
            
            # 캐시 업데이트
            self.cache.set(file_path, FileType.JSON, data)
        except Exception as e:
            raise FileError(f"JSON 파일 쓰기 오류: {e}", file_path, e)
    
    def write_yaml(
        self,
        file_path: Union[str, Path],
        data: Dict[str, Any],
        encoding: Optional[str] = None,
        create_backup: bool = True
    ) -> None:
        """YAML 파일 쓰기"""
        file_path = Path(file_path)
        encoding = encoding or self.config.default_encoding
        
        try:
            from src.core.data_parser import dump_yaml
            content = dump_yaml(data)
            self.write_text(file_path, content, encoding, create_backup)
            
            # 캐시 업데이트
            self.cache.set(file_path, FileType.YAML, data)
        except Exception as e:
            raise FileError(f"YAML 파일 쓰기 오류: {e}", file_path, e)
    
    def copy_file(
        self,
        src_path: Union[str, Path],
        dst_path: Union[str, Path],
        preserve_metadata: bool = True
    ) -> None:
        """파일 복사"""
        src_path = Path(src_path)
        dst_path = Path(dst_path)
        
        if not src_path.exists():
            raise FileError(f"소스 파일이 존재하지 않습니다: {src_path}", src_path)
        
        # 대상 디렉토리 생성
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            if preserve_metadata:
                shutil.copy2(src_path, dst_path)
            else:
                shutil.copy(src_path, dst_path)
        except Exception as e:
            raise FileError(f"파일 복사 오류: {e}", src_path, e)
    
    def move_file(
        self,
        src_path: Union[str, Path],
        dst_path: Union[str, Path]
    ) -> None:
        """파일 이동"""
        src_path = Path(src_path)
        dst_path = Path(dst_path)
        
        if not src_path.exists():
            raise FileError(f"소스 파일이 존재하지 않습니다: {src_path}", src_path)
        
        # 대상 디렉토리 생성
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            shutil.move(str(src_path), str(dst_path))
        except Exception as e:
            raise FileError(f"파일 이동 오류: {e}", src_path, e)
    
    def delete_file(self, file_path: Union[str, Path]) -> None:
        """파일 삭제"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            return
        
        try:
            file_path.unlink()
            
            # 캐시에서 제거
            for file_type in FileType:
                self.cache._cache.pop(self.cache._generate_key(file_path, file_type), None)
        except Exception as e:
            raise FileError(f"파일 삭제 오류: {e}", file_path, e)
    
    def get_file_info(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """파일 정보 조회"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileError(f"파일이 존재하지 않습니다: {file_path}", file_path)
        
        stat = file_path.stat()
        return {
            "path": str(file_path),
            "name": file_path.name,
            "size": stat.st_size,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "accessed": stat.st_atime,
            "is_file": file_path.is_file(),
            "is_dir": file_path.is_dir(),
            "suffix": file_path.suffix,
            "stem": file_path.stem
        }
    
    def list_files(
        self,
        directory: Union[str, Path],
        pattern: str = "*",
        recursive: bool = False
    ) -> List[Path]:
        """파일 목록 조회"""
        directory = Path(directory)
        
        if not directory.exists():
            raise FileError(f"디렉토리가 존재하지 않습니다: {directory}", directory)
        
        if not directory.is_dir():
            raise FileError(f"디렉토리가 아닙니다: {directory}", directory)
        
        try:
            if recursive:
                return list(directory.rglob(pattern))
            else:
                return list(directory.glob(pattern))
        except Exception as e:
            raise FileError(f"파일 목록 조회 오류: {e}", directory, e)
    
    def clear_cache(self) -> None:
        """캐시 정리"""
        self.cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 조회"""
        return self.cache.get_stats()

# ===== [06] SINGLETON PATTERN ================================================
_file_manager_instance: Optional[FileManager] = None

def get_file_manager() -> FileManager:
    """파일 매니저 싱글톤 인스턴스 반환"""
    global _file_manager_instance
    if _file_manager_instance is None:
        _file_manager_instance = FileManager()
    return _file_manager_instance

# ===== [07] CONVENIENCE FUNCTIONS ============================================
def read_text_file(file_path: Union[str, Path], **kwargs) -> str:
    """텍스트 파일 읽기 편의 함수"""
    return get_file_manager().read_text(file_path, **kwargs)

def read_binary_file(file_path: Union[str, Path], **kwargs) -> bytes:
    """바이너리 파일 읽기 편의 함수"""
    return get_file_manager().read_binary(file_path, **kwargs)

def read_json_file(file_path: Union[str, Path], **kwargs) -> Dict[str, Any]:
    """JSON 파일 읽기 편의 함수"""
    return get_file_manager().read_json(file_path, **kwargs)

def read_yaml_file(file_path: Union[str, Path], **kwargs) -> Dict[str, Any]:
    """YAML 파일 읽기 편의 함수"""
    return get_file_manager().read_yaml(file_path, **kwargs)

def write_text_file(file_path: Union[str, Path], content: str, **kwargs) -> None:
    """텍스트 파일 쓰기 편의 함수"""
    get_file_manager().write_text(file_path, content, **kwargs)

def write_binary_file(file_path: Union[str, Path], content: bytes, **kwargs) -> None:
    """바이너리 파일 쓰기 편의 함수"""
    get_file_manager().write_binary(file_path, content, **kwargs)

def write_json_file(file_path: Union[str, Path], data: Dict[str, Any], **kwargs) -> None:
    """JSON 파일 쓰기 편의 함수"""
    get_file_manager().write_json(file_path, data, **kwargs)

def write_yaml_file(file_path: Union[str, Path], data: Dict[str, Any], **kwargs) -> None:
    """YAML 파일 쓰기 편의 함수"""
    get_file_manager().write_yaml(file_path, data, **kwargs)

# ===== [08] END ==============================================================
