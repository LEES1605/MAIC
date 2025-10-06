# [02] START: src/admin/api_prompts.py — 강제 리로드/상태 조회
from __future__ import annotations
from typing import Any, Dict
from http.server import BaseHTTPRequestHandler
import json

from src/runtime.prompts_loader import load_prompts, debug_status

def handle_reload() -> Dict[str, Any]:
    data = load_prompts(force=True)  # TTL/ETag 무시
    status = debug_status()
    return {"ok": True, "status": status, "preview": data.get("modes", {})}

def handle_status() -> Dict[str, Any]:
    return {"ok": True, "status": debug_status()}

# 프레임워크에 맞게 라우팅 연결 (FastAPI/Flask/Streamlit 등)
# 예시:
# POST /admin/prompts/reload -> handle_reload()
# GET  /admin/prompts/status -> handle_status()
# [02] END: src/admin/api_prompts.py
