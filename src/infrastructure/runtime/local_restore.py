# ===== [01] FILE: src/runtime/local_restore.py — START =====
"""
로컬 백업에서 인덱스 복원 기능

특징:
- 로컬 백업 디렉터리에서 chunks.jsonl 찾기
- persist 디렉터리로 복원
- .ready 파일 생성
- 세션 상태 업데이트
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from src.core.readiness import normalize_ready_file


def find_local_backups(backup_base_dir: Path) -> List[Path]:
    """로컬 백업 디렉터리에서 인덱스 백업 찾기"""
    backups = []
    
    if not backup_base_dir.exists():
        return backups
    
    # 일반적인 백업 디렉터리 패턴들
    backup_patterns = [
        "backup",
        "backups", 
        "index_backup",
        "persist_backup",
        "maic_backup"
    ]
    
    for pattern in backup_patterns:
        backup_dir = backup_base_dir / pattern
        if backup_dir.exists():
            # chunks.jsonl이 있는 디렉터리 찾기
            for item in backup_dir.rglob("chunks.jsonl"):
                if item.is_file() and item.stat().st_size > 0:
                    backups.append(item.parent)
    
    # 직접적인 백업 파일들도 찾기
    for item in backup_base_dir.rglob("*.tar.gz"):
        if "index" in item.name.lower() or "backup" in item.name.lower():
            backups.append(item)
    
    for item in backup_base_dir.rglob("*.zip"):
        if "index" in item.name.lower() or "backup" in item.name.lower():
            backups.append(item)
    
    return sorted(backups, key=lambda x: x.stat().st_mtime if x.exists() else 0, reverse=True)


def restore_from_local_backup(backup_path: Path, dest_dir: Path) -> Tuple[bool, str]:
    """로컬 백업에서 인덱스 복원"""
    try:
        # 대상 디렉터리 준비
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # 백업이 디렉터리인 경우
        if backup_path.is_dir():
            chunks_file = backup_path / "chunks.jsonl"
            if chunks_file.exists() and chunks_file.stat().st_size > 0:
                # chunks.jsonl 복사
                shutil.copy2(chunks_file, dest_dir / "chunks.jsonl")
                
                # 다른 관련 파일들도 복사
                for item in backup_path.iterdir():
                    if item.is_file() and item.name not in ["chunks.jsonl"]:
                        shutil.copy2(item, dest_dir / item.name)
                
                # .ready 파일 생성
                normalize_ready_file(dest_dir)
                
                return True, f"로컬 백업에서 복원 완료: {backup_path}"
            else:
                return False, f"백업 디렉터리에 chunks.jsonl이 없습니다: {backup_path}"
        
        # 백업이 압축 파일인 경우
        elif backup_path.suffix in ['.tar.gz', '.zip']:
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # 압축 해제
                if backup_path.suffix == '.tar.gz':
                    import tarfile
                    with tarfile.open(backup_path, 'r:gz') as tar:
                        tar.extractall(temp_path)
                elif backup_path.suffix == '.zip':
                    import zipfile
                    with zipfile.ZipFile(backup_path, 'r') as zip_file:
                        zip_file.extractall(temp_path)
                
                # chunks.jsonl 찾기
                chunks_file = None
                for item in temp_path.rglob("chunks.jsonl"):
                    if item.is_file() and item.stat().st_size > 0:
                        chunks_file = item
                        break
                
                if chunks_file:
                    # chunks.jsonl 복사
                    shutil.copy2(chunks_file, dest_dir / "chunks.jsonl")
                    
                    # 다른 관련 파일들도 복사
                    for item in chunks_file.parent.iterdir():
                        if item.is_file() and item.name not in ["chunks.jsonl"]:
                            shutil.copy2(item, dest_dir / item.name)
                    
                    # .ready 파일 생성
                    normalize_ready_file(dest_dir)
                    
                    return True, f"압축 백업에서 복원 완료: {backup_path}"
                else:
                    return False, f"압축 파일에 chunks.jsonl이 없습니다: {backup_path}"
        
        else:
            return False, f"지원하지 않는 백업 형식: {backup_path}"
    
    except (OSError, IOError, tarfile.TarError, zipfile.BadZipFile) as e:
        from src.shared.common.utils import errlog
        errlog(f"백업 복원 실패: {e}", "restore_from_local_backup", e)
        return False, f"로컬 복원 실패: {e}"
    except Exception as e:
        from src.shared.common.utils import errlog
        errlog(f"예상치 못한 복원 오류: {e}", "restore_from_local_backup", e)
        return False, f"로컬 복원 실패: {e}"


def get_backup_info(backup_path: Path) -> dict:
    """백업 정보 조회"""
    info = {
        "path": str(backup_path),
        "type": "directory" if backup_path.is_dir() else "archive",
        "size": 0,
        "modified": None,
        "chunks_size": 0
    }
    
    try:
        if backup_path.exists():
            info["size"] = backup_path.stat().st_size if backup_path.is_file() else sum(f.stat().st_size for f in backup_path.rglob('*') if f.is_file())
            info["modified"] = backup_path.stat().st_mtime
            
            # chunks.jsonl 크기 확인
            if backup_path.is_dir():
                chunks_file = backup_path / "chunks.jsonl"
                if chunks_file.exists():
                    info["chunks_size"] = chunks_file.stat().st_size
            else:
                # 압축 파일의 경우 추정치
                info["chunks_size"] = "압축됨"
    
    except Exception:
        pass
    
    return info


# ===== [01] FILE: src/runtime/local_restore.py — END =====
