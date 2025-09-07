"""
src/core/index_probe.py
- 인덱스 준비상태 경량 진단(파일 존재/크기/샘플 파싱)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import json


def probe_index_health(persist: Path) -> Dict[str, Any]:
    """
    반환 예:
    {
      'persist': '/home/.../.maic/persist',
      'chunks_exists': True,
      'chunks_size': 1234,
      'ready_exists': True,
      'mtime': 1712345678,
      'json_sample': 200, 'json_malformed': 0, 'json_ok': True,
      'ok': True
    }
    """
    res: Dict[str, Any] = {"persist": str(persist)}
    try:
        cj = persist / "chunks.jsonl"
        res["chunks_exists"] = cj.exists()
        res["chunks_size"] = cj.stat().st_size if cj.exists() else 0
        res["ready_exists"] = (persist / ".ready").exists()
        res["mtime"] = int(cj.stat().st_mtime) if cj.exists() else 0

        malformed = 0
        sample = 0
        if cj.exists():
            with cj.open("r", encoding="utf-8") as rf:
                for i, line in enumerate(rf):
                    if i >= 200:
                        break
                    s = line.strip()
                    if not s:
                        continue
                    sample += 1
                    try:
                        json.loads(s)
                    except Exception:
                        malformed += 1

        res["json_sample"] = sample
        res["json_malformed"] = malformed
        json_ok = (malformed == 0) or (sample > 0 and malformed / sample <= 0.02)
        res["json_ok"] = json_ok

        res["ok"] = (
            res["chunks_exists"]
            and res["chunks_size"] > 0
            and res["ready_exists"]
            and json_ok
        )
    except Exception:
        res["ok"] = False
    return res
