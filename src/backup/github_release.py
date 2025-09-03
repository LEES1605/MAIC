# ===== [01] COMMON HELPERS =====================================================  # [01] START
from __future__ import annotations

import os
import importlib
from typing import Any, Dict
from pathlib import Path  # E402 방지: Path를 최상단에서 임포트

API = "https://api.github.com"


def _log(msg: str) -> None:
    """프로젝트 어디서 호출해도 안전한 초간단 로거."""
    try:
        # 동적 임포트로 mypy attr-defined 회피
        mod = importlib.import_module("src.state.session")
        fn = getattr(mod, "append_admin_log", None)
        if callable(fn):
            fn(str(msg))
            return
    except Exception:
        pass
    try:
        import logging
        logging.getLogger("maic.backup").info(str(msg))
    except Exception:
        # 최후 수단
        print(str(msg))


def _get_env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return v if isinstance(v, str) and v.strip() else default


def _token() -> str:
    t = _get_env("GITHUB_TOKEN")
    if t:
        return t
    # 동적 임포트로 mypy import-not-found 회피
    try:
        mod = importlib.import_module("src.backup.github_config")
        tk = getattr(mod, "GITHUB_TOKEN", "")
        return str(tk) if tk else ""
    except Exception:
        return ""


def _repo() -> str:
    r = _get_env("GITHUB_REPO")
    if r:
        return r
    try:
        mod = importlib.import_module("src.backup.github_config")
        rp = getattr(mod, "GITHUB_REPO", "")
        return str(rp) if rp else ""
    except Exception:
        return ""


def _branch() -> str:
    b = _get_env("GITHUB_BRANCH", "main")
    if b:
        return b
    try:
        mod = importlib.import_module("src.backup.github_config")
        br = getattr(mod, "GITHUB_BRANCH", "main")
        return str(br or "main")
    except Exception:
        return "main"


def _headers() -> Dict[str, str]:
    """GitHub API 공통 헤더."""
    t = _token()
    h: Dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "maic-backup-bot",
    }
    if t:
        h["Authorization"] = f"Bearer {t}"
    return h


def _upload_headers(content_type: str) -> Dict[str, str]:
    h = _headers()
    h["Content-Type"] = content_type
    return h
# ===== [01] COMMON HELPERS =====================================================  # [01] END


# ===== [02] CONSTANTS & PUBLIC EXPORTS =======================================  # [02] START
__all__ = ["restore_latest", "get_latest_release", "publish_backup"]
# [02] END =====================================================================


# ===== [03] LEGACY PUBLISH PLACEHOLDER ========================================  # [03] START
"""
[DEPRECATED]
이 구획의 publish_backup 구현은 폐기되었습니다.
실제 구현은 [07] 구획의 `publish_backup`를 사용하세요.
본 섹션은 중복 정의(F811)를 방지하기 위한 플레이스홀더입니다.
"""
# (함수 정의 없음)
# ===== [03] LEGACY PUBLISH PLACEHOLDER ========================================  # [03] END




