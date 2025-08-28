# [01] GITHUB RELEASE UPLOADER — START
"""
GitHub Releases 업로드 유틸
- 태그/릴리스 생성
- assets 업로드 (manifest.json, chunks.jsonl.gz, 선택 zip)
- 최신 N(기본 2)개만 보존, 나머지 릴리스+태그 자동 삭제
"""
from __future__ import annotations

import io
import os
import json
import time
import gzip
import zipfile
import pathlib
from typing import Optional, Dict, Any, List

import requests

API_ROOT = "https://api.github.com"


class GitHubReleaseError(RuntimeError):
    pass


def _get_token_and_repo(
    token: Optional[str] = None,
    repo: Optional[str] = None,
) -> tuple[str, str]:
    # 환경변수 우선 → streamlit secrets 백업
    if token is None:
        token = os.getenv("GITHUB_TOKEN")
        if token is None:
            try:
                import streamlit as st  # type: ignore
                token = st.secrets.get("GITHUB_TOKEN")  # pyright: ignore
            except Exception:
                token = None
    if repo is None:
        repo = os.getenv("GITHUB_REPO") or "LEES1605/MAIC"
        try:
            import streamlit as st  # type: ignore
            repo = st.secrets.get("GITHUB_REPO", repo)  # pyright: ignore
        except Exception:
            pass

    if not token:
        raise GitHubReleaseError("GITHUB_TOKEN 미설정")
    if not repo or "/" not in repo:
        raise GitHubReleaseError("GITHUB_REPO 형식 오류 (e.g., owner/repo)")

    return token, repo


def _headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "maic-index-uploader",
    }


def _ts_strings() -> tuple[str, str]:
    # KST 기준으로 보이도록 localtime 사용 (배포 환경 TZ 영향 가능)
    ts = time.localtime()
    tag = time.strftime("index-%Y%m%d-%H%M%S", ts)
    name = time.strftime("MAIC Index %Y-%m-%d %H:%M", ts)
    return tag, name


def _read_manifest_summary(manifest_path: pathlib.Path) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        # 가능한 key들을 관대하게 탐색
        if isinstance(data, dict):
            if "docs" in data and isinstance(data["docs"], list):
                summary["doc_count"] = len(data["docs"])
            if "stats" in data and isinstance(data["stats"], dict):
                for k in ("documents", "chunks", "tokens"):
                    if k in data["stats"]:
                        summary[f"stats_{k}"] = data["stats"][k]
        summary["manifest_size"] = manifest_path.stat().st_size
    except Exception:
        pass
    return summary


def _gzip_chunks(chunks_jsonl: pathlib.Path) -> pathlib.Path:
    gz_path = chunks_jsonl.with_suffix(chunks_jsonl.suffix + ".gz")
    with chunks_jsonl.open("rb") as fin, gzip.open(gz_path, "wb") as fout:
        fout.write(fin.read())
    return gz_path


def _build_release_body(build_meta: Optional[Dict[str, Any]], manifest_summary: Dict[str, Any]) -> str:
    meta = build_meta.copy() if build_meta else {}
    meta.update({k: v for k, v in manifest_summary.items() if v is not None})
    # 깔끔한 확인을 위해 JSON 요약 본문
    return "```json\n" + json.dumps(meta, ensure_ascii=False, indent=2) + "\n```"


def _create_release(token: str, repo: str, tag: str, name: str, body: str) -> Dict[str, Any]:
    url = f"{API_ROOT}/repos/{repo}/releases"
    resp = requests.post(
        url,
        headers=_headers(token),
        json={
            "tag_name": tag,
            "name": name,
            "body": body,
            "draft": False,
            "prerelease": False,
        },
        timeout=30,
    )
    if resp.status_code == 201:
        return resp.json()
    if resp.status_code == 422:
        # 이미 같은 tag의 릴리스가 있을 수 있음 → 기존 릴리스 재사용
        get_url = f"{API_ROOT}/repos/{repo}/releases/tags/{tag}"
        g = requests.get(get_url, headers=_headers(token), timeout=30)
        if g.status_code == 200:
            return g.json()
    raise GitHubReleaseError(f"릴리스 생성 실패: {resp.status_code} {resp.text}")


def _list_assets(token: str, repo: str, release_id: int) -> List[Dict[str, Any]]:
    url = f"{API_ROOT}/repos/{repo}/releases/{release_id}/assets"
    r = requests.get(url, headers=_headers(token), timeout=30)
    r.raise_for_status()
    return r.json()


