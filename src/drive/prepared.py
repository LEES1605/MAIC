# ============================== [01] prepared-check API — START ==============================
"""
prepared 폴더 신규 파일 검사 (Drive 우선, Local 폴백).

- 공개 API
  * check_prepared_updates(persist_dir) -> dict
      반환 예:
        {
          "status": "UPDATED" | "NO_UPDATES" | "CHECK_FAILED",
          "has_updates": bool,
          "count": int,              # 전체 파일 수
          "newest_ts": int,          # 최신 수정시각(epoch sec)
          "files": [ {...} ],        # 미리보기 최대 20개
          "new_ids": [ ... ],        # 변경/신규로 판정된 id/name 목록
          "cache_path": "...",       # prepared_seen.json 경로
          "error": "..."?,           # (실패 시) 에러 메시지
        }
  * mark_prepared_consumed(persist_dir, files) -> None
      재인덱싱/복구에 반영된 파일들의 modified_ts를 캐시에 반영(본 것으로 마킹)

- 동작 원리
  1) 우선 시도: src.integrations.gdrive.list_prepared_files()
     - 반환 형식: [{"id": "...", "name": "...", "modified_ts": 1725000000, "size": 1234?}, ...]
  2) 실패/미구현 시: 로컬 폴더 폴백
     - 기본 위치: env MAIC_PREPARED_DIR 또는 ~/.maic/prepared
     - 파일 메타: {"id": <path or name>, "name": <name>, "modified_ts": <mtime>, "size": <bytes>}

- 변경점
  * 기존 인터페이스/필드/상태(status) 완전 호환
  * CHECK_FAILED를 줄이기 위해 로컬 폴더 폴백 추가
  * files 미리보기를 최대한 채워 UI가 cards를 띄울 수 있게 함
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Dict, Tuple
import json
import time
import importlib
import os

# ---------- 캐시 파일 ----------
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


# ---------- 드라이브 드라이버 ----------
def _list_from_drive() -> Tuple[List[Dict[str, Any]], bool, str]:
    """
    Drive 목록 시도.
    반환: (files, ok, error)
    files 예: [{"id":"...","name":"doc.md","modified_ts":1725..., "size":1234?}, ...]
    """
    try:
        mod = importlib.import_module("src.integrations.gdrive")
        fn = getattr(mod, "list_prepared_files", None)
        if callable(fn):
            out = fn()
            if isinstance(out, list):
                # 최소 필드 보정
                norm: List[Dict[str, Any]] = []
                for f in out:
                    if not isinstance(f, dict):
                        continue
                    fid = str(f.get("id") or f.get("name") or "")
                    name = str(f.get("name") or fid)
                    mts = int(f.get("modified_ts") or 0)
                    size = int(f.get("size") or 0)
                    if fid:
                        norm.append({"id": fid, "name": name, "modified_ts": mts, "size": size})
                return norm, True, ""
            return [], False, "unexpected return type from list_prepared_files()"
        return [], False, "function list_prepared_files() not found"
    except Exception as e:
        return [], False, f"{type(e).__name__}: {e}"


# ---------- 로컬 폴더 폴백 ----------
def _prepared_dir() -> Path:
    root = os.getenv("MAIC_PREPARED_DIR")
    if root and root.strip():
        return Path(root).expanduser()
    return Path.home() / ".maic" / "prepared"


def _list_from_local() -> Tuple[List[Dict[str, Any]], bool, str]:
    """
    로컬 prepared 폴더(최상위 한 단계)만 스캔.
    반환: (files, ok, error)
    """
    try:
        root = _prepared_dir()
        if not root.exists() or not root.is_dir():
            return [], True, ""  # 폴더 없음 = ok(파일 0개)
        out: List[Dict[str, Any]] = []
        for p in root.iterdir():
            if not p.is_file():
                continue
            try:
                st = p.stat()
                out.append(
                    {
                        "id": str(p),               # 캐시 키로 충분
                        "name": p.name,
                        "modified_ts": int(st.st_mtime),
                        "size": int(st.st_size),
                    }
                )
            except Exception:
                continue
        return out, True, ""
    except Exception as e:
        return [], False, f"{type(e).__name__}: {e}"


# ---------- 공개 API ----------
def check_prepared_updates(persist_dir: Path | str) -> Dict[str, Any]:
    """
    신규 파일/변경 파일이 있으면 status="UPDATED"와 함께 목록 일부를 반환.
    실패 시 status="CHECK_FAILED".
    변경 없음이면 status="NO_UPDATES".
    """
    base = Path(persist_dir).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    cache = _cache_path(base)
    seen_db = _load_seen(cache)
    seen_map = seen_db.get("seen", {}) or {}

    # 1) 드라이브 시도 → 2) 로컬 폴백
    files, ok, err = _list_from_drive()
    driver = "drive"
    if not ok:
        files, ok_local, err_local = _list_from_local()
        driver = "local"
        ok = ok_local
        err = err_local if err_local else err

    latest_ts = 0
    has_updates = False
    new_ids: List[str] = []

    # 변경 판정
    for f in files:
        fid = str(f.get("id") or f.get("name") or "")
        mts = int(f.get("modified_ts") or 0)
        latest_ts = max(latest_ts, mts)
        prev = int(seen_map.get(fid) or 0)
        if mts > prev:
            has_updates = True
            new_ids.append(fid)

    # 캐시: 검사 시점만 기록(소비 반영은 mark_prepared_consumed에서)
    seen_db["checked_at"] = _now_ts()
    _save_seen(cache, seen_db)

    status = "UPDATED" if has_updates else ("NO_UPDATES" if ok else "CHECK_FAILED")
    out = {
        "status": status,
        "has_updates": bool(has_updates),
        "count": int(len(files)),
        "newest_ts": int(latest_ts),
        "files": files[:20],     # 미리보기 최대 20개
        "new_ids": new_ids,
        "cache_path": str(cache),
        "driver": driver,
    }
    if not ok:
        out["error"] = err
    return out


def mark_prepared_consumed(persist_dir: Path | str, files: List[Dict[str, Any]]) -> None:
    """
    재인덱싱/복구 등으로 반영 완료 후, 현재 파일들의 modified_ts를 '본 것으로(seen)' 마킹.
    """
    base = Path(persist_dir).expanduser()
    cache = _cache_path(base)
    seen_db = _load_seen(cache)
    seen_map = seen_db.get("seen", {}) or {}
    for f in files or []:
        fid = str(f.get("id") or f.get("name") or "")
        mts = int(f.get("modified_ts") or 0)
        if fid:
            # 더 최신 값으로 갱신
            prev = int(seen_map.get(fid) or 0)
            seen_map[fid] = max(prev, mts)
    seen_db["seen"] = seen_map
    seen_db["checked_at"] = _now_ts()
    _save_seen(cache, seen_db)
# =============================== [01] prepared-check API — END ===============================
