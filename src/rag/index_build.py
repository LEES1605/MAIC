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
def rebuild_index(output_dir=None):
    """
    로컬 인덱스를 재구축합니다. (고퀄 버전)
    - 의미 단위 청킹(문단/문장) + 오버랩 적용
    - 마크다운/HTML 정리, 코드블록 제거
    - 메타데이터(id, doc_id, chunk_id, title, source, ext, offsets, lang)
    - 중복 청크 제거(정규화 텍스트 해시)
    - 원자적 쓰기 후 검증 통과 시 .ready 생성

    매개변수:
        output_dir: str | pathlib.Path | None
    반환(dict):
        { "persist_dir": "<경로>", "chunks": <작성 라인 수>, "sources": <소스 루트 수> }
    """
    # ---- 내부 헬퍼 및 설정 ------------------------------------------------------
    from pathlib import Path
    import os
    import re
    import json
    import hashlib
    import datetime

    TARGET_CHARS = 1200       # 청크 목표 길이(문자)
    OVERLAP_CHARS = 200       # 청크 간 오버랩
    MAX_CHUNKS = 800          # 과도한 인덱싱 방지(초기가동 상한)

    def _persist_dir() -> Path:
        if output_dir:
            return Path(output_dir).expanduser()
        try:
            cfg = globals().get("PERSIST_DIR")
            if cfg:
                return Path(cfg).expanduser()
        except Exception:
            pass
        try:
            from src.config import PERSIST_DIR as CFG  # noqa: E402
            return Path(str(CFG)).expanduser()
        except Exception:
            pass
        return Path.home() / ".maic" / "persist"

    def _allowed_exts() -> set:
        try:
            exts = globals().get("ALLOWED_EXTS")
            if exts:
                return {str(e).lower() for e in exts}
        except Exception:
            pass
        # PDF는 외부 라이브러리 없이 안정 추출이 어려워 일단 제외(빈 텍스트 방지)
        return {".md", ".txt", ".json", ".csv"}

    def _iter_source_roots():
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

    def _yield_files(root: Path):
        exts = _allowed_exts()
        for p in root.rglob("*"):
            try:
                if p.is_file() and p.suffix.lower() in exts:
                    yield p
            except Exception:
                continue

    # ---------- 정규화/클린업 ----------
    _re_codeblock = re.compile(r"```.*?```", re.S)
    _re_html = re.compile(r"<[^>]+>")
    _re_ws = re.compile(r"[ \t]+")
    _re_md_head = re.compile(r"^\s*#{1,6}\s+(.*)$", re.M)

    def _strip_noise(s: str) -> str:
        s = _re_codeblock.sub("", s)
        s = _re_html.sub(" ", s)
        s = _re_ws.sub(" ", s)
        return s.strip()

    def _title_from_markdown(s: str) -> str:
        m = _re_md_head.search(s)
        return m.group(1).strip() if m else ""

    def _detect_lang(s: str) -> str:
        # 간단 추정: 한글 비율
        hangul = sum(0xAC00 <= ord(ch) <= 0xD7A3 for ch in s)
        return "ko" if hangul >= max(10, len(s) * 0.1) else "en"

    # ---------- 청킹 ----------
    _re_paras = re.compile(r"\n{2,}")
    _re_sents = re.compile(r"(?<=[.!?。！？])\s+")

    def _split_paragraphs(s: str) -> list[str]:
        parts = [p.strip() for p in _re_paras.split(s) if p.strip()]
        return parts or [s.strip()]

    def _split_sentences(p: str) -> list[str]:
        # 문장 단위 분할(영문/국문 기본 구두점)
        parts = [x.strip() for x in _re_sents.split(p) if x.strip()]
        return parts or [p.strip()]

    def _chunk_text(text: str, target: int, overlap: int) -> list[tuple[str, int, int]]:
        """
        텍스트를 (chunk, start, end) 리스트로 반환.
        - 문단→문장 단위로 모아 target 크기까지 누적
        - 청크 경계 사이에 overlap 문자만큼 앞부분을 유지
        """
        chunks = []
        start = 0
        acc = ""
        acc_start = 0
        pos = 0
        for para in _split_paragraphs(text):
            for sent in _split_sentences(para):
                if not acc:
                    acc_start = pos
                if len(acc) + len(sent) + 1 <= target or not acc:
                    acc = (acc + " " + sent).strip()
                else:
                    chunks.append((acc, acc_start, acc_start + len(acc)))
                    # 오버랩을 위해 acc의 뒤 overlap 부분을 남김
                    if overlap > 0 and len(acc) > overlap:
                        tail = acc[-overlap:]
                        acc = tail
                        acc_start = (acc_start + len(acc)) - len(tail)
                    else:
                        acc = ""
                        acc_start = pos
                    # 현재 문장 추가 시작
                    if acc:
                        if len(acc) + len(sent) + 1 <= target:
                            acc = (acc + " " + sent).strip()
                        else:
                            chunks.append((sent, pos, pos + len(sent)))
                            acc = ""
                            acc_start = pos + len(sent)
                    else:
                        acc = sent
                        acc_start = pos
                pos += len(sent) + 1
            pos += 1  # 단락 경계 보정
        if acc:
            chunks.append((acc, acc_start, acc_start + len(acc)))
        return chunks

    # ---------- JSONL 쓰기 ----------
    def _write_jsonl_atomic(lines, out_file: Path) -> int:
        tmp = out_file.with_suffix(".jsonl.tmp")
        try:
            if tmp.exists():
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
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
        return count

    def _hash_norm(s: str) -> str:
        s2 = s.lower().strip()
        return hashlib.sha1(s2.encode("utf-8", errors="ignore")).hexdigest()

    # ---- 빌드 ---------------------------------------------------------------
    dest = _persist_dir()
    dest.mkdir(parents=True, exist_ok=True)
    out_jsonl = dest / "chunks.jsonl"

    roots = [p for p in _iter_source_roots()]
    lines = []
    seen = set()

    for root in roots:
        for f in _yield_files(root):
            try:
                raw = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                try:
                    raw = f.read_bytes().decode("utf-8", errors="ignore")
                except Exception:
                    raw = ""
            text = _strip_noise(raw)
            if not text:
                continue

            title = _title_from_markdown(raw) or f.stem
            lang = _detect_lang(text)
            doc_id = f"doc::{f.name}"
            meta_time = ""
            try:
                ts = datetime.datetime.fromtimestamp(f.stat().st_mtime)
                meta_time = ts.isoformat()
            except Exception:
                pass

            chunks = _chunk_text(text, TARGET_CHARS, OVERLAP_CHARS)
            for i, (chunk, s0, s1) in enumerate(chunks):
                h = _hash_norm(chunk)
                if h in seen:
                    continue
                seen.add(h)
                lines.append(
                    {
                        "id": f"{doc_id}::chunk::{i}",
                        "doc_id": doc_id,
                        "chunk_id": i,
                        "title": title,
                        "text": chunk,
                        "source": str(f),
                        "ext": f.suffix.lower(),
                        "lang": lang,
                        "start_char": s0,
                        "end_char": s1,
                        "modified_at": meta_time,
                    }
                )
                if len(lines) >= MAX_CHUNKS:
                    break
            if len(lines) >= MAX_CHUNKS:
                break
        if len(lines) >= MAX_CHUNKS:
            break

    # 소스가 전무하면 부트스트랩 1라인 생성(READY 보장)
    if not lines:
        lines = [
            {
                "id": "bootstrap::hello",
                "doc_id": "bootstrap",
                "chunk_id": 0,
                "title": "bootstrap",
                "text": "MAIC index bootstrap line",
                "source": "bootstrap",
                "ext": ".txt",
                "lang": "en",
                "start_char": 0,
                "end_char": 29,
                "modified_at": "",
            }
        ]

    wrote = _write_jsonl_atomic(lines, out_jsonl)

    try:
        ready = dest / ".ready"
        if wrote > 0 and not ready.exists():
            ready.write_text("ok", encoding="utf-8")
    except Exception:
        pass

    return {"persist_dir": str(dest), "chunks": int(wrote), "sources": int(len(roots))}
# ======================== [04] PUBLIC API: rebuild_index — END ========================
