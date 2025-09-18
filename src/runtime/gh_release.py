from __future__ import annotations

import importlib
import io
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional
from zipfile import ZipFile

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class GHConfig:
    owner: str
    repo: str
    token: Optional[str] = None
    timeout: int = 20


class GHError(RuntimeError):
    pass


class GHReleases:
    """Minimal GitHub Releases client for index bundles."""

    def __init__(self, cfg: GHConfig) -> None:
        self.cfg = cfg
        self._session: Optional[Any] = None  # requests.Session

    # ------------------------- http helpers -------------------------

    def _sess(self) -> Any:
        if self._session is None:
            try:
                requests = importlib.import_module("requests")
            except Exception as exc:  # noqa: BLE001
                raise GHError("requests is required: pip install requests") from exc
            s = requests.Session()
            s.headers.update(
                {
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "MAIC-IndexClient/1.0",
                }
            )
            if self.cfg.token:
                s.headers["Authorization"] = f"Bearer {self.cfg.token}"
            self._session = s
        return self._session

    def _get(self, url: str) -> Any:
        r = self._sess().get(url, timeout=self.cfg.timeout)
        if r.status_code == 404:
            raise GHError("resource not found")
        r.raise_for_status()
        return r

    def _post(self, url: str, **kw: Any) -> Any:
        r = self._sess().post(url, timeout=self.cfg.timeout, **kw)
        r.raise_for_status()
        return r

    def _patch(self, url: str, **kw: Any) -> Any:
        r = self._sess().patch(url, timeout=self.cfg.timeout, **kw)
        r.raise_for_status()
        return r

    def _delete(self, url: str) -> None:
        r = self._sess().delete(url, timeout=self.cfg.timeout)
        # 204 expected for deletes; ignore 404
        if r.status_code not in (200, 201, 202, 204, 404):
            r.raise_for_status()

    # ------------------------- release ops -------------------------

    def get_release_by_tag(self, tag: str) -> dict:
        url = (
            f"https://api.github.com/repos/{self.cfg.owner}/"
            f"{self.cfg.repo}/releases/tags/{tag}"
        )
        return self._get(url).json()

    def ensure_release(self, tag: str, name: Optional[str] = None) -> dict:
        """Return release by tag; create if missing."""
        name = name or f"Indices {tag}"
        try:
            return self.get_release_by_tag(tag)
        except GHError:
            url = f"https://api.github.com/repos/{self.cfg.owner}/{self.cfg.repo}/releases"
            payload = {"tag_name": tag, "name": name, "prerelease": False}
            return self._post(url, json=payload).json()

    def delete_asset_if_exists(self, rel: dict, asset_name: str) -> None:
        for a in rel.get("assets", []) or []:
            if a.get("name") == asset_name:
                asset_id = a.get("id")
                if asset_id:
                    url = (
                        f"https://api.github.com/repos/{self.cfg.owner}/"
                        f"{self.cfg.repo}/releases/assets/{asset_id}"
                    )
                    self._delete(url)

    def upload_asset(
        self,
        rel: dict,
        file_path: Path,
        *,
        label: Optional[str] = None,
    ) -> None:
        """Upload file as release asset (replaces if same name exists)."""
        if not file_path.exists():
            raise GHError(f"asset file not found: {file_path}")
        fname = file_path.name
        self.delete_asset_if_exists(rel, fname)

        # upload_url template: .../assets{?name,label}
        upload_url_tpl = rel.get("upload_url", "")
        base = upload_url_tpl.split("{", 1)[0]
        label_q = f"&label={label}" if label else ""
        url = f"{base}?name={fname}{label_q}"

        headers = {"Content-Type": "application/zip"}
        with file_path.open("rb") as f:
            data = f.read()
        r = self._sess().post(url, headers=headers, data=data, timeout=self.cfg.timeout)
        r.raise_for_status()

    # ------------------------- download/restore -------------------------

    def _download_asset_bytes(self, asset: dict) -> bytes:
        url = asset.get("browser_download_url")
        if not url:
            raise GHError("asset has no browser_download_url")
        r = self._sess().get(
            url,
            headers={"Accept": "application/octet-stream"},
            timeout=self.cfg.timeout,
        )
        r.raise_for_status()
        return r.content

    @staticmethod
    def _safe_extract_zip(zip_bytes: bytes, dest: Path) -> None:
        """Extract zip safely (prevent path traversal)."""
        dest.mkdir(parents=True, exist_ok=True)
        with ZipFile(io.BytesIO(zip_bytes)) as zf:
            for info in zf.infolist():
                # Avoid absolute/parent paths
                rel = Path(info.filename)
                if rel.is_absolute() or ".." in rel.parts:
                    raise GHError(f"unsafe path in zip: {info.filename}")
            zf.extractall(dest)

    def restore_latest_index(
        self,
        *,
        tag_candidates: Iterable[str],
        asset_candidates: Iterable[str],
        dest: Path,
        clean_dest: bool = True,
    ) -> str:
        """
        Try tags and asset names in order, extract to dest.
        Returns a short human log.
        """
        tried: list[str] = []
        last_err: Optional[str] = None

        for tag in tag_candidates:
            try:
                rel = self.get_release_by_tag(tag)
            except Exception as exc:  # noqa: BLE001
                tried.append(f"tag:{tag}=404")
                last_err = str(exc)
                continue

            assets = rel.get("assets") or []
            picked: Optional[dict] = None
            # Exact name first, then any *.zip as fallback
            for name in asset_candidates:
                for a in assets:
                    if a.get("name") == name:
                        picked = a
                        break
                if picked:
                    break
            if not picked:
                for a in assets:
                    if str(a.get("name", "")).lower().endswith(".zip"):
                        picked = a
                        break

            if not picked:
                tried.append(f"tag:{tag}=no-zip")
                continue

            content = self._download_asset_bytes(picked)
            if clean_dest and dest.exists():
                for p in dest.glob("*"):
                    try:
                        if p.is_dir():
                            for q in p.rglob("*"):
                                if q.is_file():
                                    q.unlink(missing_ok=True)
                            p.rmdir()
                        else:
                            p.unlink(missing_ok=True)
                    except Exception:  # noqa: BLE001
                        pass
            self._safe_extract_zip(content, dest)
            name = picked.get("name", "unknown.zip")
            return f"OK: tag={tag}, asset={name}, files restored to {dest}"

        detail = "; ".join(tried)
        raise GHError(f"no matching release asset. tried: {detail}. last={last_err}")

    def upload_index_zip(
        self,
        *,
        tag: str,
        name: Optional[str],
        zip_path: Path,
        make_tag: bool = True,
    ) -> str:
        """Create/update tag release and upload zip as asset; returns log."""
        rel = self.ensure_release(tag, name=name or f"Indices {tag}")
        self.upload_asset(rel, zip_path, label=None)
        return f"OK: uploaded {zip_path.name} to tag={tag}"
