# [01] START: src/runtime/gh_release.py — GitHub Releases helper (ensure_release / upload_asset)
from __future__ import annotations

import json
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from urllib import error, request

# 협의규약/보안: 토큰은 환경변수/Secrets만, 로그에 토큰/PII 금지. :contentReference[oaicite:2]{index=2}

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
            # uploads.github.com 도 JSON Accept 허용
            h["Accept"] = "application/vnd.github+json"
        return h

    def _http(self, method: str, url: str, *, data: Optional[bytes] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        req = request.Request(url, data=data, headers=headers or {}, method=method)
        try:
            with request.urlopen(req, timeout=20) as resp:
                body = resp.read()
                if not body:
                    return {}
                # JSON이 아니면 빈 dict 반환
                try:
                    return json.loads(body.decode("utf-8"))
                except Exception:
                    return {}
        except error.HTTPError as e:
            # GitHub 에러 메시지 표준화
            try:
                err_json = json.loads(e.read().decode("utf-8"))
            except Exception:
                err_json = {"message": str(e)}
            msg = err_json.get("message") or str(e)
            raise GHError(f"{method} {url} -> {e.code}: {msg}") from e
        except error.URLError as e:
            raise GHError(f"{method} {url} -> URLError: {e.reason}") from e

    # --------- Releases ---------
    def _get_release_by_tag(self, tag: str) -> Optional[Dict[str, Any]]:
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/tags/{tag}"
        try:
            return self._http("GET", url, headers=self._headers())
        except GHError as e:
            # 404면 None
            if " 404:" in str(e):
                return None
            raise

    def ensure_release(self, tag: str, *, title: Optional[str] = None, notes: Optional[str] = None) -> Dict[str, Any]:
        """
        태그로 릴리스를 조회하고, 없으면 생성해 반환한다.
        반환 dict에는 id/upload_url/assets 등이 포함된다.
        """
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
        # 일부 응답은 본문 없음 → 성공 시 예외 없음
        self._http("DELETE", url, headers=self._headers())

    def upload_asset(self, *, tag: str, file_path: str | Path, asset_name: Optional[str] = None, clobber: bool = True) -> Dict[str, Any]:
        """
        지정 릴리스(tag)에 자산을 업로드한다. 같은 이름이 있으면 clobber=True일 때 삭제 후 업로드한다.
        """
        p = Path(file_path).expanduser().resolve()
        if not p.exists() or not p.is_file():
            raise GHError(f"asset file not found: {p}")

        rel = self.ensure_release(tag)
        rel_id = int(rel["id"])
        # 같은 이름 삭제
        name = asset_name or p.name
        if clobber:
            for a in self._list_assets(rel_id):
                if a.get("name") == name:
                    self._delete_asset(int(a["id"]))

        # 업로드
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
    """
    환경변수에서 owner/repo/token을 추출해 GHReleases를 생성한다.
    - MAIC_GH_OWNER/MAIC_GH_REPO 우선, 없으면 GITHUB_REPOSITORY(owner/repo) 파싱
    - 토큰: GITHUB_TOKEN → GH_TOKEN → GITHUB_ADMIN_TOKEN
    """
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
