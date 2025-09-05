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
# [03] END==================================================================
# ======================= [04] PUBLIC API: rebuild_index — START =======================
def rebuild_index(output_dir=None):
    """
    Google Drive 'prepared' 폴더만을 소스로 사용하여 로컬 인덱스를 재구축합니다.
    - 의미 단위 청킹(문단/문장) + 오버랩
    - 메타데이터(id, doc_id, chunk_id, title, source, ext, offsets, lang)
    - 중복 청크 제거(정규화 텍스트 해시)
    - 원자적 쓰기 후 검증 통과 시 .ready 생성
    - PDF: PyPDF2 있으면 본문 추출, 없으면 제목으로 최소 인덱싱

    요구 환경:
        GDRIVE_PREPARED_FOLDER_ID  (필수)  ← src.integrations.gdrive가 사용
    옵션:
        MAIC_INDEX_MODE=HQ  → 작은 청크/높은 오버랩/상한↑
    """
    # ---- 내부 헬퍼 및 설정 ------------------------------------------------------
    from pathlib import Path
    import os
    import re
    import json
    import hashlib
    import datetime
    import importlib

    MODE = (os.getenv("MAIC_INDEX_MODE") or "").upper()
    if MODE == "HQ":
        TARGET_CHARS = 900
        OVERLAP_CHARS = 250
        MAX_CHUNKS = 8000
    else:
        TARGET_CHARS = 1200
        OVERLAP_CHARS = 200
        MAX_CHUNKS = 800

    # --- persist dir 결정: config → 상수 → 폴백 -------------------------------
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

    # --- 허용 확장자: search.py와 일치(.md/.txt/.pdf/.csv/.json) --------------
    def _allowed_exts() -> set:
        try:
            exts = globals().get("ALLOWED_EXTS")
            if exts:
                return {str(e).lower() for e in exts}
        except Exception:
            pass
        return {".md", ".txt", ".json", ".csv", ".pdf"}  # ← PDF 포함
    exts_allowed = _allowed_exts()

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
        hangul = sum(0xAC00 <= ord(ch) <= 0xD7A3 for ch in s)
        return "ko" if hangul >= max(10, len(s) * 0.1) else "en"

    # ---------- PDF 텍스트 추출(가능하면) ----------
    def _read_text_pdf_bytes(blob: bytes) -> str:
        try:
            mod = importlib.import_module("PyPDF2")
            PdfReader = getattr(mod, "PdfReader", None)
            if PdfReader is None:
                return ""
            import io as _io
            reader = PdfReader(_io.BytesIO(blob))
            parts = []
            for page in getattr(reader, "pages", []):
                try:
                    t = page.extract_text() or ""
                except Exception:
                    t = ""
                if t:
                    parts.append(t)
            return "\n".join(parts).strip()
        except Exception:
            return ""

    # ---------- 청킹 ----------
    _re_paras = re.compile(r"\n{2,}")
    _re_sents = re.compile(r"(?<=[.!?。！？])\s+")

    def _split_paragraphs(s: str) -> list[str]:
        parts = [p.strip() for p in _re_paras.split(s) if p.strip()]
        return parts or [s.strip()]

    def _split_sentences(p: str) -> list[str]:
        parts = [x.strip() for x in _re_sents.split(p) if x.strip()]
        return parts or [p.strip()]

    def _chunk_text(text: str, target: int, overlap: int) -> list[tuple[str, int, int]]:
        chunks = []
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
                    if overlap > 0 and len(acc) > overlap:
                        tail = acc[-overlap:]
                        acc = tail
                        acc_start = (acc_start + len(acc)) - len(tail)
                    else:
                        acc = ""
                        acc_start = pos
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
            pos += 1
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

    # ---- 빌드: Drive prepared에서만 수집 --------------------------------------
    dest = _persist_dir()
    dest.mkdir(parents=True, exist_ok=True)
    out_jsonl = dest / "chunks.jsonl"

    # 1) 목록 가져오기
    gd = importlib.import_module("src.integrations.gdrive")
    list_files = getattr(gd, "list_prepared_files")
    download_bytes = getattr(gd, "download_bytes")
    files = list_files() if callable(list_files) else []
    # files: [{"id","name","modified_ts","size","mime"?}, ...]

    lines = []
    seen = set()

    for f in files:
        fid = str(f.get("id") or "")
        name = str(f.get("name") or fid)
        mts = int(f.get("modified_ts") or 0)
        size = int(f.get("size") or 0)
        mime = str(f.get("mime") or "")
        # 확장자 판정(이름 우선, 없으면 mime 힌트)
        ext = ""
        m = name.rsplit(".", 1)
        if len(m) == 2:
            ext = "." + m[1].lower()
        if not ext and mime:
            # 단순 맵핑
            if "pdf" in mime:
                ext = ".pdf"
            elif "markdown" in mime or "md" == mime:
                ext = ".md"
            elif "csv" in mime:
                ext = ".csv"
            elif "json" in mime:
                ext = ".json"
            elif "text" in mime:
                ext = ".txt"
        if ext and ext not in exts_allowed:
            continue  # 비허용 확장자 스킵

        # 2) 콘텐츠 읽기
        try:
            blob, eff_mime = download_bytes(fid, mime_hint=mime)
        except Exception:
            blob, eff_mime = (b"", mime)

        raw = ""
        if (ext == ".pdf") or (not ext and "pdf" in (eff_mime or "")):
            # PDF 처리
            raw = _read_text_pdf_bytes(blob) or ""
        else:
            try:
                raw = blob.decode("utf-8", errors="ignore")
            except Exception:
                raw = ""

        # 텍스트가 없으면 최소 인덱싱(파일명)으로 대체
        if not raw:
            raw = name

        text = _strip_noise(raw)
        title = _title_from_markdown(raw) or name
        lang = _detect_lang(text)
        doc_id = f"gdrive::{fid}"
        meta_time = ""
        try:
            meta_time = datetime.datetime.utcfromtimestamp(mts).isoformat() + "Z" if mts else ""
        except Exception:
            pass

        chunks = _chunk_text(text, TARGET_CHARS, OVERLAP_CHARS)
        if not chunks:
            continue

        for i, (ck, s0, s1) in enumerate(chunks):
            if len(lines) >= MAX_CHUNKS:
                break
            h = _hash_norm(ck)
            if h in seen:
                continue
            seen.add(h)
            lines.append(
                {
                    "id": len(lines),
                    "doc_id": doc_id,
                    "chunk_id": f"{doc_id}::{i}",
                    "title": title,
                    "source": f"gdrive://{fid}/{name}",
                    "ext": ext or "",
                    "offsets": [s0, s1],
                    "lang": lang,
                    "text": ck,
                    "mtime": meta_time,
                    "bytes": size,
                }
            )
        if len(lines) >= MAX_CHUNKS:
            break

    # ---- 결과 쓰기 & READY 플래그 ----------------------------------------------
    count = _write_jsonl_atomic(lines, out_jsonl)
    if count > 0:
        try:
            (dest / ".ready").write_text("ready", encoding="utf-8")
        except Exception:
            pass
        # manifest.json(문서 헤더만) 기록 — UI 가시화용
        headers = {}
        for obj in lines:
            d = obj.get("doc_id")
            if d and d not in headers:
                headers[d] = {"title": obj.get("title"), "source": obj.get("source")}
        try:
            (dest / "manifest.json").write_text(json.dumps({"docs": headers}, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    return {"chunks": count, "dest": str(dest), "roots": ["gdrive:prepared"]}
# ======================== [04] PUBLIC API: rebuild_index — END ========================

