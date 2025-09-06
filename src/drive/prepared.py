# =============================== [FILE: src/drive/prepared.py] — START ===============================
# src/drive/prepared.py
# -----------------------------------------------------------------------------
# Google Drive의 prepared 폴더만을 **단일 소스**로 가정한 어댑터.
# 앱 측에서 요구하는 표준 인터페이스:
#   - check_prepared_updates(persist_dir) -> dict
#   - mark_prepared_consumed(persist_dir, files: list[dict] | list[str]) -> None
#
# 동작 개요
# - src.integrations.gdrive.list_prepared_files() 를 통해 전체 파일 목록을 얻는다.
# - persist_dir/prepared.seen.json 파일에 '이미 소비(seen)한 파일 식별자'를 저장/조회한다.
# - 식별자 우선순위: id → fileId → name → path
# -----------------------------------------------------------------------------

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import json
import re

# -----------------------------------------------------------------------------
# 내부 유틸
# -----------------------------------------------------------------------------

def _persist_path(persist_dir: str | Path) -> Path:
    """
    prepared.seen.json 저장 위치를 반환
    """
    p = Path(persist_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p / "prepared.seen.json"


def _load_seen(persist_dir: str | Path) -> Set[str]:
    """
    이미 소비한 prepared 파일의 식별자 집합을 로드
    """
    fp = _persist_path(persist_dir)
    if not fp.exists():
        return set()
    try:
        data = json.loads(fp.read_text(encoding="utf-8") or "[]")
        if isinstance(data, list):
            return set(map(str, data))
    except Exception:
        # 손상되었거나 포맷이 바뀐 경우 초기화
        return set()
    return set()


def _save_seen(persist_dir: str | Path, seen: Set[str]) -> None:
    """
    소비한 식별자 집합을 저장
    """
    fp = _persist_path(persist_dir)
    fp.write_text(json.dumps(sorted(seen)), encoding="utf-8")


def _extract_id(rec: Any) -> Optional[str]:
    """
    dict/str 혼용 입력에서 식별자(id/fileId/name/path) 하나를 문자열로 추출
    우선순위: id → fileId → name → path
    """
    if rec is None:
        return None
    if isinstance(rec, str):
        # 경로나 파일명일 수 있음
        s = rec.strip()
        return s or None
    if isinstance(rec, dict):
        for k in ("id", "fileId", "name", "path"):
            if k in rec and rec[k]:
                v = str(rec[k]).strip()
                if v:
                    return v
    return None


# -----------------------------------------------------------------------------
# 공개 API: check_prepared_updates / mark_prepared_consumed
# -----------------------------------------------------------------------------

def check_prepared_updates(persist_dir: str | Path, files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    prepared 폴더 목록(files)과 persist_dir 상태를 비교하여,
    새로 유입된 항목 리스트를 반환한다.
    """
    seen: Set[str] = _load_seen(persist_dir)

    new_ids: List[str] = []
    for rec in files:
        fid = _extract_id(rec)
        if fid and fid not in seen:
            new_ids.append(fid)

    return {
        "driver": "drive",
        "total": len(files),
        "new": len(new_ids),
        "files": new_ids,
    }


def mark_prepared_consumed(
    persist_dir: str | Path,
    files: List[Dict[str, Any]] | List[str],
) -> None:
    """
    files: list[dict] | list[str]
    dict/str 혼용 입력을 모두 수용하며, _extract_id()로 식별자를 추출하여 seen에 추가한다.
    """
    seen: Set[str] = _load_seen(persist_dir)

    if isinstance(files, list):
        for rec in files:
            fid = _extract_id(rec)
            if fid:
                seen.add(fid)

    _save_seen(persist_dir, seen)
# =============================== [FILE: src/drive/prepared.py] — END ===============================
