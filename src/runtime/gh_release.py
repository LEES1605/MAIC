# [01] START: src/runtime/gh_release.py — GitHub Releases helper (ensure_release / upload_asset)
from __future__ import annotations

import json
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from urllib import error, request

class GHError(RuntimeError):
    pass

@dataclass
class GHReleases:
    owner: str
    repo: str
    token: str

    def _headers(self, *, accept_upload: bool = False) -> Dict[str, str]:
        h = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "maic-release/1",
            "Authorization": f"Bearer {self.token}",
        }
        if accept_upload:
            h["Accept"] = "application/vnd.github+json"
        return h

    def _http(self, method: str, url: str, *, data: Optional[bytes] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        req = request.Request(url, data=data, headers=headers or {}, method=method)
        try:
            with request.urlopen(req, timeout=20) as resp:
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

    def _get_release_by_tag(self, tag: str) -> Optional[Dict[str, Any]]:
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/tags/{tag}"
        try:
            return self._http("GET", url, headers=self._headers())
        except GHError as e:
            if " 404:" in str(e):
                return None
            raise

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
        upload_url = f"https://uploads.github.com/repos/{self.owner}/{self.repo}/releases/{rel_id}/assets?name={request.quote(name)}"
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
    return GHReleases(owner=owner, repo=repo, token=token)
# [01] END: src/runtime/gh_release.py — GitHub Releases helper (ensure_release / upload_asset)
