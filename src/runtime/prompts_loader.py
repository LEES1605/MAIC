# [03] START: src/runtime/prompts_loader.py — SSOT(prompts.yaml) 로더 (지연 임포트/캐시/강제리로드)
from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from urllib import request, error

# yaml은 지연 임포트(테스트 수집 단계 즉사 방지)
try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # 런타임에서 필요 시 친절한 에러로 전환

# --- SSOT/환경설정 -------------------------------------------------------------
OWNER = os.getenv("MAIC_GH_OWNER", "LEES1605")
REPO = os.getenv("MAIC_GH_REPO", "MAIC")
REF = os.getenv("MAIC_GH_REF", "main")
PATH_ = os.getenv("MAIC_GH_PATH", "docs/_gpt/prompts.yaml")  # SSOT 파일 경로(고정) :contentReference[oaicite:4]{index=4}
TOKEN = os.getenv("GITHUB_TOKEN", "")

TIMEOUT = float(os.getenv("MAIC_PROMPTS_TIMEOUT_SEC", "5"))
TTL_SEC = int(os.getenv("MAIC_PROMPTS_TTL_SEC", "600"))

CACHE_DIR = Path(os.getenv("MAIC_PROMPTS_CACHE_DIR", ".maic_cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "prompts.yaml"
META_FILE = CACHE_DIR / "prompts.meta.json"

_REQUIRED = ("grammar", "sentence", "passage")
_last_load_ts: Optional[float] = None
_last_status: Dict[str, Any] = {
    "source": "init", "reason": "not_loaded", "etag": "", "sha": "",
    "ref": REF, "path": PATH_, "ts": 0, "schema_ok": False,
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

def _yaml_load(text: str) -> Dict[str, Any]:
    """
    1) PyYAML이 있으면 yaml.safe_load
    2) 없으면 JSON 시도(모든 JSON은 YAML 유효 → 최소 폴백)
    3) 여전히 안 되면 친절한 오류로 종료(설치 가이드)
    """
    if yaml is not None:
        return yaml.safe_load(text)
    try:
        return json.loads(text)
    except Exception as e:
        raise RuntimeError("YAML 파서(PyYAML)가 없습니다. CI/의존성에 'pyyaml>=6'을 추가하세요.") from e

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
                text=text, sha=j.get("sha", ""), etag=resp.headers.get("ETag", ""), status=resp.status
            )
    except error.HTTPError as e:
        if e.code == 304:
            return None
        raise

# --- 공개 API -----------------------------------------------------------------
def debug_status() -> Dict[str, Any]:
    return dict(_last_status)

def load_prompts(force: bool = False) -> Dict[str, Any]:
    """
    SSOT(prompts.yaml)를 로드:
    1) GitHub(ETag/If-None-Match; force=True면 미전송) → 2) 캐시 → 3) 내장 샘플
    반환: {'version': '...', 'modes': {...}}
    """
    global _last_load_ts, _last_status
    now = time.time()

    if (not force) and _last_load_ts and (now - _last_load_ts) < TTL_SEC and CACHE_FILE.exists():
        data = _yaml_load(CACHE_FILE.read_text(encoding="utf-8"))
        _validate_schema(data)
        _last_status.update({"source": "cache", "reason": "ttl_hit", "ts": now, "schema_ok": True})
        return {"version": str(data.get("version", "1")), "modes": data["modes"]}

    etag = ""
    if META_FILE.exists():
        try:
            etag = json.loads(META_FILE.read_text(encoding="utf-8")).get("etag", "")
        except Exception:
            etag = ""

    try:
        fr = _fetch_repo_file(etag=etag or None, send_etag=not force)
        if fr is not None:
            CACHE_FILE.write_text(fr.text, encoding="utf-8")
            META_FILE.write_text(json.dumps({"etag": fr.etag, "sha": fr.sha}), encoding="utf-8")
            data = _yaml_load(fr.text)
            _validate_schema(data)
            _last_status.update({"source": "repo", "reason": "200", "etag": fr.etag, "sha": fr.sha,
                                 "ts": now, "schema_ok": True})
            _last_load_ts = now
            return {"version": str(data.get("version", "1")), "modes": data["modes"]}
    except Exception as e:
        _last_status.update({"source": "repo", "reason": f"error:{e.__class__.__name__}", "ts": now, "schema_ok": False})

    if CACHE_FILE.exists():
        data = _yaml_load(CACHE_FILE.read_text(encoding="utf-8"))
        _validate_schema(data)
        _last_status.update({"source": "cache", "reason": "fallback", "ts": now, "schema_ok": True})
        _last_load_ts = now
        return {"version": str(data.get("version", "1")), "modes": data["modes"]}

    fb = Path("docs/_gpt/prompts.sample.yaml")
    if fb.exists():
        data = _yaml_load(fb.read_text(encoding="utf-8"))
        _validate_schema(data)
        _last_status.update({"source": "builtin", "reason": "fallback", "ts": now, "schema_ok": True})
        _last_load_ts = now
        return {"version": str(data.get("version", "1")), "modes": data["modes"]}

    _last_status.update({"source": "none", "reason": "no_source", "ts": now, "schema_ok": False})
    raise RuntimeError("No prompts available (remote/cache/fallback all failed)")
# [03] END: src/runtime/prompts_loader.py
