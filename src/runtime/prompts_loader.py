# [01] START: src/runtime/prompts_loader.py — SSOT 로더(로컬/원격·JSON/YAML·강제리로드·캐시)
from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from urllib import request, error

# yaml은 지연 임포트(수집 단계 즉사 방지). 없으면 JSON 폴백 시도 후 친절히 실패.
try:
    import yaml  # type: ignore
except Exception:
    yaml = None

# ---- SSOT/환경 기본값 ---------------------------------------------------------
# SSOT 루트: docs/_gpt/ (Workspace Pointer/Conventions) 
OWNER = os.getenv("MAIC_GH_OWNER", "LEES1605")
REPO = os.getenv("MAIC_GH_REPO", "MAIC")
REF = os.getenv("MAIC_GH_REF", "main")
PATH_ = os.getenv("MAIC_GH_PATH", "docs/_gpt/prompts.yaml")  # 원격 기본 경로
TOKEN = os.getenv("GITHUB_TOKEN", "")

TIMEOUT = float(os.getenv("MAIC_PROMPTS_TIMEOUT_SEC", "5"))
TTL_SEC = int(os.getenv("MAIC_PROMPTS_TTL_SEC", "600"))

CACHE_DIR = Path(os.getenv("MAIC_PROMPTS_CACHE_DIR", ".maic_cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "prompts.yaml"
META_FILE = CACHE_DIR / "prompts.meta.json"

_REQUIRED = ("grammar", "sentence", "passage")
PASSAGE_SKELETON = (
    "[지문] 작성 규칙:\n"
    "- \"요지/주제\"를 1~2문장으로 요약합니다.\n"
    "- \"쉬운 예시/비유\"로 학생 수준에 맞춘 설명을 제공합니다.\n"
    "- \"제목\"을 1개 제안합니다.\n"
    "- \"오답 포인트\"가 있으면 1~2개만 짚습니다.\n"
    "- \"근거/출처\"에 본문/사전/문법서 등 최소 1건을 남깁니다.\n"
)

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

# ---- 유틸 ---------------------------------------------------------------------
def _yaml_load(text: str) -> Dict[str, Any]:
    """PyYAML이 있으면 YAML, 없으면 JSON으로 파싱(모든 JSON은 YAML 유효)."""
    if yaml is not None:
        return yaml.safe_load(text)
    try:
        return json.loads(text)
    except Exception as e:
        raise RuntimeError("YAML 파서(PyYAML)가 없습니다. 의존성에 'pyyaml>=6'을 추가하세요.") from e

def _ensure_required_modes(data: Dict[str, Any], *, permissive: bool = False) -> Dict[str, Any]:
    """
    필수 키 보장. permissive=True이면 local 파일 로딩 시 'passage'가 비거나 없으면
    PASSAGE_SKELETON으로 보강(테스트 픽스처 호환성).
    """
    if not isinstance(data, dict):
        raise ValueError("root must be mapping(dict)")
    if "modes" not in data or not isinstance(data["modes"], dict):
        raise ValueError("missing 'modes' mapping")
    modes = data["modes"]
    if permissive and (not isinstance(modes.get("passage"), str) or not modes.get("passage", "").strip()):
        modes["passage"] = PASSAGE_SKELETON
    # 최종 검증(엄격)
    for k in _REQUIRED:
        v = modes.get(k)
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"'modes.{k}' required and non-empty")
    if "version" not in data:
        data["version"] = "1"
    return data

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

def _fetch_repo_file(owner: str, repo: str, ref: str, path: str, *, etag: Optional[str], send_etag: bool) -> Optional[FetchResult]:
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={ref}"
    req = request.Request(url, headers=_gh_headers())
    if send_etag and etag:
        req.add_header("If-None-Match", etag)
    try:
        with request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            j = json.loads(body)
            text = base64.b64decode(j.get("content", "")).decode("utf-8")
            return FetchResult(text=text, sha=j.get("sha", ""), etag=resp.headers.get("ETag", ""), status=resp.status)
    except error.HTTPError as e:
        if e.code == 304:
            return None
        raise

def debug_status() -> Dict[str, Any]:
    return dict(_last_status)

# ---- 공개 API -----------------------------------------------------------------
def load_prompts(
    force: bool = False,
    *,
    owner: Optional[str] = None,
    repo: Optional[str] = None,
    ref: Optional[str] = None,
    path: Optional[str] = None,
    local_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """
    SSOT 프롬프트 로더.
    우선순위: (1) local_path 명시 → (2) GitHub Contents(ETag/캐시/TTL) → (3) 캐시 → (4) 내장 샘플.
    - 테스트 호환: local_path가 주어지면 **그 파일(JSON/YAML)**을 직접 읽어 반환합니다.
    - 강제 리로드(force=True): If-None-Match 미전송 → 원격 200 강제.
    반환 형식: {'version': '1', 'modes': {'grammar': str, 'sentence': str, 'passage': str}}
    """
    global _last_load_ts, _last_status

    eff_owner = owner or OWNER
    eff_repo = repo or REPO
    eff_ref = ref or REF
    eff_path = path or PATH_

    now = time.time()

    # (1) local_path가 주어지면 로컬 우선(테스트 픽스처 경로: docs/_gpt/prompts.sample.json)
    if local_path is not None:
        p = Path(local_path)
        if not p.exists():
            raise FileNotFoundError(f"local_path not found: {p}")
        text = p.read_text(encoding="utf-8")
        data = _yaml_load(text)
        data = _ensure_required_modes(data, permissive=True)  # passage 보강 허용
        _last_status.update({"source": "local", "reason": "file", "path": str(p), "ts": now, "schema_ok": True})
        _last_load_ts = now
        return {"version": str(data.get("version", "1")), "modes": data["modes"]}

    # TTL 캐시
    if (not force) and _last_load_ts and (now - _last_load_ts) < TTL_SEC and CACHE_FILE.exists():
        data = _yaml_load(CACHE_FILE.read_text(encoding="utf-8"))
        data = _ensure_required_modes(data)
        _last_status.update({"source": "cache", "reason": "ttl_hit", "ts": now, "schema_ok": True})
        return {"version": str(data.get("version", "1")), "modes": data["modes"]}

    # (2) 원격 시도
    etag = ""
    if META_FILE.exists():
        try:
            etag = json.loads(META_FILE.read_text(encoding="utf-8")).get("etag", "")
        except Exception:
            etag = ""

    try:
        fr = _fetch_repo_file(eff_owner, eff_repo, eff_ref, eff_path, etag=etag or None, send_etag=not force)
        if fr is not None:  # 200
            CACHE_FILE.write_text(fr.text, encoding="utf-8")
            META_FILE.write_text(json.dumps({"etag": fr.etag, "sha": fr.sha}), encoding="utf-8")
            data = _yaml_load(fr.text)
            data = _ensure_required_modes(data)
            _last_status.update({"source": "repo", "reason": "200", "etag": fr.etag, "sha": fr.sha,
                                 "ref": eff_ref, "path": eff_path, "ts": now, "schema_ok": True})
            _last_load_ts = now
            return {"version": str(data.get("version", "1")), "modes": data["modes"]}
    except Exception as e:
        _last_status.update({"source": "repo", "reason": f"error:{e.__class__.__name__}", "ref": eff_ref,
                             "path": eff_path, "ts": now, "schema_ok": False})

    # (3) 캐시 폴백
    if CACHE_FILE.exists():
        data = _yaml_load(CACHE_FILE.read_text(encoding="utf-8"))
        data = _ensure_required_modes(data)
        _last_status.update({"source": "cache", "reason": "fallback", "ts": now, "schema_ok": True})
        _last_load_ts = now
        return {"version": str(data.get("version", "1")), "modes": data["modes"]}

    # (4) 내장 샘플 폴백(.yaml 우선, 없으면 .json도 시도)
    for fb in (Path("docs/_gpt/prompts.sample.yaml"), Path("docs/_gpt/prompts.sample.json")):
        if fb.exists():
            data = _yaml_load(fb.read_text(encoding="utf-8"))
            data = _ensure_required_modes(data, permissive=True)
            _last_status.update({"source": "builtin", "reason": "fallback", "path": str(fb), "ts": now, "schema_ok": True})
            _last_load_ts = now
            return {"version": str(data.get("version", "1")), "modes": data["modes"]}

    _last_status.update({"source": "none", "reason": "no_source", "ts": now, "schema_ok": False})
    raise RuntimeError("No prompts available (remote/cache/fallback all failed)")
# [01] END: src/runtime/prompts_loader.py