def _delete_asset(token: str, repo: str, asset_id: int) -> None:
    url = f"{API_ROOT}/repos/{repo}/releases/assets/{asset_id}"
    r = requests.delete(url, headers=_headers(token), timeout=30)
    # 204 expected
    if r.status_code not in (204, 404):
        raise GitHubReleaseError(f"자산 삭제 실패: {r.status_code} {r.text}")


def _upload_asset(token: str, upload_url_template: str, asset_name: str, content: bytes, content_type: str) -> Dict[str, Any]:
    upload_url = upload_url_template.split("{")[0] + f"?name={asset_name}"
    headers = _headers(token).copy()
    headers["Content-Type"] = content_type
    r = requests.post(upload_url, headers=headers, data=content, timeout=120)
    if r.status_code not in (201, 200):
        raise GitHubReleaseError(f"자산 업로드 실패: {r.status_code} {r.text}")
    return r.json()


def _cleanup_old_releases(token: str, repo: str, keep: int = 2, tag_prefix: str = "index-") -> None:
    url = f"{API_ROOT}/repos/{repo}/releases?per_page=100"
    r = requests.get(url, headers=_headers(token), timeout=30)
    r.raise_for_status()
    releases = [rel for rel in r.json() if isinstance(rel.get("tag_name"), str) and rel["tag_name"].startswith(tag_prefix)]
    # 최신순 정렬
    releases.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    for rel in releases[keep:]:
        rel_id = rel["id"]
        tag = rel.get("tag_name", "")
        # 릴리스 삭제
        durl = f"{API_ROOT}/repos/{repo}/releases/{rel_id}"
        requests.delete(durl, headers=_headers(token), timeout=30)
        # 태그 삭제 (실패해도 계속)
        if tag:
            turl = f"{API_ROOT}/repos/{repo}/git/refs/tags/{tag}"
            requests.delete(turl, headers=_headers(token), timeout=30)


def upload_index_release(
    manifest_path: str | pathlib.Path,
    chunks_jsonl_path: str | pathlib.Path,
    *,
    repo: Optional[str] = None,
    token: Optional[str] = None,
    include_zip: bool = False,
    keep: int = 2,
    build_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    인덱싱 산출물 업로드 (성공 시 호출):
      - manifest.json
      - chunks.jsonl.gz (자동 생성)
      - (옵션) zip 번들
    """
    token, repo = _get_token_and_repo(token, repo)
    manifest = pathlib.Path(manifest_path).resolve()
    chunks_jsonl = pathlib.Path(chunks_jsonl_path).resolve()

    if not manifest.exists() or not chunks_jsonl.exists():
        raise GitHubReleaseError("산출물 경로 확인 실패 (manifest/chunks 누락)")

    tag, name = _ts_strings()
    manifest_summary = _read_manifest_summary(manifest)
    body = _build_release_body(build_meta, manifest_summary)

    # 릴리스 생성/가져오기
    release = _create_release(token, repo, tag, name, body)
    upload_url = release["upload_url"]
    release_id = release["id"]

    # 기존 동일 이름 자산이 있으면 삭제
    existing = _list_assets(token, repo, release_id)
    existing_map = {a.get("name"): a for a in existing if "name" in a}

    # chunks.jsonl.gz 생성
    gz_path = _gzip_chunks(chunks_jsonl)

    assets_to_upload: List[tuple[str, bytes, str]] = []
    assets_to_upload.append(("manifest.json", manifest.read_bytes(), "application/json"))
    assets_to_upload.append((gz_path.name, gz_path.read_bytes(), "application/gzip"))

    if include_zip:
        # maic-index-YYYYmmdd-HHMMSS.zip
        zip_name = f"{tag}.zip"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", manifest.read_bytes())
            zf.writestr(gz_path.name, gz_path.read_bytes())
        assets_to_upload.append((zip_name, buf.getvalue(), "application/zip"))

    # 업로드 (중복명 있으면 선삭제)
    for name_, content, ctype in assets_to_upload:
        if name_ in existing_map:
            try:
                _delete_asset(token, repo, existing_map[name_]["id"])
            except Exception:
                pass
        _upload_asset(token, upload_url, name_, content, ctype)

    # 보존 정책: 최신 2개만 유지
    _cleanup_old_releases(token, repo, keep=keep, tag_prefix="index-")

    return {
        "ok": True,
        "repo": repo,
        "tag": tag,
        "release_id": release_id,
        "assets": [a[0] for a in assets_to_upload],
    }
# [01] GITHUB RELEASE UPLOADER — END
