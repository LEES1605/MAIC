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


# [04] 빌드 엔트리포인트(데모 스텁)  # [04] START
def build_index_with_checkpoint(prepared_dir: Path) -> Dict[str, Any]:
    """
    prepared_dir에서 인덱스 데이터를 생성하고, 로컬에 기록한 뒤 ZIP 스냅샷을 반환.
    (데모/스텁: 실제 인덱싱 파이프라인은 별도 모듈에서 동작)
    """
    # 간단 매니페스트 예시
    files = []
    for p in Path(prepared_dir).rglob("*"):
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTS:
            st = p.stat()
            files.append({"path": str(p), "bytes": st.st_size, "mtime": int(st.st_mtime)})

    data = {"manifest": {"files": files}, "chunks": []}
    _write_json(MANIFEST_PATH, data.get("manifest", {}))
    return data
# [04] END
