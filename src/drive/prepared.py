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
from typing import Any, Dict, List, Set


__all__ = [
    "check_prepared_updates",
    "mark_prepared_consumed",
]


# ------------------------------- 내부 유틸 -------------------------------

def _seen_store_path(persist_dir: str | Path) -> Path:
    return Path(persist_dir).expanduser() / "prepared.seen.json"


def _load_seen(persist_dir: str | Path) -> Set[str]:
    import json

    p = _seen_store_path(persist_dir)
    if not p.exists():
        return set()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return set(str(x) for x in data)
    except Exception:
        pass
    return set()


def _save_seen(persist_dir: str | Path, seen: Set[str]) -> None:
    import json

    p = _seen_store_path(persist_dir)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # 저장 실패는 치명적이지 않음(다음 점검에서 다시 신규로 잡힐 뿐)
        pass


def _extract_id(rec: Dict[str, Any] | str) -> str:
    """
    files 항목에서 식별자 추출:
    - dict: id → fileId → name → path
    - str : 자체가 식별자
    - 그 외: 빈 문자열
    """
    if isinstance(rec, str):
        return rec.strip()
    if isinstance(rec, dict):
        for k in ("id", "fileId", "name", "path"):
            v = rec.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return ""


def _list_prepared_files_safe() -> List[Dict[str, Any]]:
    """
    src.integrations.gdrive.list_prepared_files() 가 있으면 호출,
    없으면 빈 목록 반환(안전 폴백).
    """
    try:
        import importlib

        mod = importlib.import_module("src.integrations.gdrive")
        lf = getattr(mod, "list_prepared_files", None)
        if callable(lf):
            out = lf() or []
            return out if isinstance(out, list) else []
    except Exception:
        pass
    return []


# ----------------------------- 공개 API ------------------------------

def check_prepared_updates(persist_dir: str | Path) -> Dict[str, Any]:
    """
    반환 스키마:
    {
      "driver": "drive",
      "total": <전체 파일 수>,
      "new":   <신규 파일 수>,
      "files": [<신규 식별자(str)>...]
    }
    """
    files: List[Dict[str, Any]] = _list_prepared_files_safe()
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


def mark_prepared_consumed(persist_dir: str | Path, files: List[Dict[str, Any]] | List[str]) -> None:
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
