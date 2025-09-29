# [01] START: src/runtime/prompts_loader.py — SSOT(prompts.yaml) 로더/강제 리로드/캐시/가시성
from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from urllib import request, error

try:
    import yaml  # PyYAML
except Exception as e:  # ruff: B904 - re-raise with context
    raise RuntimeError("PyYAML가 필요합니다. 의존성에 pyyaml을 추가하세요.") from e

# --- 환경설정(SSOT 기준) -------------------------------------------------------
# SSOT는 docs/_gpt/ 아래에 존재(Workspace Pointer·Conventions). 
OWNER = os.getenv("MAIC_GH_OWNER", "LEES1605")
REPO = os.getenv("MAIC_GH_REPO", "MAIC")
REF = os.getenv("MAIC_GH_REF", "main")  # 브랜치 또는 태그
PATH_ = os.getenv("MAIC_GH_PATH", "docs/_gpt/prompts.yaml")  # SSOT 경로
TOKEN = os.getenv("GITHUB_TOKEN", "")  # 읽기전용이면 충분(레이트리밋 완화)

TIMEOUT = float(os.getenv("MAIC_PROMPTS_TIMEOUT_SEC", "5"))
TTL_SEC = int(os.getenv("MAIC_PROMPTS_TTL_SEC", "600"))  # 캐시 TTL 10분

CACHE_DIR = Path(os.getenv("MAIC_PROMPTS_CACHE_DIR", ".maic_cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "prompts.yaml"
META_FILE = CACHE_DIR / "prompts.meta.json"

_REQUIRED = ("grammar", "sentence", "passage")
_last_load_ts: Optional[float] = None
_last_status: Dict[str, Any] = {
    "source": "init",
    "reason": "not_loaded",
    "etag": "",
    "sha": "",
    "ref": REF,
    "path": PATH_,
    "ts": 0,
    "schema_ok": False,
}

# --- 유틸 ----------------------------------------------------------------------
def _validate_schema(data: Dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ValueError("root must be mapping(dict)")
    modes = data.get("modes")
    if not isinstance(modes, dict):
        raise ValueError("'modes' must be mapping")
    for k in _REQUIRED:
        v = modes.get(k)
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"'modes.{k}' required and non-empty")

def _gh_headers() -> Dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "User-Agent": "maic-runtime/1"}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    return h

@dataclass
class FetchResult:
    text: str
    sha: str
    etag: str
    status: int

def _fetch_repo_file(etag: Optional[str], send_etag: bool) -> Optional[FetchResult]:
    """
    GitHub Contents API로 SSOT 파일을 조회.
    force=True일 때는 send_etag=False로 내려 304를 회피(항상 200 유도).
    """
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{PATH_}?ref={REF}"
    req = request.Request(url, headers=_gh_headers())
    if send_etag and etag:
        req.add_header("If-None-Match", etag)
    try:
        with request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            j = json.loads(body)
            text = base64.b64decode(j.get("content", "")).decode("utf-8")
            return FetchResult(
                text=text,
                sha=j.get("sha", ""),
                etag=resp.headers.get("ETag", ""),
                status=resp.status,
            )
    except error.HTTPError as e:
        if e.code == 304:  # Not Modified
            return None
        raise

# --- 공개 API -----------------------------------------------------------------
def debug_status() -> Dict[str, Any]:
    """마지막 로드의 출처/사유/sha/etag 등을 반환(관리자 패널에서 노출)."""
    return dict(_last_status)

def load_prompts(force: bool = False) -> Dict[str, Any]:
    """
    SSOT(prompts.yaml)를 로드한다.
    1) 원격(GitHub Contents API; ETag) → 2) 캐시 → 3) 내장 샘플
    - force=True일 때는 ETag를 보내지 않아 200 강제(즉시 최신 반영).
    - 반환값은 {'version': '...', 'modes': {...}} 딕셔너리.
    """
    global _last_load_ts, _last_status
    now = time.time()

    # 1) TTL 범위 내면 캐시 사용
    if (not force) and _last_load_ts and (now - _last_load_ts) < TTL_SEC and CACHE_FILE.exists():
        data = yaml.safe_load(CACHE_FILE.read_text(encoding="utf-8"))
        _validate_schema(data)
        _last_status.update({"source": "cache", "reason": "ttl_hit", "ts": now, "schema_ok": True})
        return {"version": str(data.get("version", "1")), "modes": data["modes"]}

    # 2) 원격 조회 시도
    etag = ""
    if META_FILE.exists():
        try:
            etag = json.loads(META_FILE.read_text(encoding="utf-8")).get("etag", "")
        except Exception:
            etag = ""

    try:
        fr = _fetch_repo_file(etag=etag or None, send_etag=not force)
        if fr is not None:  # 200
            CACHE_FILE.write_text(fr.text, encoding="utf-8")
            META_FILE.write_text(json.dumps({"etag": fr.etag, "sha": fr.sha}), encoding="utf-8")
            data = yaml.safe_load(fr.text)
            _validate_schema(data)
            _last_status.update(
                {"source": "repo", "reason": "200", "etag": fr.etag, "sha": fr.sha, "ts": now, "schema_ok": True}
            )
            _last_load_ts = now
            return {"version": str(data.get("version", "1")), "modes": data["modes"]}
        # 304 → 캐시 폴백
    except Exception as e:
        _last_status.update({"source": "repo", "reason": f"error:{e.__class__.__name__}", "ts": now, "schema_ok": False})

    # 3) 캐시 폴백
    if CACHE_FILE.exists():
        data = yaml.safe_load(CACHE_FILE.read_text(encoding="utf-8"))
        _validate_schema(data)
        _last_status.update({"source": "cache", "reason": "fallback", "ts": now, "schema_ok": True})
        _last_load_ts = now
        return {"version": str(data.get("version", "1")), "modes": data["modes"]}

    # 4) 내장 샘플 폴백
    fb = Path("docs/_gpt/prompts.sample.yaml")
    if fb.exists():
        data = yaml.safe_load(fb.read_text(encoding="utf-8"))
        _validate_schema(data)
        _last_status.update({"source": "builtin", "reason": "fallback", "ts": now, "schema_ok": True})
        _last_load_ts = now
        return {"version": str(data.get("version", "1")), "modes": data["modes"]}

    _last_status.update({"source": "none", "reason": "no_source", "ts": now, "schema_ok": False})
    raise RuntimeError("No prompts available (remote/cache/fallback all failed)")
# [01] END: src/runtime/prompts_loader.py
