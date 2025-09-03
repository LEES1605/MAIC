# ============================== [01] prepared-check API — START ==============================
"""
prepared 폴더 신규 파일 검사.
- check_prepared_updates(persist_dir) → {
    status: "UPDATED" | "NO_UPDATES" | "CHECK_FAILED",
    has_updates, count, newest_ts, files, new_ids, cache_path, error?
  }
- src.integrations.gdrive.list_prepared_files()가 있으면 사용, 없으면 빈 리스트 폴백.
- 마지막 본 상태를 persist_dir/prepared_seen.json에 저장해 증분 판단.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, List, Dict, Tuple
import json
import time


def _cache_path(persist_dir: Path) -> Path:
    return persist_dir / "prepared_seen.json"


def _now_ts() -> int:
    return int(time.time())


def _load_seen(p: Path) -> Dict[str, Any]:
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"seen": {}, "checked_at": 0}


def _save_seen(p: Path, data: Dict[str, Any]) -> None:
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _list_prepared_files_safe() -> Tuple[List[Dict[str, Any]], bool, str]:
    """
    반환: (files, ok, error_msg)
      - files 예: [{ "id": "fileId", "name": "doc.md", "modified_ts": 1725000000 }, ...]
    """
    try:
        import importlib

        mod = importlib.import_module("src.integrations.gdrive")
        fn = getattr(mod, "list_prepared_files", None)
        if callable(fn):
            out = fn()
            if isinstance(out, list):
                return out, True, ""
            return [], False, "unexpected return type from list_prepared_files()"
        return [], False, "function list_prepared_files() not found"
    except Exception as e:
        return [], False, f"{type(e).__name__}: {e}"


def check_prepared_updates(persist_dir: Path | str) -> Dict[str, Any]:
    base = Path(persist_dir).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    cache = _cache_path(base)
    seen_db = _load_seen(cache)

    files, ok, err = _list_prepared_files_safe()
    latest_ts = 0
    has_updates = False
    new_ids = []

    seen_map = seen_db.get("seen", {})
    for f in files:
        fid = str(f.get("id") or f.get("name") or "")
        mts = int(f.get("modified_ts") or 0)
        latest_ts = max(latest_ts, mts)
        prev = int(seen_map.get(fid) or 0)
        if mts > prev:
            has_updates = True
            new_ids.append(fid)

    # 캐시: 검사 시점 기록(실제 반영 시점은 호출자가 mark_prepared_consumed로 저장)
    seen_db["checked_at"] = _now_ts()
    _save_seen(cache, seen_db)

    status = "UPDATED" if has_updates else ("NO_UPDATES" if ok else "CHECK_FAILED")
    out = {
        "status": status,
        "has_updates": bool(has_updates),
        "count": int(len(files)),
        "newest_ts": int(latest_ts),
        "files": files[:20],  # 미리보기 최대 20개
        "new_ids": new_ids,
        "cache_path": str(cache),
    }
    if not ok:
        out["error"] = err
    return out


def mark_prepared_consumed(persist_dir: Path | str, files: List[Dict[str, Any]]) -> None:
    """
    재인덱싱/복구 등으로 반영 완료 후, 현재 파일들의 modified_ts를 '본 것으로' 마킹.
    """
    base = Path(persist_dir).expanduser()
    cache = _cache_path(base)
    seen_db = _load_seen(cache)
    seen_map = seen_db.get("seen", {})
    for f in files:
        fid = str(f.get("id") or f.get("name") or "")
        mts = int(f.get("modified_ts") or 0)
        if fid:
            seen_map[fid] = max(int(seen_map.get(fid) or 0), mts)
    seen_db["seen"] = seen_map
    seen_db["checked_at"] = _now_ts()
    _save_seen(cache, seen_db)
# =============================== [01] prepared-check API — END ===============================
