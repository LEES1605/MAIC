# ===== [01] FILE: src/runtime/gh_release.py — START =====
from __future__ import annotations

import importlib
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

@dataclass(frozen=True)
class GHConfig:
    owner: str
    repo: str
    token: Optional[str] = None
    timeout: int = 20


class GHError(RuntimeError):
    pass


@dataclass(frozen=True)
class RestoreLog:
    tag: Optional[str]
    release_id: Optional[int]
    asset_name: Optional[str]
    detail: str
    used_latest_endpoint: bool = False


class GHReleases:
    """Minimal GitHub Releases client (SSOT)."""

    def __init__(self, cfg: GHConfig) -> None:
        self.cfg = cfg
        self._session: Optional[Any] = None  # requests.Session

    # ------------------------- http helpers -------------------------
    def _sess(self) -> Any:
        if self._session is None:
            try:
                requests = importlib.import_module("requests")
            except Exception as exc:
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

    def _get(self, url: str):
        r = self._sess().get(url, timeout=self.cfg.timeout)
        if r.status_code == 404:
            raise GHError("resource not found")
        r.raise_for_status()
        return r

    def _post(self, url: str, **kw: Any):
        r = self._sess().post(url, timeout=self.cfg.timeout, **kw)
        r.raise_for_status()
        return r

    def _patch(self, url: str, **kw: Any):
        r = self._sess().patch(url, timeout=self.cfg.timeout, **kw)
        r.raise_for_status()
        return r

    def _delete(self, url: str) -> None:
        r = self._sess().delete(url, timeout=self.cfg.timeout)
        if r.status_code not in (200, 201, 202, 204, 404):
            r.raise_for_status()

    # ------------------------- release ops -------------------------
    def get_release_by_tag(self, tag: str) -> dict:
        url = f"https://api.github.com/repos/{self.cfg.owner}/{self.cfg.repo}/releases/tags/{tag}"
        return self._get(url).json()

    def get_latest_release(self) -> dict:
        url = f"https://api.github.com/repos/{self.cfg.owner}/{self.cfg.repo}/releases/latest"
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
                    url = f"https://api.github.com/repos/{self.cfg.owner}/{self.cfg.repo}/releases/assets/{asset_id}"
                    self._delete(url)

    def upload_asset(self, rel: dict, file_path: Path, *, label: Optional[str] = None) -> None:
        if not file_path.exists():
            raise GHError(f"asset file not found: {file_path}")
        fname = file_path.name
        self.delete_asset_if_exists(rel, fname)

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
    @staticmethod
    def _safe_extract_zip(zip_bytes: bytes, dest: Path) -> None:
        """Extract zip safely (prevent path traversal)."""
        import zipfile
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for info in zf.infolist():
                rel = Path(info.filename)
                if rel.is_absolute() or ".." in rel.parts:
                    raise GHError(f"unsafe path in zip: {info.filename}")
            zf.extractall(dest)

    def _clean_destination(self, dest: Path) -> None:
        if not dest.exists():
            return
        for p in dest.glob("*"):
            try:
                if p.is_dir():
                    for q in p.rglob("*"):
                        if q.is_file():
                            q.unlink(missing_ok=True)
                    p.rmdir()
                else:
                    p.unlink(missing_ok=True)
            except Exception:
                pass

    def restore_latest_index(
        self,
        *,
        tag_candidates: Iterable[str],
        asset_candidates: Iterable[str],
        dest: Path,
        clean_dest: bool = True,
    ) -> RestoreLog:
        """
        Try tags and asset names in order, then fall back to /releases/latest.
        Always returns RestoreLog (tag/release_id/asset_name/detail/used_latest_endpoint).
        """
        tried: list[str] = []
        last_err: Optional[str] = None

        def _pick_zip(assets: list[dict]) -> Optional[dict]:
            # exact match first
            for name in asset_candidates:
                for a in assets:
                    if a.get("name") == name:
                        return a
            # then any *.zip
            for a in assets:
                if str(a.get("name", "")).lower().endswith(".zip"):
                    return a
            return None

        # 1) try provided tags
        for tag in tag_candidates:
            try:
                rel = self.get_release_by_tag(tag)
            except Exception as exc:
                tried.append(f"tag:{tag}=404")
                last_err = str(exc)
                continue

            picked = _pick_zip(rel.get("assets") or [])
            if not picked:
                tried.append(f"tag:{tag}=no-zip")
                continue

            content = self._sess().get(
                picked.get("browser_download_url"),
                headers={"Accept": "application/octet-stream"},
                timeout=self.cfg.timeout,
            )
            content.raise_for_status()
            if clean_dest:
                self._clean_destination(dest)
            self._safe_extract_zip(content.content, dest)
            name = picked.get("name", "unknown.zip")
            tag_name = str(rel.get("tag_name") or tag or "").strip() or None
            release_id = rel.get("id")
            return RestoreLog(
                tag=tag_name,
                release_id=release_id,
                asset_name=name,
                detail=f"OK: tag={tag}, asset={name}, files restored to {dest}",
                used_latest_endpoint=False,
            )

        # 2) fall back to latest release
        try:
            rel = self.get_latest_release()
            picked = _pick_zip(rel.get("assets") or [])
            if picked:
                content = self._sess().get(
                    picked.get("browser_download_url"),
                    headers={"Accept": "application/octet-stream"},
                    timeout=self.cfg.timeout,
                )
                content.raise_for_status()
                if clean_dest:
                    self._clean_destination(dest)
                self._safe_extract_zip(content.content, dest)
                name = picked.get("name", "unknown.zip")
                tag_name = str(rel.get("tag_name") or "latest").strip() or None
                release_id = rel.get("id")
                return RestoreLog(
                    tag=tag_name,
                    release_id=release_id,
                    asset_name=name,
                    detail=f"OK: tag=latest, asset={name}, files restored to {dest}",
                    used_latest_endpoint=True,
                )
            tried.append("latest=no-zip")
        except Exception as exc:
            tried.append("latest=error")
            last_err = str(exc)

        detail = "; ".join(tried)
        raise GHError(f"no matching release asset. tried: {detail}. last={last_err}")

    # convenience
    def upload_index_zip(self, *, tag: str, name: Optional[str], zip_path: Path, make_tag: bool = True) -> str:
        rel = self.ensure_release(tag, name=name or f"Indices {tag}")
        self.upload_asset(rel, zip_path, label=None)
        return f"OK: uploaded {zip_path.name} to tag={tag}"

__all__ = ["GHConfig", "GHError", "RestoreLog", "GHReleases"]
# ===== [01] FILE: src/runtime/gh_release.py — END =====
