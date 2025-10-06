"""
MAIC 인덱싱 서비스 모듈

app.py에서 분리된 인덱싱 관련 로직을 담당합니다.
- 인덱싱 상태 관리
- 파일 해시 계산
- 새 파일 스캔
- prepared API 로딩
"""

import json
import time
import importlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable

from src.infrastructure.core.persist import effective_persist_dir


class IndexingService:
    """인덱싱 관련 서비스 클래스"""
    
    def __init__(self):
        self._persist_dir = None
        self._indexing_state_file = None
    
    @property
    def persist_dir(self) -> Path:
        """안전한 persist 디렉토리 경로"""
        if self._persist_dir is None:
            try:
                self._persist_dir = Path(str(effective_persist_dir())).expanduser()
            except Exception:
                self._persist_dir = Path.home() / ".maic" / "persist"
        return self._persist_dir
    
    @property
    def indexing_state_file(self) -> Path:
        """인덱싱 상태 파일 경로"""
        if self._indexing_state_file is None:
            self._indexing_state_file = self.persist_dir / ".indexing_state.json"
        return self._indexing_state_file
    
    def load_indexing_state(self) -> Dict[str, Any]:
        """인덱싱 상태 로드"""
        try:
            if self.indexing_state_file.exists():
                with open(self.indexing_state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {"indexed_files": {}, "last_scan_time": None}
    
    def save_indexing_state(self, state: Dict[str, Any]) -> None:
        """인덱싱 상태 저장"""
        try:
            self.indexing_state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.indexing_state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def get_file_hash(self, file_path: Path) -> str:
        """파일 해시값 계산"""
        try:
            import hashlib
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return ""
    
    def get_new_files_to_index(self, source_dir: Path) -> List[Path]:
        """새로 인덱싱해야 할 파일들만 반환"""
        state = self.load_indexing_state()
        indexed_files = state.get("indexed_files", {})
        new_files = []
        
        try:
            for file_path in source_dir.rglob("*"):
                if file_path.is_file():
                    file_str = str(file_path)
                    file_hash = self.get_file_hash(file_path)
                    
                    # 파일이 새로 추가되었거나 수정된 경우
                    if file_str not in indexed_files or indexed_files[file_str] != file_hash:
                        new_files.append(file_path)
                        
            print(f"[DEBUG] Found {len(new_files)} new/modified files to index")
            return new_files
        except Exception as e:
            print(f"[DEBUG] Error scanning for new files: {e}")
            return []
    
    def update_indexing_state(self, new_files: List[Path]) -> None:
        """인덱싱 상태 업데이트"""
        state = self.load_indexing_state()
        indexed_files = state.get("indexed_files", {})
        
        for file_path in new_files:
            file_str = str(file_path)
            file_hash = self.get_file_hash(file_path)
            indexed_files[file_str] = file_hash
        
        state["indexed_files"] = indexed_files
        state["last_scan_time"] = time.time()
        self.save_indexing_state(state)
        print(f"[DEBUG] Updated indexing state with {len(new_files)} files")
    
    def load_prepared_lister(self) -> Tuple[Optional[Callable], List[str]]:
        """prepared 파일 리스터 로딩"""
        tried: List[str] = []

        def _try(modname: str):
            try:
                m = importlib.import_module(modname)
                fn = getattr(m, "list_prepared_files", None)
                if callable(fn):
                    tried.append(f"ok: {modname}")
                    return fn
                tried.append(f"miss func: {modname}")
                return None
            except Exception as e:
                tried.append(f"fail: {modname} ({e})")
                return None

        for name in ("src.integrations.gdrive", "gdrive"):
            fn = _try(name)
            if fn:
                return fn, tried
        return None, tried
    
    def load_prepared_api(self) -> Tuple[Optional[Callable], Optional[Callable], List[str]]:
        """prepared API 로딩"""
        tried: List[str] = []

        def _try(modname: str):
            try:
                m = importlib.import_module(modname)
                chk_fn = getattr(m, "check_prepared_updates", None)
                mark_fn = getattr(m, "mark_prepared_consumed", None)
                if callable(chk_fn) and callable(mark_fn):
                    tried.append(f"ok: {modname}")
                    return chk_fn, mark_fn
                tried.append(f"miss attrs: {modname}")
                return None, None
            except Exception as e:
                tried.append(f"fail: {modname} ({e})")
                return None, None

        for name in ("prepared", "gdrive", "src.prepared", "src.drive.prepared", "src.integrations.gdrive"):
            chk, mark = _try(name)
            if chk and mark:
                return chk, mark, tried
        return None, None, tried


# 전역 인스턴스
indexing_service = IndexingService()


# 편의 함수들 (기존 app.py와의 호환성을 위해)
def _persist_dir_safe() -> Path:
    """안전한 persist 디렉토리 경로"""
    return indexing_service.persist_dir


def _get_indexing_state_file() -> Path:
    """인덱싱 상태 파일 경로"""
    return indexing_service.indexing_state_file


def _load_indexing_state() -> Dict[str, Any]:
    """인덱싱 상태 로드"""
    return indexing_service.load_indexing_state()


def _save_indexing_state(state: Dict[str, Any]) -> None:
    """인덱싱 상태 저장"""
    indexing_service.save_indexing_state(state)


def _get_file_hash(file_path: Path) -> str:
    """파일 해시값 계산"""
    return indexing_service.get_file_hash(file_path)


def _get_new_files_to_index(source_dir: Path) -> List[Path]:
    """새로 인덱싱해야 할 파일들만 반환"""
    return indexing_service.get_new_files_to_index(source_dir)


def _update_indexing_state(new_files: List[Path]) -> None:
    """인덱싱 상태 업데이트"""
    indexing_service.update_indexing_state(new_files)


def _load_prepared_lister():
    """prepared 파일 리스터 로딩"""
    return indexing_service.load_prepared_lister()


def _load_prepared_api():
    """prepared API 로딩"""
    return indexing_service.load_prepared_api()
