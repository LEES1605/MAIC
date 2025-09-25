# =============================== [01] imports & types — START =========================
from __future__ import annotations

import io
import os
import re
import json
import time
import shutil
import zipfile
import hashlib
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
    """단순 딕트 형태로 반환(기존 app.py 호환)."""
    def __init__(self, tag: Optional[str], release_id: Optional[int]):
        super().__init__(tag=tag, release_id=release_id)
        self.tag = tag
        self.release_id = release_id
# =============================== [02] config & utils — END ============================


# =============================== [03] class GHReleases — START ========================
class GHReleases:
    """
    GitHub Releases 헬퍼.
    - 'restore_latest_index()'에서 자산 이름을 광범위 패턴으로 탐지하여
      index-타임스탬프 릴리스/자산에도 견고하게 동작.
    """

    # 기본 패턴(필터는 '소문자' 기준, fnmatch 유사: *와 ?를 지원)
    DEFAULT_ASSET_GLOBS = [
        "*indices*.zip",   # indices.zip / indices-YYYYMMDD.zip …
        "*index*.zip",     # index.zip / index-1758719924.zip …
        "*persist*.zip",   # persist.zip / persist-latest.zip …
        "*hq_index*.zip",  # hq_index.zip …
        "*prepared*.zip",  # prepared.zip …
    ]

    def __init__(self, cfg: GHConfig):
        self.cfg = cfg

    # ---------- HTTP ----------
    def _headers(self, accept_json: bool = True) -> Dict[str, str]:
        h = {"Accept": "application/vnd.github+json" if accept_json else "*/*"}
        if self.cfg.token:
            h["Authorization"] = f"Bearer {self.cfg.token}"
        return h

    def _get_json(self, url: str, timeout: int = 20) -> dict:
        r = requests.get(url, headers=self._headers(True), timeout=timeout)
        r.raise_for_status()
        return r.json()

    def _get_bytes(self, url: str, timeout: int = 60) -> bytes:
        r = requests.get(url, headers=self._headers(False), timeout=timeout, stream=True)
        r.raise_for_status()
        buf = io.BytesIO()
        for chunk in r.iter_content(chunk_size=1024 * 256):
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

    # ---------- helpers ----------
    @staticmethod
    def _compile_glob(glob: str) -> re.Pattern:
        # 단순 와일드카드(*, ?) → 정규식
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
            # 확장자 없으면 '.zip'도 허용
            if "." not in c:
                globs.append(c)
                globs.append(f"{c}.zip")
                globs.append(f"*{c}*.zip")
            else:
                globs.append(c)
                # glob 문자가 없다면 양쪽 확장: "*name*"
                if "*" not in c and "?" not in c:
                    globs.append(f"*{c}*")
        # 중복 제거
        seen, uniq = set(), []
        for g in globs:
            g2 = g.lower()
            if g2 in seen:
                continue
            seen.add(g2)
            uniq.append(g)
        return [cls._compile_glob(g) for g in uniq]

    @staticmethod
    def _is_zip_member_safe(member: zipfile.ZipInfo, dest: Path) -> bool:
        # ZipSlip 방지: 추출 경로가 dest 밖으로 벗어나지 않는지 확인
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
    ) -> _RestoreResult:
        """
        최신 인덱스 자산(zip)을 다운로드 → dest에 복원.
        - tag_candidates: 우선 고려할 태그 목록(없으면 latest)
        - asset_candidates: 자산명 후보(없어도 DEFAULT_ASSET_GLOBS로 탐색)
        - dest: 복원 대상 디렉터리
        """
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)

        # 1) 릴리스 선택
        rel: Optional[dict] = None
        tried_tags: List[str] = []
        if tag_candidates:
            for tg in tag_candidates:
                try:
                    rel = self.get_release_by_tag(tg)
                    break
                except Exception:
                    tried_tags.append(tg)
                    rel = None
        if rel is None:
            rel = self.get_latest_release()

        tag = (rel.get("tag_name") or rel.get("name") or "").strip() or None
        release_id = rel.get("id")
        assets = rel.get("assets") or []

        # 2) 자산 선택(광범위 패턴)
        patterns = self._normalize_patterns(asset_candidates)
        chosen = None
        for a in assets:
            name = (a.get("name") or "").strip()
            name_lc = name.lower()
            # “source code (zip)” 같은 자동 항목은 assets[]에 안 오지만 혹시 모를 잡음 방지
            if not name or "source code" in name_lc:
                continue
            if any(pat.match(name_lc) for pat in patterns):
                chosen = a
                break
        if not chosen:
            cand_list = ", ".join(sorted({p.pattern for p in patterns}))
            raise RuntimeError(
                f"index asset not found in release '{tag or release_id}'. "
                f"patterns={cand_list}"
            )

        url = chosen.get("browser_download_url")
        if not url:
            raise RuntimeError("chosen asset has no browser_download_url")

        # 3) 다운로드
        data = self._get_bytes(url)

        # 4) 정리 & 복원
        if clean_dest:
            for item in dest.iterdir():
                if item.is_file():
                    item.unlink(missing_ok=True)
                else:
                    shutil.rmtree(item, ignore_errors=True)

        self._extract_zip_safely(data, dest)

        # 5) 간단 무결성 힌트(옵션): 파일 존재 체크
        chunks = dest / "chunks.jsonl"
        ready = dest / ".ready"
        if not chunks.exists():
            raise RuntimeError("restored archive does not contain 'chunks.jsonl'")
        # '.ready'가 없더라도 상위에서 normalize_ready_file()이 채운다.

        return _RestoreResult(tag=tag, release_id=release_id)
# =============================== [03] class GHReleases — END ==========================
