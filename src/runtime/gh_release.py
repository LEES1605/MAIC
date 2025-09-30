# [01] START: src/runtime/gh_release.py — GitHub Releases helper (ensure_release / upload/download/restore)
from __future__ import annotations

import io
import json
import mimetypes
import os
import tarfile
import zipfile
from dataclasses import dataclass
import re
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple
from urllib import error, request, parse


class GHError(RuntimeError):
    pass


@dataclass
class GHConfig:
    owner: str
    repo: str
    token: Optional[str] = None


@dataclass
class RestoreLog:
    tag: Optional[str]
    release_id: Optional[int]
    asset_name: Optional[str]
    detail: str = ""
    used_latest_endpoint: bool = False


class GHReleases:
    """GitHub Releases client.

    Backwards compatible ctor:
      - GHReleases(GHConfig(...))
      - GHReleases(owner=..., repo=..., token=...)
    """

    def __init__(self, cfg: GHConfig | None = None, *, owner: Optional[str] = None, repo: Optional[str] = None, token: Optional[str] = None) -> None:
        if cfg is not None:
            self.owner = cfg.owner
            self.repo = cfg.repo
            self.token = cfg.token or ""
        else:
            self.owner = str(owner or "")
            self.repo = str(repo or "")
            self.token = str(token or "")
        if not (self.owner and self.repo and self.token):
            # 업로드 외 읽기 전용은 퍼블릭에서 토큰 없이도 가능하지만, 통일성을 위해 토큰 요구
            # 필요 시 호출부에서 빈 토큰을 넘길 수 있으므로 여기서 막지는 않음
            pass

    def _headers(self, *, accept_upload: bool = False, accept_octet: bool = False) -> Dict[str, str]:
        h = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "maic-release/1",
        }
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if accept_upload:
            h["Accept"] = "application/vnd.github+json"
        if accept_octet:
            h["Accept"] = "application/octet-stream"
        return h

    def _http(self, method: str, url: str, *, data: Optional[bytes] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        req = request.Request(url, data=data, headers=headers or {}, method=method)
        try:
            with request.urlopen(req, timeout=30) as resp:
                body = resp.read()
                if not body:
                    return {}
                try:
                    return json.loads(body.decode("utf-8"))
                except Exception:
                    return {}
        except error.HTTPError as e:
            try:
                err_json = json.loads(e.read().decode("utf-8"))
            except Exception:
                err_json = {"message": str(e)}
            msg = err_json.get("message") or str(e)
            raise GHError(f"{method} {url} -> {e.code}: {msg}") from e
        except error.URLError as e:
            raise GHError(f"{method} {url} -> URLError: {e.reason}") from e

    # -------- Release queries --------
    def get_latest_release(self) -> Optional[Dict[str, Any]]:
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"
        try:
            j = self._http("GET", url, headers=self._headers())
            return j or None
        except GHError as e:
            if " 404:" in str(e):
                return None
            raise

    def get_release_by_tag(self, tag: str) -> Optional[Dict[str, Any]]:
        return self._get_release_by_tag(tag)

    def _get_release_by_tag(self, tag: str) -> Optional[Dict[str, Any]]:
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/tags/{tag}"
        try:
            return self._http("GET", url, headers=self._headers())
        except GHError as e:
            if " 404:" in str(e):
                return None
            raise

    # -------- Upload helpers --------
    def ensure_release(self, tag: str, *, title: Optional[str] = None, notes: Optional[str] = None) -> Dict[str, Any]:
        rel = self._get_release_by_tag(tag)
        if rel:
            return rel
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases"
        payload = {
            "tag_name": tag,
            "name": title or tag,
            "body": notes or "",
            "prerelease": False,
            "draft": False,
        }
        j = self._http("POST", url, data=json.dumps(payload).encode("utf-8"), headers=self._headers())
        if not j or not j.get("id"):
            raise GHError("failed to create release")
        return j

    def _list_assets(self, release_id: int) -> list[dict]:
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/{release_id}/assets"
        j = self._http("GET", url, headers=self._headers())
        assets = j if isinstance(j, list) else j.get("assets", [])
        return assets or []

    def list_releases(self, per_page: int = 30) -> list[dict]:
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases?per_page={int(per_page)}"
        j = self._http("GET", url, headers=self._headers())
        return j if isinstance(j, list) else []

    def _delete_asset(self, asset_id: int) -> None:
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/assets/{asset_id}"
        self._http("DELETE", url, headers=self._headers())

    def upload_asset(self, *, tag: str, file_path: str | Path, asset_name: Optional[str] = None, clobber: bool = True) -> Dict[str, Any]:
        p = Path(file_path).expanduser().resolve()
        if not p.exists() or not p.is_file():
            raise GHError(f"asset file not found: {p}")

        rel = self.ensure_release(tag)
        rel_id = int(rel["id"])
        name = asset_name or p.name
        if clobber:
            for a in self._list_assets(rel_id):
                if a.get("name") == name:
                    self._delete_asset(int(a["id"]))

        mime, _ = mimetypes.guess_type(name)
        ctype = mime or "application/octet-stream"
        upload_url = f"https://uploads.github.com/repos/{self.owner}/{self.repo}/releases/{rel_id}/assets?name={parse.quote(name)}"
        headers = self._headers(accept_upload=True)
        headers["Content-Type"] = ctype
        data = p.read_bytes()
        req = request.Request(upload_url, data=data, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode("utf-8") if resp.read is not None else ""
                try:
                    return json.loads(body) if body else {"ok": True, "name": name}
                except Exception:
                    return {"ok": True, "name": name}
        except error.HTTPError as e:
            try:
                err_json = json.loads(e.read().decode("utf-8"))
            except Exception:
                err_json = {"message": str(e)}
            msg = err_json.get("message") or str(e)
            raise GHError(f"upload asset failed: {e.code}: {msg}") from e

    # -------- Restore helpers --------
    def _download_asset(self, browser_download_url: str) -> bytes:
        req = request.Request(browser_download_url, headers=self._headers(accept_octet=True))
        with request.urlopen(req, timeout=60) as resp:
            return resp.read()

    @staticmethod
    def _extract_bytes_to(dest: Path, name: str, data: bytes) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        lower = name.lower()
        bio = io.BytesIO(data)
        if lower.endswith(".zip"):
            with zipfile.ZipFile(bio) as zf:
                zf.extractall(path=dest)
            return
        if lower.endswith(".tar.gz") or lower.endswith(".tgz"):
            with tarfile.open(fileobj=bio, mode="r:gz") as tf:
                tf.extractall(path=dest)
            return
        # fallback: write raw
        (dest / name).write_bytes(data)

    def restore_latest_index(
        self,
        *,
        tag_candidates: Sequence[str],
        asset_candidates: Sequence[str],
        dest: Path,
    ) -> RestoreLog:
        # 1) find release by tag candidates or latest
        chosen_rel: Optional[Dict[str, Any]] = None
        chosen_tag: Optional[str] = None
        used_latest = False

        tag_candidates = list(tag_candidates or [])

        # 1) 명시된 태그 우선 탐색
        for t in tag_candidates:
            rel = self.get_release_by_tag(t)
            if rel and isinstance(rel, dict) and rel.get("id"):
                chosen_rel = rel
                chosen_tag = rel.get("tag_name") or t
                break

        # 2) 최신 릴리스/최근 릴리스 중 index-* 우선 탐색
        if not chosen_rel:
            rel_latest = self.get_latest_release()
            releases = [rel_latest] + self.list_releases(per_page=30)
            for rel in releases:
                if not rel or not rel.get("id"):
                    continue
                tag = str(rel.get("tag_name") or rel.get("name") or "")
                if tag.startswith("index-"):
                    chosen_rel = rel
                    chosen_tag = tag
                    used_latest = used_latest or (rel is rel_latest)
                    break

        # 3) 마지막으로 latest 자체를 포함한 재시도
        if not chosen_rel:
            for t in tag_candidates + ["latest"]:
                rel = self.get_latest_release() if t == "latest" else self.get_release_by_tag(t)
                if rel and isinstance(rel, dict) and rel.get("id"):
                    chosen_rel = rel
                    chosen_tag = rel.get("tag_name") or t
                    used_latest = used_latest or (t == "latest")
                    break

        if not chosen_rel:
            raise GHError("no matching release found for index restore")

        rel_id = int(chosen_rel.get("id"))
        assets = chosen_rel.get("assets") or []
        if not assets:
            # fetch via assets API if not embedded
            assets = self._list_assets(rel_id)

        # 2) choose asset on chosen_rel
        chosen_asset: Optional[Dict[str, Any]] = None
        for cand in asset_candidates or []:
            for a in assets:
                if str(a.get("name") or "").lower() == cand.lower():
                    chosen_asset = a
                    break
            if chosen_asset:
                break

        # 2-1) heuristic match (e.g., index_1758719923.zip)
        if not chosen_asset:
            patts = [
                re.compile(r"^index[_-].+\.(zip|tar\.gz)$", re.IGNORECASE),
                re.compile(r"^(indices|persist|hq_index|prepared)\.(zip|tar\.gz)$", re.IGNORECASE),
            ]
            for a in assets:
                nm = str(a.get("name") or "")
                if any(p.search(nm) for p in patts):
                    chosen_asset = a
                    break

        # Fallback: scan recent releases for first one that has a matching asset
        if not chosen_asset:
            for rel in self.list_releases(per_page=50):
                rid = rel.get("id")
                if not rid:
                    continue
                tag = str(rel.get("tag_name") or rel.get("name") or "")
                # prefer tags starting with "index-"
                prefer = tag.startswith("index-")
                rel_assets = rel.get("assets") or []
                if not rel_assets:
                    rel_assets = self._list_assets(int(rid))
                # exact-match by candidate list
                for cand in asset_candidates or []:
                    hit = next((a for a in rel_assets if str(a.get("name") or "").lower() == cand.lower()), None)
                    if hit:
                        chosen_rel = rel
                        chosen_tag = tag or chosen_tag
                        chosen_asset = hit
                        rel_id = int(rid)
                        assets = rel_assets
                        break
                # heuristic fallback
                if not chosen_asset:
                    for a in rel_assets:
                        nm = str(a.get("name") or "")
                        if any(p.search(nm) for p in patts):
                            chosen_rel = rel
                            chosen_tag = tag or chosen_tag
                            chosen_asset = a
                            rel_id = int(rid)
                            assets = rel_assets
                            break
                if chosen_asset:
                    # if we didn't prefer index-* and can continue to find better, we could, but keep simple
                    break

        if not chosen_asset:
            raise GHError("no matching asset in any recent release for index restore")

        name = chosen_asset.get("name")
        bdl = chosen_asset.get("browser_download_url") or ""
        if not bdl:
            raise GHError("asset has no browser_download_url")

        # 3) download and extract
        data = self._download_asset(bdl)
        self._extract_bytes_to(dest, str(name), data)

        return RestoreLog(
            tag=chosen_tag,
            release_id=rel_id,
            asset_name=str(name),
            detail=f"restored to {dest}",
            used_latest_endpoint=used_latest,
        )


def from_env() -> GHReleases:
    owner = os.getenv("MAIC_GH_OWNER", "")
    repo = os.getenv("MAIC_GH_REPO", "")
    if not (owner and repo):
        rep = os.getenv("GITHUB_REPOSITORY", "")
        if rep and "/" in rep:
            owner, repo = rep.split("/", 1)
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("GITHUB_ADMIN_TOKEN") or ""
    if not (owner and repo and token):
        raise GHError("missing env: owner/repo/token")
    return GHReleases(GHConfig(owner=owner, repo=repo, token=token))
# [01] END: src/runtime/gh_release.py — GitHub Releases helper (ensure_release / upload/download/restore)
