from __future__ import annotations

import importlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import yaml

__all__ = ["PromptsLoader", "load_prompts"]


@dataclass(frozen=True)
class LoaderConfig:
    owner: str
    repo: str
    tag: str = "prompts-latest"
    asset_name: str = "prompts.yaml"
    token: Optional[str] = None
    cache_dir: Path = Path.home() / ".cache" / "maic" / "prompts"
    schema_path: Optional[Path] = None  # default = repo_root/schemas/prompts.schema.json
    timeout_sec: int = 15


class PromptsLoadError(RuntimeError):
    pass


class PromptsLoader:
    """
    GitHub Releases에서 prompts 번들을 읽어와 캐시/검증/롤백해 주는 로더.

    - 네트워크가 불가능하거나 테스트 상황이면 local_path로 바로 로드
    - 네트워크 가능 시:
        1) release tag(기본: prompts-latest)의 assets 조회
        2) prompts.yaml 자산을 ETag 기반으로 If-None-Match 요청
        3) 변경 시 내려받아 sha256.txt와 대조, 스키마 검증 후 캐시 갱신
        4) 실패 시 기존 검증 캐시로 롤백
    """

    def __init__(self, cfg: LoaderConfig) -> None:
        self.cfg = cfg
        self.cache_dir = cfg.cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.meta_path = self.cache_dir / "meta.json"
        self.yaml_path = self.cache_dir / "prompts.yaml"
        self.sha_path = self.cache_dir / "sha256.txt"

        if cfg.schema_path is None:
            # src/runtime/prompts_loader.py → repo_root
            repo_root = Path(__file__).resolve().parents[2]
            self.schema_path = repo_root / "schemas" / "prompts.schema.json"
        else:
            self.schema_path = cfg.schema_path

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "User-Agent": "MAIC-PromptsLoader/1.0",
            }
        )
        if cfg.token:
            self.session.headers["Authorization"] = f"Bearer {cfg.token}"

    # ------------------------------- public API -------------------------------

    def load(
        self,
        *,
        local_path: Optional[Path] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Load prompts from Releases (or local_path for offline).

        Returns parsed YAML (dict). Raises PromptsLoadError on failure with no cache.
        """
        if local_path is not None:
            data = self._read_yaml(local_path)
            self._validate_schema(data)
            return data

        try:
            return self._load_remote(force_refresh=force_refresh)
        except Exception as exc:  # noqa: BLE001
            # Fallback to validated cache
            cached = self._load_cache()
            if cached is not None:
                logging.warning("prompts: remote load failed, using cached copy: %r", exc)
                return cached
            raise PromptsLoadError(f"prompts load failed and no cache: {exc!r}") from exc

    # ------------------------------ remote loading ----------------------------

    def _load_remote(self, *, force_refresh: bool) -> Dict[str, Any]:
        rel = self._get_release_by_tag(self.cfg.tag)
        assets = rel.get("assets") or []
        yaml_asset = self._find_asset(assets, self.cfg.asset_name)
        sha_asset = self._find_asset(assets, "sha256.txt")

        if yaml_asset is None:
            raise PromptsLoadError(f"asset not found: {self.cfg.asset_name}")

        etag_cached = self._read_meta().get("etag") if not force_refresh else None
        etag, content = self._download_asset(yaml_asset, etag=etag_cached)
        if content is None:
            # 304 Not Modified: use cache
            cached = self._load_cache()
            if cached is None:
                raise PromptsLoadError("ETag says not modified, but cache is missing")
            return cached

        # write temp → atomic replace
        tmp_yaml = self.yaml_path.with_suffix(".yaml.tmp")
        tmp_sha = self.sha_path.with_suffix(".txt.tmp")
        tmp_yaml.write_bytes(content)

        # validate checksum if present
        if sha_asset is not None:
            sha_txt = self._download_asset_text(sha_asset)
            tmp_sha.write_text(sha_txt, encoding="utf-8")
            expected = self._parse_sha256(sha_txt)
            actual = sha256(content).hexdigest()
            if expected and expected.lower() != actual.lower():
                raise PromptsLoadError(f"sha256 mismatch: expected {expected}, got {actual}")

        # schema validation
        data = yaml.safe_load(content)
        self._validate_schema(data)

        # commit
        tmp_yaml.replace(self.yaml_path)
        if tmp_sha.exists():
            tmp_sha.replace(self.sha_path)
        self._write_meta({"etag": etag, "ts": int(time.time())})

        return data

    def _get_release_by_tag(self, tag: str) -> Dict[str, Any]:
        url = f"https://api.github.com/repos/{self.cfg.owner}/{self.cfg.repo}/releases/tags/{tag}"
        r = self.session.get(url, timeout=self.cfg.timeout_sec)
        if r.status_code == 404:
            raise PromptsLoadError(f"release tag not found: {tag!r}")
        r.raise_for_status()
        return r.json()

    def _find_asset(
        self,
        assets: list[dict[str, Any]],
        name: str,
    ) -> Optional[dict[str, Any]]:
        for a in assets:
            if a.get("name") == name:
                return a
        return None

    def _download_asset(
        self,
        asset: dict[str, Any],
        *,
        etag: Optional[str],
    ) -> tuple[Optional[str], Optional[bytes]]:
        """
        Return (etag, content). content=None when 304 Not Modified.
        """
        url = asset.get("browser_download_url")
        if not url:
            raise PromptsLoadError("asset has no browser_download_url")

        headers = {"Accept": "application/octet-stream"}
        if etag:
            headers["If-None-Match"] = etag

        r = self.session.get(url, headers=headers, timeout=self.cfg.timeout_sec)
        if r.status_code == 304:
            return (etag, None)
        r.raise_for_status()
        new_etag = r.headers.get("ETag", "").strip('"')
        return (new_etag, r.content)

    def _download_asset_text(self, asset: dict[str, Any]) -> str:
        url = asset.get("browser_download_url")
        if not url:
            raise PromptsLoadError("sha asset has no download url")
        r = self.session.get(url, headers={"Accept": "text/plain"}, timeout=self.cfg.timeout_sec)
        r.raise_for_status()
        return r.text

    # --------------------------------- cache ----------------------------------

    def _load_cache(self) -> Optional[Dict[str, Any]]:
        if not self.yaml_path.exists():
            return None
        data = self._read_yaml(self.yaml_path)
        try:
            self._validate_schema(data)
        except Exception as exc:  # noqa: BLE001
            logging.warning("prompts: cached schema validation failed: %r", exc)
            return None
        return data

    def _read_meta(self) -> Dict[str, Any]:
        if self.meta_path.exists():
            try:
                return json.loads(self.meta_path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                return {}
        return {}

    def _write_meta(self, meta: Dict[str, Any]) -> None:
        tmp = self.meta_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.meta_path)

    # --------------------------------- utils ----------------------------------

    def _read_yaml(self, path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _validate_schema(self, data: Dict[str, Any]) -> None:
        # 런타임 의존성: jsonschema. 타입 스텁은 강제하지 않음(동적 임포트).
        schema_text = self.schema_path.read_text(encoding="utf-8")
        schema = json.loads(schema_text)

        js = importlib.import_module("jsonschema")  # type: ignore[no-redef]
        validator_cls: Any = getattr(js, "Draft202012Validator", None)
        if validator_cls is None:
            raise PromptsLoadError("jsonschema.Draft202012Validator not found")
        validator = validator_cls(schema)
        validator.validate(data)

    @staticmethod
    def _parse_sha256(text: str) -> Optional[str]:
        # accept "sha256:HEX" or plain HEX in file
        m = re.search(r"([A-Fa-f0-9]{64})", text)
        return m.group(1) if m else None


def load_prompts(
    *,
    owner: Optional[str] = None,
    repo: Optional[str] = None,
    token: Optional[str] = None,
    tag: str = "prompts-latest",
    asset_name: str = "prompts.yaml",
    cache_dir: Optional[Path] = None,
    local_path: Optional[Path] = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    편의 함수. 환경변수로 기본값을 채워 호출할 수 있다.

    Env:
      MAIC_GH_OWNER / MAIC_GH_REPO / MAIC_GH_TOKEN
      MAIC_PROMPTS_TAG / MAIC_PROMPTS_ASSET
      MAIC_PROMPTS_CACHE_DIR / MAIC_PROMPTS_LOCAL_PATH
    """
    default_cache_dir = str(LoaderConfig.cache_dir)
    env_cache_dir = os.getenv("MAIC_PROMPTS_CACHE_DIR", default_cache_dir)

    owner_str: str = owner if owner is not None else os.getenv("MAIC_GH_OWNER", "")
    repo_str: str = repo if repo is not None else os.getenv("MAIC_GH_REPO", "")

    cfg = LoaderConfig(
        owner=owner_str,
        repo=repo_str,
        tag=os.getenv("MAIC_PROMPTS_TAG", tag),
        asset_name=os.getenv("MAIC_PROMPTS_ASSET", asset_name),
        token=token or os.getenv("MAIC_GH_TOKEN") or None,
        cache_dir=cache_dir or Path(env_cache_dir),
    )
    if not cfg.owner or not cfg.repo:
        raise PromptsLoadError("missing owner/repo (set params or MAIC_GH_OWNER/MAIC_GH_REPO)")

    loader = PromptsLoader(cfg)
    env_local = os.getenv("MAIC_PROMPTS_LOCAL_PATH")
    lp = local_path or (Path(env_local) if env_local else None)
    return loader.load(local_path=lp, force_refresh=force_refresh)
