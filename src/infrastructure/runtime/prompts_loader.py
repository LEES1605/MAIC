# [01] START: src/runtime/prompts_loader.py — SSOT 로더(문자열/객체 동시 허용 + permissive 보강)
from __future__ import annotations

import base64
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple
from urllib import request, error

from src.runtime.gh_release import GHReleases, GHError

# 지연 임포트: PyYAML 없을 때 테스트 수집 단계 즉사 방지
try:
    import yaml  # type: ignore
except Exception:
    yaml = None

# ---- SSOT/환경 기본값 ---------------------------------------------------------
# SSOT Root: docs/_gpt/ (Workspace Pointer/Conventions)  
OWNER = os.getenv("MAIC_GH_OWNER", "LEES1605")
REPO = os.getenv("MAIC_GH_REPO", "MAIC")
REF = os.getenv("MAIC_GH_REF", "main")
PATH_ = os.getenv("MAIC_GH_PATH", "docs/_gpt/prompts.yaml")
TOKEN = os.getenv("GITHUB_TOKEN", "")

TIMEOUT = float(os.getenv("MAIC_PROMPTS_TIMEOUT_SEC", "5"))
TTL_SEC = int(os.getenv("MAIC_PROMPTS_TTL_SEC", "600"))

CACHE_DIR = Path(os.getenv("MAIC_PROMPTS_CACHE_DIR", ".maic_cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "prompts.yaml"
META_FILE = CACHE_DIR / "prompts.meta.json"
FROM_RELEASE = bool(int(os.getenv("MAIC_PROMPTS_FROM_RELEASE", "1")))

_REQUIRED = ("grammar", "sentence", "passage")
PASSAGE_SKELETON_TEXT = (
    "[지문] 작성 규칙:\n"
    "- \"요지/주제\"를 1~2문장으로 요약합니다.\n"
    "- \"쉬운 예시/비유\"로 학생 수준에 맞춘 설명을 제공합니다.\n"
    "- \"제목\"을 1개 제안합니다.\n"
    "- \"오답 포인트\"가 있으면 1~2개만 짚습니다.\n"
    "- \"근거/출처\"에 본문/사전/문법서 등 최소 1건을 남깁니다.\n"
)

_last_load_ts: Optional[float] = None
_last_status: Dict[str, Any] = {
    "source": "init", "reason": "not_loaded", "etag": "", "sha": "",
    "ref": REF, "path": PATH_, "ts": 0, "schema_ok": False,
}

# ---- 파싱 유틸 ----------------------------------------------------------------
def _yaml_load(text: str) -> Dict[str, Any]:
    """레거시 호환성을 위한 YAML 로딩 함수"""
    from src.core.data_parser import parse_yaml
    return parse_yaml(text)

def _is_non_empty_str(x: Any) -> bool:
    return isinstance(x, str) and bool(x.strip())

def _is_non_empty_mapping(x: Any) -> bool:
    return isinstance(x, dict) and len(x) > 0

def _ensure_required_modes(data: Dict[str, Any], *, permissive: bool = False) -> Dict[str, Any]:
    """
    필수 모드 보장 + 타입 완화:
    - grammar/sentence/passage 는 **문자열 또는 매핑(dict)** 둘 다 허용.
    - permissive=True (로컬/샘플 로딩 등)일 때 passage가 비어있으면 최소 스켈레톤으로 보강.
    """
    if not isinstance(data, dict):
        raise ValueError("root must be mapping(dict)")
    modes = data.get("modes")
    if not isinstance(modes, dict):
        raise ValueError("missing 'modes' mapping")

    # 필요 시 passage 보강(객체 스키마와의 일관성을 위해 template 필드로 넣음)
    if permissive:
        p = modes.get("passage")
        if not (_is_non_empty_str(p) or _is_non_empty_mapping(p)):
            modes["passage"] = {"template": PASSAGE_SKELETON_TEXT}

    # 최종 검증: 각 모드는 문자열(비어있지 않음) 또는 매핑(비어있지 않음) 허용
    for k in _REQUIRED:
        v = modes.get(k)
        if not (_is_non_empty_str(v) or _is_non_empty_mapping(v)):
            raise ValueError(f"'modes.{k}' must be non-empty (string or mapping)")
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


def _download_url(url: str, *, token: Optional[str] = None, timeout: float = TIMEOUT) -> bytes:
    headers = _gh_headers()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(url, headers=headers)
    with request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _fetch_release_asset(
    owner: str,
    repo: str,
    *,
    token: Optional[str],
    tag_candidates: Sequence[str],
    asset_candidates: Sequence[str],
) -> Optional[Tuple[str, str]]:
    try:
        gh = GHReleases(owner=owner, repo=repo, token=token or "")
    except Exception:
        return None

    # Attempt pointer tags first, then fallback to scanning releases
    chosen_rel = None
    chosen_tag = None
    chosen_asset = None

    patterns = [
        re.compile(r"^prompts[-_].+\.(yaml|yml)$", re.IGNORECASE),
        re.compile(r"^prompts\.(yaml|yml)$", re.IGNORECASE),
    ]

    for tag in tag_candidates:
        rel = gh.get_release_by_tag(tag) if tag != "latest" else gh.get_latest_release()
        if rel and rel.get("id"):
            assets = rel.get("assets") or []
            for cand in asset_candidates:
                hit = next((a for a in assets if str(a.get("name") or "").lower() == cand.lower()), None)
                if hit:
                    chosen_rel = rel
                    chosen_tag = rel.get("tag_name") or tag
                    chosen_asset = hit
                    break
            if not chosen_asset:
                for asset in assets:
                    nm = str(asset.get("name") or "")
                    if any(p.search(nm) for p in patterns):
                        chosen_rel = rel
                        chosen_tag = rel.get("tag_name") or tag
                        chosen_asset = asset
                        break
            if chosen_asset:
                break

    if not chosen_asset:
        # fallback: scan recent releases for first matching asset
        try:
            for rel in gh.list_releases(per_page=30):
                assets = rel.get("assets") or []
                for cand in asset_candidates:
                    hit = next((a for a in assets if str(a.get("name") or "").lower() == cand.lower()), None)
                    if hit:
                        chosen_rel = rel
                        chosen_tag = rel.get("tag_name") or rel.get("name")
                        chosen_asset = hit
                        break
                if not chosen_asset:
                    for asset in assets:
                        nm = str(asset.get("name") or "")
                        if any(p.search(nm) for p in patterns):
                            chosen_rel = rel
                            chosen_tag = rel.get("tag_name") or rel.get("name")
                            chosen_asset = asset
                            break
                if chosen_asset:
                    break
        except GHError:
            pass

    if not chosen_asset:
        return None

    url = chosen_asset.get("browser_download_url") or ""
    if not url:
        return None

    try:
        data = _download_url(url, token=token)
        text = data.decode("utf-8")
        return text, chosen_tag or ""
    except Exception:
        return None

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
    우선순위: (1) local_path → (2) GitHub Contents(ETag/TTL) → (3) 캐시 → (4) 내장 샘플.
    - 각 모드는 문자열/객체 둘 다 허용. 로컬/샘플에서는 passage 자동 보강(permissive=True).
    반환: {'version': '1', 'modes': {...}}
    """
    global _last_load_ts, _last_status
    now = time.time()

    eff_owner = owner or OWNER
    eff_repo = repo or REPO
    eff_ref = ref or REF
    eff_path = path or PATH_

    # 1) 로컬 경로 우선(테스트 픽스처: docs/_gpt/prompts.sample.json)
    if local_path is not None:
        p = Path(local_path)
        if not p.exists():
            raise FileNotFoundError(f"local_path not found: {p}")
        text = p.read_text(encoding="utf-8")
        data = _yaml_load(text)
        data = _ensure_required_modes(data, permissive=True)
        _last_status.update({"source": "local", "reason": "file", "path": str(p), "ts": now, "schema_ok": True})
        _last_load_ts = now
        return {"version": str(data.get("version", "1")), "modes": data["modes"]}

    # TTL 캐시
    if (not force) and _last_load_ts and (now - _last_load_ts) < TTL_SEC and CACHE_FILE.exists():
        data = _yaml_load(CACHE_FILE.read_text(encoding="utf-8"))
        data = _ensure_required_modes(data)  # 엄격
        _last_status.update({"source": "cache", "reason": "ttl_hit", "ts": now, "schema_ok": True})
        return {"version": str(data.get("version", "1")), "modes": data["modes"]}

    # 2) 릴리스 자산 우선 시도 (prompts)
    if FROM_RELEASE:
        release_try = _fetch_release_asset(
            eff_owner,
            eff_repo,
            token=TOKEN,
            tag_candidates=("prompts-latest", "latest"),
            asset_candidates=("prompts.yaml", "prompts.yml"),
        )
        if release_try is not None:
            text, tag = release_try
            CACHE_FILE.write_text(text, encoding="utf-8")
            META_FILE.write_text(json.dumps({"release_tag": tag}), encoding="utf-8")
            data = _yaml_load(text)
            data = _ensure_required_modes(data)
            _last_status.update({
                "source": "release",
                "reason": "download",
                "ref": tag,
                "path": "release/prompts.yaml",
                "ts": now,
                "schema_ok": True,
            })
            _last_load_ts = now
            return {"version": str(data.get("version", "1")), "modes": data["modes"]}

    # 3) GitHub Contents API 시도
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
            data = _ensure_required_modes(data)  # 엄격
            _last_status.update({"source": "repo", "reason": "200", "etag": fr.etag, "sha": fr.sha,
                                 "ref": eff_ref, "path": eff_path, "ts": now, "schema_ok": True})
            _last_load_ts = now
            return {"version": str(data.get("version", "1")), "modes": data["modes"]}
    except Exception as e:
        _last_status.update({"source": "repo", "reason": f"error:{e.__class__.__name__}", "ref": eff_ref,
                             "path": eff_path, "ts": now, "schema_ok": False})

    # 4) 캐시 폴백
    if CACHE_FILE.exists():
        data = _yaml_load(CACHE_FILE.read_text(encoding="utf-8"))
        data = _ensure_required_modes(data)  # 엄격
        _last_status.update({"source": "cache", "reason": "fallback", "ts": now, "schema_ok": True})
        _last_load_ts = now
        return {"version": str(data.get("version", "1")), "modes": data["modes"]}

    # 5) 내장 샘플(.yaml → .json 순서)
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
