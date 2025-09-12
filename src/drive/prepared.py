# src/drive/prepared.py
# -----------------------------------------------------------------------------
# Prepared 소비(Seen) SSOT
# - check_prepared_updates(persist_dir, files=None) -> dict
# - mark_prepared_consumed(persist_dir, files) -> None
#
# 강화 포인트
# 1) 원자적 저장(임시파일 → os.replace)
# 2) 대용량 안전(최대 엔트리 초과 시 오래된 항목 정리)
# 3) 입력 유연성(list[dict|str])과 하위호환(json 배열/대체 파일명) 지원
# 4) files=None이면 동적 임포트로 list_prepared_files() 호출(하위호환)
# -----------------------------------------------------------------------------

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import json
import os
import time
import importlib

# 파일명: 기존과 동일(점(.) 없는 이름) 사용
# - 과거 일부 분기에서 ".prepared_seen.json" 을 쓴 적이 있어, 읽기 시 폴백 허용
_SEEN_NAME_PRIMARY = "prepared.seen.json"
_SEEN_NAME_ALT = ".prepared_seen.json"
_MAX_ENTRIES = 20_000


def _persist_path(persist_dir: str | Path) -> Path:
    p = Path(persist_dir).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p / _SEEN_NAME_PRIMARY


def _read_json_any(path: Path) -> Any:
    try:
        if path.exists() and path.stat().st_size > 0:
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def _load_seen_db(persist_dir: str | Path) -> Dict[str, Dict[str, Any]]:
    """
    seen DB 로드.
    - 신포맷: {"<id>": {"name": "...", "ts": 1725000000}}
    - 구포맷: ["id1", "id2", ...]  → {"id1": {"name":"", "ts":0}, ...}
    - 대체 파일명도 읽기 폴백
    """
    primary = _persist_path(persist_dir)
    alt = primary.with_name(_SEEN_NAME_ALT)

    data = _read_json_any(primary)
    if data is None:
        data = _read_json_any(alt)

    seen: Dict[str, Dict[str, Any]] = {}
    if isinstance(data, dict):
        # 이미 신포맷
        for k, v in data.items():
            if not isinstance(v, dict):
                v = {}
            name = str(v.get("name") or "")
            ts = int(v.get("ts") or 0)
            seen[str(k)] = {"name": name, "ts": ts}
        return seen

    if isinstance(data, list):
        # 구포맷 배열 → 신포맷으로 승격
        for item in data:
            fid = str(item).strip()
            if fid:
                seen[fid] = {"name": "", "ts": 0}
        return seen

    return {}


def _atomic_write_json(path: Path, obj: Dict[str, Dict[str, Any]]) -> None:
    try:
        tmp = path.with_suffix(path.suffix + ".tmp")
        txt = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        tmp.write_text(txt, encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        # 저장 실패는 무해화
        pass


def _extract_id_name(rec: Any) -> Tuple[str, str]:
    """
    dict/str 혼용 입력에서 (id, name) 추출.
    우선순위(id): id → fileId → name → path
    표시이름(name): name → path → file → id
    """
    if rec is None:
        return "", ""
    if isinstance(rec, str):
        s = rec.strip()
        return (s, s) if s else ("", "")
    if isinstance(rec, dict):
        # E731 회피: lambda 할당 대신 내부 함수 사용
        def _get(k: str) -> str:
            return str(rec.get(k) or "").strip()

        fid = _get("id") or _get("fileId") or _get("name") or _get("path")
        nm = _get("name") or _get("path") or _get("file") or fid
        return (fid, nm) if fid else ("", "")
    s = str(rec or "").strip()
    return (s, s) if s else ("", "")


def _prune_if_needed(db: Dict[str, Dict[str, Any]]) -> None:
    try:
        if len(db) <= _MAX_ENTRIES:
            return
        items = [(k, int(v.get("ts") or 0)) for k, v in db.items()]
        items.sort(key=lambda kv: kv[1])  # 오래된 것부터
        drop = len(items) - _MAX_ENTRIES
        for k, _ in items[:drop]:
            db.pop(k, None)
    except Exception:
        pass


def _dynamic_list() -> List[Dict[str, Any]]:
    """
    files 인자가 None일 때 동적 임포트로 prepared 목록 취득.
    - src.integrations.gdrive.list_prepared_files()
    - 또는 gdrive.list_prepared_files()
    """
    for modname in ("src.integrations.gdrive", "gdrive"):
        try:
            m = importlib.import_module(modname)
            fn = getattr(m, "list_prepared_files", None)
            if callable(fn):
                rows = fn() or []
                if isinstance(rows, list):
                    return rows
        except Exception:
            continue
    return []


# -----------------------------------------------------------------------------
# 공개 API
# -----------------------------------------------------------------------------
def check_prepared_updates(
    persist_dir: str | Path,
    files: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """
    prepared 목록과 persist_dir 상태를 비교하여 '새 파일' 목록을 계산.

    Args:
        persist_dir: 인덱스 persist 디렉토리
        files: list[dict|str] prepared 목록.
               None이면 동적으로 list_prepared_files() 호출(하위호환).
    Returns:
        {
          "driver": "drive",
          "total": 총 파일 수,
          "new": 새 파일 수,
          "files": ["id1", "id2", ...]  # 새 파일 id 리스트
        }
    """
    rows = files if isinstance(files, list) else _dynamic_list()
    total = len(rows)

    db = _load_seen_db(persist_dir)
    new_ids: List[str] = []

    for rec in rows:
        fid, _nm = _extract_id_name(rec)
        if not fid:
            continue
        if fid not in db:
            new_ids.append(fid)

    return {
        "driver": "drive",
        "total": total,
        "new": len(new_ids),
        "files": new_ids,
    }


def mark_prepared_consumed(
    persist_dir: str | Path,
    files: Iterable[Any],
) -> None:
    """
    전달된 파일들을 소비(Seen)로 기록.
    - 문자열/사전 혼용 지원
    - 이미 존재하면 ts/name 업데이트
    """
    path = _persist_path(persist_dir)
    db = _load_seen_db(persist_dir)
    now = int(time.time())

    for rec in files or []:
        fid, name = _extract_id_name(rec)
        if not fid:
            continue
        cur = db.get(fid) or {}
        nm = name or cur.get("name") or ""
        db[fid] = {"name": nm, "ts": now}

    _prune_if_needed(db)
    _atomic_write_json(path, db)
