# =============================== [01] imports & types — START =========================
from __future__ import annotations

import io
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
# =============================== [01] imports & types — END ===========================


# =============================== [02] config & utils — START ==========================
@dataclass(frozen=True)
class GHConfig:
    owner: str
    repo: str
    token: Optional[str] = None


class _RestoreResult(dict):
    """단순 딕트 형태로 반환(app.py 호환)."""
    def __init__(self, tag: Optional[str], release_id: Optional[int]):
        super().__init__(tag=tag, release_id=release_id)
        self.tag = tag
        self.release_id = release_id
# =============================== [02] config & utils — END ============================


# =============================== [03] class GHReleases — START ========================
class GHReleases:
    """
    GitHub Releases 유틸.
    - restore_latest_index(): '최신 한 건'이 아니라 **여러 릴리스**를 훑어서
      index 자산이 들어있는 첫 릴리스를 찾아 복원한다.
    """

    # 기본 자산 패턴(모두 소문자 비교)
    DEFAULT_ASSET_GLOBS = [
        "*indices*.zip",   # indices.zip / indices-*.zip ...
        "*index*.zip",     # index.zip / index-*.zip ...
        "*persist*.zip",   # persist.zip / persist-*.zip ...
        "*hq_index*.zip",  # hq_index.zip ...
        "*prepared*.zip",  # prepared.zip ...
    ]

    def __init__(self, cfg: GHConfig):
        self.cfg = cfg

    # ---------- HTTP ----------
    def _headers(self, accept_json: bool = True) -> Dict[str, str]:
        h = {"Accept": "application/vnd.github+json" if accept_json else "*/*"}
        if self.cfg.token:
            h["Authorization"] = f"Bearer {self.cfg.token}"
        return h

    def _get_json(self, url: str, timeout: int = 20) -> Any:
        r = requests.get(url, headers=self._headers(True), timeout=timeout)
        r.raise_for_status()
        return r.json()

    def _get_bytes(self, url: str, timeout: int = 60) -> bytes:
        r = requests.get(url, headers=self._headers(False), timeout=timeout, stream=True)
        r.raise_for_status()
        buf = io.BytesIO()
        for chunk in r.iter_content(chunk_size=256 * 1024):
            if chunk:
                buf.write(chunk)
        return buf.getvalue()

    # ---------- Releases ----------
    def get_release_by_tag(self, tag: str) -> dict:
        u = f"https://api.github.com/repos/{self.cfg.owner}/{self.cfg.repo}/releases/tags/{tag}"
        return self._get_json(u)

    def get_latest_release(self) -> dict:
        u = f"https://api.github.com/repos/{self.cfg.owner}/{self.cfg.repo}/releases/latest"
        return self._get_json(u)

    def list_releases(self, *, per_page: int = 20, max_pages: int = 5) -> Iterable[dict]:
        """
        최신 → 오래된 순으로 여러 릴리스를 스트리밍.
        draft 릴리스는 건너뛴다(보통 자산이 불완전).
        """
        for page in range(1, max_pages + 1):
            url = (
                f"https://api.github.com/repos/{self.cfg.owner}/{self.cfg.repo}/releases"
                f"?per_page={per_page}&page={page}"
            )
            data = self._get_json(url)
            if not isinstance(data, list) or not data:
                break
            for rel in data:
                if rel.get("draft") is True:
                    continue
                yield rel
            if len(data) < per_page:
                break

    # ---------- helpers ----------
    @staticmethod
    def _compile_glob(glob: str) -> re.Pattern:
        esc = re.escape(glob).replace(r"\*", ".*").replace(r"\?", ".")
        return re.compile(rf"^{esc}$", re.I)

    @classmethod
    def _normalize_patterns(
        cls, candidates: Optional[Iterable[str]]
    ) -> List[re.Pattern]:
        globs = list(cls.DEFAULT_ASSET_GLOBS)
        for c in candidates or []:
            c = (c or "").strip()
            if not c:
                continue
            if "." not in c:
                globs += [c, f"{c}.zip", f"*{c}*.zip"]
            else:
                globs.append(c)
                if "*" not in c and "?" not in c:
                    globs.append(f"*{c}*")
        # dedup
        seen, uniq = set(), []
        for g in globs:
            g2 = g.lower()
            if g2 in seen:
                continue
            seen.add(g2)
            uniq.append(g)
        return [cls._compile_glob(g) for g in uniq]

    @staticmethod
    def _pick_asset_from_release(rel: dict, patterns: List[re.Pattern]) -> Optional[dict]:
        assets = rel.get("assets") or []
        for a in assets:
            name = (a.get("name") or "").lower()
            if not name or "source code" in name:
                continue
            if any(p.match(name) for p in patterns):
                return a
        return None

    @staticmethod
    def _is_zip_member_safe(member: zipfile.ZipInfo, dest: Path) -> bool:
        # ZipSlip 방지
        target = (dest / member.filename).resolve()
        return str(target).startswith(str(dest.resolve()))

    @staticmethod
    def _extract_zip_safely(zip_bytes: bytes, dest: Path) -> None:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for m in zf.infolist():
                if not GHReleases._is_zip_member_safe(m, dest):
                    raise RuntimeError(f"Unsafe zip path detected: {m.filename}")
            zf.extractall(dest)

    # ---------- core ----------
    def restore_latest_index(
        self,
        *,
        tag_candidates: Optional[Iterable[str]] = None,
        asset_candidates: Optional[Iterable[str]] = None,
        dest: Path | str,
        clean_dest: bool = True,
        scan_pages: int = 5,
    ) -> _RestoreResult:
        """
        최신 인덱스 자산(zip)을 찾아 dest에 복원.
        절차:
          1) tag_candidates 순서대로 시도
          2) 실패 시 최신 릴리스 목록을 page=1..scan_pages 순회하며
             첫 번째 '자산 패턴 일치' 릴리스를 사용
        """
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)

        patterns = self._normalize_patterns(asset_candidates)

        # 1) 태그 우선
        chosen_rel: Optional[dict] = None
        chosen_asset: Optional[dict] = None
        if tag_candidates:
            for tg in tag_candidates:
                try:
                    rel = self.get_release_by_tag(tg)
                except Exception:
                    continue
                a = self._pick_asset_from_release(rel, patterns)
                if a:
                    chosen_rel, chosen_asset = rel, a
                    break

        # 2) 릴리스 다건 스캔
        if chosen_asset is None:
            for rel in self.list_releases(per_page=20, max_pages=scan_pages):
                a = self._pick_asset_from_release(rel, patterns)
                if a:
                    chosen_rel, chosen_asset = rel, a
                    break

        if chosen_asset is None or chosen_rel is None:
            patt = ", ".join(p.pattern for p in patterns)
            raise RuntimeError(f"index asset not found across recent releases (patterns={patt})")

        url = chosen_asset.get("browser_download_url")
        if not url:
            raise RuntimeError("chosen asset has no browser_download_url")

        # 다운로드
        data = self._get_bytes(url)

        # 복원
        if clean_dest:
            for item in dest.iterdir():
                if item.is_file():
                    item.unlink(missing_ok=True)
                else:
                    shutil.rmtree(item, ignore_errors=True)
        self._extract_zip_safely(data, dest)

        # 무결성 힌트
        if not (dest / "chunks.jsonl").exists():
            raise RuntimeError("restored archive does not contain 'chunks.jsonl'")

        tag = (chosen_rel.get("tag_name") or chosen_rel.get("name") or "").strip() or None
        rid = chosen_rel.get("id")
        return _RestoreResult(tag=tag, release_id=rid)
# =============================== [03] class GHReleases — END ==========================
