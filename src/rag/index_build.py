# [01] 기본 설정 & 상수  # [01] START
from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path
from typing import Any, Dict  # List, Optional, Tuple 제거 (ruff F401 대응)

# 퍼시스트 디렉토리(인덱스/매니페스트 저장)
PERSIST_DIR = Path.home() / ".maic" / "persist"
PERSIST_DIR.mkdir(parents=True, exist_ok=True)

# 인덱싱 대상 확장자(감지/인덱싱 동일 규칙)
ALLOWED_EXTS = (".md", ".txt", ".pdf", ".csv", ".zip")

# manifest 경로
MANIFEST_PATH = PERSIST_DIR / "manifest.json"

# prepared 폴더 식별 (이름 또는 ID 직접 지정)
PREPARED_FOLDER_NAME = os.getenv("MAIC_PREPARED_FOLDER_NAME", "prepared")
PREPARED_FOLDER_ID = os.getenv("MAIC_PREPARED_FOLDER_ID")  # 있으면 이 ID 우선

# Google 인증
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

# 최대 파일 크기(안전)
MAX_BYTES = 64 * 1024 * 1024  # 64MB
# [01] END


# [02] 공통 유틸  # [02] START
def _log(msg: str) -> None:
    try:
        import streamlit as st

        st.write(msg)
    except Exception:
        print(msg)


def _write_json(path: Path, obj: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
# [02] END

# [03] ZIP 스냅샷 생성/복원  # [03] START
def _pack_snapshot(data: Dict[str, Any]) -> bytes:
    """
    manifest.json, chunks.jsonl 형태로 간단 ZIP 패키지 생성.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(data.get("manifest", {}), ensure_ascii=False))
        chunks = data.get("chunks") or []
        text = "\n".join(json.dumps(c, ensure_ascii=False) for c in chunks)
        zf.writestr("chunks.jsonl", text)
    buf.seek(0)
    return buf.read()


def _unpack_snapshot(blob: bytes) -> Dict[str, Any]:
    with zipfile.ZipFile(io.BytesIO(blob), "r") as zf:
        out: Dict[str, Any] = {"manifest": {}, "chunks": []}  # ← 타입 명시 추가
        try:
            out["manifest"] = json.loads(zf.read("manifest.json").decode("utf-8"))
        except Exception:
            out["manifest"] = {}
        try:
            out["chunks"] = [
                json.loads(line)
                for line in zf.read("chunks.jsonl").decode("utf-8").splitlines()
                if line.strip()
            ]
        except Exception:
            out["chunks"] = []
        return out
# [03] END


# ======================= [04] PUBLIC API: rebuild_index — START =======================
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

# 이 파일 상단 [01]에서 이미 PERSIST_DIR, ALLOWED_EXTS 등이 정의되어 있다고 가정합니다.


def _iter_source_roots() -> Iterable[Path]:
    """
    인덱싱 소스 루트 후보를 반환합니다(존재하는 경로만).
    우선순위:
      1) 환경변수 MAIC_KNOWLEDGE_DIR
      2) 레포 상대 'knowledge/'
      3) 사용자 홈 '~/.maic/knowledge'
    """
    env = os.getenv("MAIC_KNOWLEDGE_DIR", "").strip()
    if env:
        p = Path(env).expanduser()
        if p.exists():
            yield p
    repo_k = Path.cwd() / "knowledge"
    if repo_k.exists():
        yield repo_k
    home_k = Path.home() / ".maic" / "knowledge"
    if home_k.exists():
        yield home_k


def _yield_files(root: Path) -> Iterable[Path]:
    """허용 확장자만 재귀 순회하며 파일 경로를 반환."""
    exts = {e.lower() for e in ALLOWED_EXTS}
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts:
            yield p


def _safe_read_text(p: Path, max_bytes: int = 1_000_000) -> str:
    """
    텍스트 파일을 최대 max_bytes까지 읽어 유니코드로 반환.
    바이너리/인코딩 오류는 무시하며, 줄바꿈은 유지합니다.
    """
    try:
        data = p.read_bytes()[:max_bytes]
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _write_jsonl_atomic(lines: Iterable[dict[str, Any]], out_file: Path) -> int:
    """
    JSONL을 원자적으로 기록합니다.
    - out_file.tmp에 먼저 쓰고, 완료 시 replace로 교체
    - 반환: 기록한 라인 수
    """
    tmp = out_file.with_suffix(".jsonl.tmp")
    if tmp.exists():
        try:
            tmp.unlink()
        except Exception:
            pass

    count = 0
    try:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w", encoding="utf-8") as w:
            for obj in lines:
                try:
                    w.write(json.dumps(obj, ensure_ascii=False))
                    w.write("\n")
                    count += 1
                except Exception:
                    continue
        if count > 0:
            if out_file.exists():
                out_file.unlink()
            tmp.replace(out_file)
        else:
            tmp.unlink(missing_ok=True)
    except Exception:
        # 실패 시 임시 파일 정리
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
    return count


def rebuild_index(output_dir: str | Path | None = None) -> dict[str, Any]:
    """
    로컬 인덱스를 재구축합니다.
    - knowledge/ 하위(또는 MAIC_KNOWLEDGE_DIR 등)에서 허용 확장자 파일을 수집
    - 각 파일을 '파일 단위 1청크'로 JSONL 라인 생성 (간단 부트스트랩 인덱싱)
    - 소스가 전혀 없으면 'bootstrap' 1라인을 생성해 READY를 보장

    반환(dict):
        {
          "persist_dir": "<경로>",
          "chunks": <작성 라인 수>,
          "sources": <사용된 소스 루트 수>
        }
    """
    dest = Path(output_dir).expanduser() if output_dir else PERSIST_DIR
    dest.mkdir(parents=True, exist_ok=True)
    out_jsonl = dest / "chunks.jsonl"

    roots = [p for p in _iter_source_roots()]
    lines: list[dict[str, Any]] = []

    # 1) 실제 소스 → 파일당 1라인 청크로 기록(간단 부트스트랩)
    for root in roots:
        for f in _yield_files(root):
            text = _safe_read_text(f)
            if not text.strip():
                continue
            # 필요한 최소 필드: id, text, source
            lines.append(
                {
                    "id": f"file::{f.name}",
                    "text": text,
                    "source": str(f),
                }
            )
            # 과도한 인덱싱 방지: 초기가동은 최대 200개만
            if len(lines) >= 200:
                break
        if len(lines) >= 200:
            break

    # 2) 소스가 전무하면 bootstrap 1라인 생성(READY 보장용)
    if not lines:
        lines = [
            {
                "id": "bootstrap::hello",
                "text": "MAIC index bootstrap line",
                "source": "bootstrap",
            }
        ]

    # 3) 원자적 쓰기
    wrote = _write_jsonl_atomic(lines, out_jsonl)

    # 4) READY 플래그 보정
    try:
        ready = dest / ".ready"
        if wrote > 0 and not ready.exists():
            ready.write_text("ok", encoding="utf-8")
    except Exception:
        pass

    return {
        "persist_dir": str(dest),
        "chunks": int(wrote),
        "sources": int(len(roots)),
    }
# ======================== [04] PUBLIC API: rebuild_index — END ========================