# ===== [04] RELEASE DISCOVERY =================================================  # [04] START
def _latest_release(repo: str) -> dict | None:
    """가장 최신 릴리스를 조회. 실패 시 None."""
    if not repo:
        _log("GITHUB_REPO가 설정되지 않았습니다.")
        return None
    import requests  # E402 회피: 함수 내부 로컬 임포트
    url = f"{API}/repos/{repo}/releases/latest"
    try:
        r = requests.get(url, headers=_headers(), timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _log(f"최신 릴리스 조회 실패: {type(e).__name__}: {e}")
        return None


def get_latest_release(repo: str | None = None) -> dict | None:
    """
    PUBLIC API: 최신 GitHub 릴리스를 반환합니다.
    - repo 인자가 없으면 secrets/env의 GITHUB_REPO를 사용합니다.
    - 요청/파싱 실패 시 None을 반환합니다(예외 발생하지 않음).
    """
    target = (repo or _repo()).strip()
    rel = _latest_release(target)
    if rel is None:
        return None
    # 최소 필드 정규화(호출측 편의)
    if "tag_name" not in rel and "name" in rel:
        rel["tag_name"] = rel.get("name")
    return rel


def _pick_best_asset(rel: dict) -> dict | None:
    """릴리스 자산 중 우선순위(.zip > .tar.gz > .gz > 첫 번째)를 선택."""
    assets = rel.get("assets") or []
    if not assets:
        return None
    for a in assets:
        if str(a.get("name", "")).lower().endswith(".zip"):
            return a
    for a in assets:
        if str(a.get("name", "")).lower().endswith(".tar.gz"):
            return a
    for a in assets:
        if str(a.get("name", "")).lower().endswith(".gz"):
            return a
    return assets[0] if assets else None
# [04] END



# ===== [05] ASSET DOWNLOAD & EXTRACT =========================================  # [05] START
def _download_asset(asset: dict) -> bytes | None:
    """GitHub 릴리스 자산을 내려받아 바이트로 반환. 실패 시 None."""
    url = asset.get("url") or asset.get("browser_download_url")
    if not url:
        return None
    try:
        import requests  # E402 회피: 함수 내부 로컬 임포트
        # GitHub 'assets/:id' API는 application/octet-stream을 요구
        hdrs = dict(_headers())
        if "releases/assets/" in url and "browser_download_url" not in asset:
            hdrs["Accept"] = "application/octet-stream"
        r = requests.get(url, headers=hdrs, timeout=60)
        r.raise_for_status()
        return r.content
    except Exception as e:
        _log(f"자산 다운로드 실패: {type(e).__name__}: {e}")
        return None


def _extract_zip(data: bytes, dest_dir: Path) -> bool:
    """ZIP 바이트를 dest_dir에 풀기. 성공 True/실패 False."""
    try:
        import io, zipfile  # E402 회피: 함수 내부 로컬 임포트
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(dest_dir)
        return True
    except Exception as e:
        _log(f"압축 해제 실패(zip): {type(e).__name__}: {e}")
        return False


def _extract_targz(data: bytes, dest_dir: Path) -> bool:
    """TAR.GZ / TGZ 바이트를 dest_dir에 풀기."""
    try:
        import tarfile, io  # E402 회피
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            tf.extractall(dest_dir)
        return True
    except Exception as e:
        _log(f"압축 해제 실패(tar.gz): {type(e).__name__}: {e}")
        return False


def _extract_gz_to_file(asset_name: str, data: bytes, dest_dir: Path) -> bool:
    """단일 .gz(예: chunks.jsonl.gz)를 dest_dir/<basename>으로 풀기."""
    try:
        import gzip, io  # E402 회피
        base = asset_name[:-3] if asset_name.lower().endswith(".gz") else asset_name
        out_path = dest_dir / base
        with gzip.GzipFile(fileobj=io.BytesIO(data), mode="rb") as gf:
            out_path.write_bytes(gf.read())
        return True
    except Exception as e:
        _log(f"압축 해제 실패(gz): {type(e).__name__}: {e}")
        return False


def _extract_auto(asset_name: str, data: bytes, dest_dir: Path) -> bool:
    """자산 이름으로 형식을 유추하여 적절히 해제."""
    n = (asset_name or "").lower()
    if n.endswith(".zip"):
        return _extract_zip(data, dest_dir)
    if n.endswith(".tar.gz") or n.endswith(".tgz"):
        return _extract_targz(data, dest_dir)
    if n.endswith(".gz"):
        return _extract_gz_to_file(asset_name, data, dest_dir)
    # 알 수 없는 형식: zip 시도(실패 시 False)
    return _extract_zip(data, dest_dir)
# [05] END =====================================================================


# ===== [06] PUBLIC API: restore_latest =======================================  # [06] START
def restore_latest(dest_dir: str | Path) -> bool:
    """최신 GitHub Release에서 아티팩트를 내려받아 dest_dir에 복원.

    반환:
        성공 시 True, 실패 시 False (예외는 올리지 않음)

    비고:
        - .zip/.tar.gz/.tgz/.gz 모두 처리
        - 압축 해제 결과가 '최상위 단일 폴더'일 경우, 그 폴더를 한 겹 평탄화하여
          폴더 내부의 파일/디렉터리를 dest_dir 바로 아래로 복사한다.
        - 이후 dest 내 산출물을 정리하여 chunks.jsonl을 루트로 모으고 .ready를 보정한다.
    """
    # E402 회피: 함수 내부 로컬 임포트
    import tempfile, shutil

    dest = Path(dest_dir).expanduser()
    dest.mkdir(parents=True, exist_ok=True)

    repo = _repo()
    if not repo:
        _log("restore_latest: GITHUB_REPO 미설정")
        return False

    rel = _latest_release(repo)
    if not rel:
        return False

    name = rel.get("name") or rel.get("tag_name") or "(no-tag)"
    _log(f"최신 릴리스: {name}")

    asset = _pick_best_asset(rel)
    if not asset:
        _log("릴리스에 다운로드 가능한 자산이 없습니다.")
        return False

    asset_name = str(asset.get("name") or "")
    _log(f"자산 다운로드: {asset_name}")
    data = _download_asset(asset)
    if not data:
        return False

    # 임시 디렉터리를 사용해 원자적 교체에 가깝게 복원
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # 1) 압축 해제 (.zip/.tar.gz/.tgz/.gz 자동 판별)
        ok = _extract_auto(asset_name, data, tmp)
        if not ok:
            return False

        # 2) '최상위 단일 폴더' 감지 → 평탄화 대상 루트 결정
        children = [
            p
            for p in tmp.iterdir()
            if p.name not in (".DS_Store",) and not p.name.startswith("__MACOSX")
        ]
        src_root = tmp
        if len(children) == 1 and children[0].is_dir():
            src_root = children[0]
            _log("평탄화 적용: 최상위 폴더 내부를 루트로 승격")
            _log(f"승격 대상 폴더: '{src_root.name}'")

        # 3) 복사(기존 동일 경로는 교체). '폴더 자체'가 아니라 '폴더 내부'를 복사한다.
        for p in src_root.iterdir():
            target = dest / p.name
            try:
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                if p.is_dir():
                    shutil.copytree(p, target)
                else:
                    shutil.copy2(p, target)
            except Exception as e:
                _log("파일 복사 실패(일부 항목). 다음 라인에 상세 표시.")
                _log(f"원본: {p.name} → 대상: {target.name} — {type(e).__name__}: {e}")
                return False

    # 4) 산출물 정리(강화): dest 안에서 chunks.jsonl을 루트로 모으기
    def _size(p: Path) -> int:
        try:
            return p.stat().st_size
        except Exception:
            return 0

    def _decompress_gz(src: Path, dst: Path) -> bool:
        try:
            import gzip
            with gzip.open(src, "rb") as gf:
                data2 = gf.read()
            if not data2:
                return False
            dst.write_bytes(data2)
            return True
        except Exception as e:
            _log(f"gz 해제 실패: {type(e).__name__}: {e}")
            return False

    def _merge_dir_jsonl(chunk_dir: Path, out_file: Path) -> bool:
        """chunk_dir 안의 *.jsonl을 라인 보존으로 병합한다."""
        try:
            bytes_written = 0
            tmp_out = out_file.with_suffix(".jsonl.tmp")
            if tmp_out.exists():
                tmp_out.unlink()
            with tmp_out.open("wb") as w:
                for p in sorted(chunk_dir.glob("*.jsonl")):
                    try:
                        with p.open("rb") as r:
                            while True:
                                buf = r.read(1024 * 1024)
                                if not buf:
                                    break
                                w.write(buf)
                                bytes_written += len(buf)
                    except Exception:
                        continue
            if bytes_written > 0:
                if out_file.exists():
                    out_file.unlink()
                tmp_out.replace(out_file)
                return True
            tmp_out.unlink(missing_ok=True)
            return False
        except Exception as e:
            _log(f"chunks/ 병합 실패: {type(e).__name__}: {e}")
            return False

    target = dest / "chunks.jsonl"

    def _consolidate_to_target(root: Path, target_file: Path) -> bool:
        # 이미 유효하면 끝
        if target_file.exists() and _size(target_file) > 0:
            return True

        # a) 정확명 우선: chunks.jsonl / chunks.jsonl.gz (임의 깊이)
        try:
            exact = [p for p in root.rglob("chunks.jsonl") if _size(p) > 0]
        except Exception:
            exact = []
        if exact:
            best = max(exact, key=_size)
            shutil.copy2(best, target_file)
            _log(f"exact chunks.jsonl 사용: {best}")
            return True

        try:
            exact_gz = [p for p in root.rglob("chunks.jsonl.gz") if _size(p) > 0]
        except Exception:
            exact_gz = []
        if exact_gz:
            best_gz = max(exact_gz, key=_size)
            if _decompress_gz(best_gz, target_file):
                _log(f"exact chunks.jsonl.gz 해제: {best_gz}")
                return True

        # b) 디렉터리 병합: */chunks/*.jsonl
        try:
            chunk_dirs = [d for d in root.rglob("chunks") if d.is_dir()]
        except Exception:
            chunk_dirs = []
        for d in chunk_dirs:
            if _merge_dir_jsonl(d, target_file):
                _log(f"디렉터리 병합 사용: {d}")
                return True

        # c) 범용 파일: 임의의 *.jsonl / *.jsonl.gz 중 가장 큰 것 선택
        try:
            any_jsonl = [p for p in root.rglob("*.jsonl") if _size(p) > 0]
        except Exception:
            any_jsonl = []
        if any_jsonl:
            best_any = max(any_jsonl, key=_size)
            shutil.copy2(best_any, target_file)
            _log(f"임의 *.jsonl 사용: {best_any}")
            return True

        try:
            any_gz = [p for p in root.rglob("*.jsonl.gz") if _size(p) > 0]
        except Exception:
            any_gz = []
        if any_gz:
            best_any_gz = max(any_gz, key=_size)
            if _decompress_gz(best_any_gz, target_file):
                _log(f"임의 *.jsonl.gz 해제: {best_any_gz}")
                return True

        # 실패 시 0바이트 target이 있으면 제거
        if target_file.exists() and _size(target_file) == 0:
            target_file.unlink(missing_ok=True)
        return False

    ok_cons = _consolidate_to_target(dest, target)

    # 🔁 최종 폴백: 릴리스 자산이 chunks.jsonl.gz 단일 파일인 경우, 원본 바이트로 직접 해제
    if not ok_cons and asset_name.lower().endswith(".gz") and data:
        try:
            import gzip
            raw = gzip.decompress(data)
            if raw:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                _log("자산 바이트 직접 해제: chunks.jsonl 생성(폴백)")
                ok_cons = True
        except Exception as e:
            _log(f"폴백 해제 실패: {type(e).__name__}: {e}")

    if not ok_cons:
        _log("산출물 정리 실패: chunks.jsonl을 만들 수 없습니다.")
        # READY 보정 없이 종료
        return False

    # 5) SSOT 보정: chunks.jsonl만 존재하고 .ready가 없으면 생성
    try:
        chunks = dest / "chunks.jsonl"
        ready = dest / ".ready"
        if chunks.exists() and chunks.stat().st_size > 0 and not ready.exists():
            ready.write_text("ok", encoding="utf-8")
    except Exception:
        pass

    _log("복원이 완료되었습니다.")
    return True
# ===== [06] PUBLIC API: restore_latest =======================================  # [06] END


# ===== [07] PUBLIC API: publish_backup =======================================  # [07] START
def publish_backup(persist_dir, keep: int = 5) -> bool:
    """
    로컬 인덱스를 GitHub 릴리스에 백업한다.
    업로드: chunks.jsonl.gz, manifest.json
    태그: index-YYYYMMDD-HHMMSS (가능하면 기존 manifest.build_id 사용)
    보존: 'index-' 접두 릴리스 최근 keep개만 보존
    """
    import io
    import json
    import gzip
    import time
    import hashlib
    import urllib.parse
    from typing import Any
    from pathlib import Path

    try:
        import requests  # 프로젝트 의존성 가정
    except Exception:
        _log("publish_backup: requests 모듈이 없습니다.")
        return False

    def _as_path(p) -> Path:
        return p if isinstance(p, Path) else Path(str(p))

    def _sha256_file(p: Path) -> str:
        h = hashlib.sha256()
        with p.open("rb") as r:
            for chunk in iter(lambda: r.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _count_lines(p: Path) -> int:
        cnt = 0
        with p.open("rb") as f:
            for b in iter(lambda: f.read(1024 * 1024), b""):
                cnt += b.count(b"\n")
        return cnt

    # mypy-safe 캐스팅 헬퍼
    def _as_int(v: Any, default: int) -> int:
        try:
            if v is None:
                return default
            if isinstance(v, bool):
                return int(v)
            if isinstance(v, int):
                return v
            if isinstance(v, float):
                return int(v)
            if isinstance(v, (bytes, bytearray)):
                s = v.decode(errors="ignore").strip()
                return int(s) if s else default
            if isinstance(v, str):
                s = v.strip()
                return int(s) if s else default
            # 최후 수단
            return int(v)
        except Exception:
            return default

    base = _as_path(persist_dir)
    chunks = base / "chunks.jsonl"
    manifest = base / "manifest.json"

    if not chunks.exists() or chunks.stat().st_size == 0:
        _log("publish_backup: chunks.jsonl 이 없거나 비어 있습니다.")
        return False

    repo = _repo()
    if not repo:
        _log("publish_backup: GITHUB_REPO 미설정")
        return False

    # manifest 보정/생성
    mode = (_get_env("MAIC_INDEX_MODE", "STD") or "STD").upper()
    build_id = time.strftime("%Y%m%d-%H%M%S")
    manifest_obj: dict[str, Any] = {}
    try:
        if manifest.exists():
            manifest_obj = json.loads(manifest.read_text(encoding="utf-8") or "{}")
            build_id = str(manifest_obj.get("build_id") or build_id)
            manifest_obj["mode"] = str(manifest_obj.get("mode") or mode)
            manifest_obj["sha256"] = (
                manifest_obj.get("sha256") or _sha256_file(chunks)
            )
            manifest_obj["chunks"] = _as_int(manifest_obj.get("chunks"), _count_lines(chunks))
            manifest_obj["file"] = "chunks.jsonl"
            manifest_obj["persist_dir"] = str(base)
            manifest_obj["version"] = _as_int(manifest_obj.get("version"), 2)
        else:
            manifest_obj = {
                "build_id": build_id,
                "created_at": int(time.time()),
                "mode": mode,
                "file": "chunks.jsonl",
                "sha256": _sha256_file(chunks),
                "chunks": _count_lines(chunks),
                "persist_dir": str(base),
                "version": 2,
            }
            manifest.write_text(
                json.dumps(manifest_obj, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except Exception as e:
        _log(f"publish_backup: manifest 생성/보정 실패: {e}")
        return False

    tag = f"index-{build_id}"
    rel_name = f"{tag} ({mode})"

    session = requests.Session()
    session.headers.update(_headers())

    # 릴리스 생성/획득
    try:
        payload = {
            "tag_name": tag,
            "name": rel_name,
            "target_commitish": _branch(),
            "body": (
                "Automated index backup\n"
                f"- mode: {mode}\n"
                f"- chunks: {manifest_obj.get('chunks')}\n"
                f"- sha256: {manifest_obj.get('sha256')}\n"
            ),
            "draft": False,
            "prerelease": False,
        }
        r = session.post(
            f"{API}/repos/{repo}/releases", json=payload, timeout=30
        )
        if r.status_code not in (201, 422):
            _log(f"publish_backup: 릴리스 생성 실패: {r.status_code} {r.text}")
            return False

        rel = r.json()
        if r.status_code == 422:
            rr = session.get(
                f"{API}/repos/{repo}/releases/tags/{tag}", timeout=15
            )
            if rr.status_code != 200:
                _log(
                    f"publish_backup: 기존 릴리스 조회 실패: "
                    f"{rr.status_code} {rr.text}"
                )
                return False
            rel = rr.json()

        upload_url_tpl = str(rel.get("upload_url") or "")
        upload_url = upload_url_tpl.split("{")[0]
        rel_id = rel.get("id")
        if not upload_url or not rel_id:
            _log("publish_backup: upload_url/release id 획득 실패")
            return False
    except Exception as e:
        _log(f"publish_backup: 릴리스 생성/조회 예외: {e}")
        return False

    # 에셋 업로드
    try:
        # chunks.jsonl.gz
        gz = io.BytesIO()
        with gzip.GzipFile(fileobj=gz, mode="wb") as gzfp:
            gzfp.write(chunks.read_bytes())
        asset_name = "chunks.jsonl.gz"
        q = urllib.parse.urlencode({"name": asset_name})
        urla = f"{upload_url}?{q}"
        ra = session.post(
            urla,
            data=gz.getvalue(),
            headers=_upload_headers("application/gzip"),
            timeout=60,
        )
        if ra.status_code == 422:
            assets = session.get(
                f"{API}/repos/{repo}/releases/{rel_id}/assets", timeout=15
            ).json()
            old = next((a for a in assets if a.get("name") == asset_name), None)
            if old:
                aid = old.get("id")
                session.delete(f"{API}/releases/assets/{aid}", timeout=15)
                ra = session.post(
                    urla,
                    data=gz.getvalue(),
                    headers=_upload_headers("application/gzip"),
                    timeout=60,
                )
        if ra.status_code not in (201, 200):
            _log(f"publish_backup: chunks 업로드 실패: {ra.status_code} {ra.text}")
            return False

        # manifest.json
        m_name = "manifest.json"
        qm = urllib.parse.urlencode({"name": m_name})
        urlm = f"{upload_url}?{qm}"
        rm = session.post(
            urlm,
            data=json.dumps(manifest_obj, ensure_ascii=False).encode("utf-8"),
            headers=_upload_headers("application/json"),
            timeout=30,
        )
        if rm.status_code == 422:
            assets = session.get(
                f"{API}/repos/{repo}/releases/{rel_id}/assets", timeout=15
            ).json()
            old = next((a for a in assets if a.get("name") == m_name), None)
            if old:
                aid = old.get("id")
                session.delete(f"{API}/releases/assets/{aid}", timeout=15)
                rm = session.post(
                    urlm,
                    data=json.dumps(manifest_obj, ensure_ascii=False).encode("utf-8"),
                    headers=_upload_headers("application/json"),
                    timeout=30,
                )
        if rm.status_code not in (201, 200):
            _log(f"publish_backup: manifest 업로드 실패: {rm.status_code} {rm.text}")
            return False
    except Exception as e:
        _log(f"publish_backup: 에셋 업로드 예외: {e}")
        return False

    # 보존 정책 적용
    try:
        rels = []
        page = 1
        while True:
            rr = session.get(
                f"{API}/repos/{repo}/releases",
                params={"per_page": 100, "page": page},
                timeout=15,
            )
            if rr.status_code != 200:
                break
            batch = rr.json()
            if not isinstance(batch, list) or not batch:
                break
            rels.extend(batch)
            if len(batch) < 100:
                break
            page += 1

        # index-* 만
        index_rels = [
            r for r in rels
            if isinstance(r.get("tag_name"), str)
            and str(r.get("tag_name")).startswith("index-")
        ]
        index_rels.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        to_delete = index_rels[keep:] if keep > 0 else index_rels
        for item in to_delete:
            rid = item.get("id")
            tname = item.get("tag_name", "")
            if not rid:
                continue
            session.delete(f"{API}/repos/{repo}/releases/{rid}", timeout=15)
            if tname:
                session.delete(
                    f"{API}/repos/{repo}/git/refs/tags/{tname}", timeout=15
                )
    except Exception as e:
        _log(f"publish_backup: 보존 정책 예외(무시): {e}")

    _log(f"publish_backup: 완료 — tag={tag}, repo={repo}")
    return True
# ===== [07] PUBLIC API: publish_backup =======================================  # [07] END

