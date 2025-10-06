# [03] START: src/admin/ui_prompt_page.py — 다시 불러오기(강제) + 상태 보이기
from __future__ import annotations
import requests

def on_click_reload() -> None:
    # 서버 API로 강제 리로드
    r = requests.post("/admin/prompts/reload", timeout=10)
    r.raise_for_status()
    j = r.json()
    status = j.get("status", {})
    # UI에 핵심 상태 노출: source/reason/ref/path/etag/sha
    # 예) "source=repo reason=200 sha=abc123 etag=W/"xyz""
    show_toast(f"Reload: source={status.get('source')} reason={status.get('reason')} sha={status.get('sha')}")

def show_status_panel():
    r = requests.get("/admin/prompts/status", timeout=10).json()
    status = r.get("status", {})
    render_kv_table(status)  # UI 프레임워크에 맞게
# [03] END: src/admin/ui_prompt_page.py
