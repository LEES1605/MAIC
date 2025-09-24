# ===== [01] FILE: pages/90_admin_prompt.py — START =====
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Streamlit multipage wiring for Admin Prompts UI (Persona + Prompt, 2-field).
Delegates to root 'admin_prompt.main()' and applies minimal admin sidebar chrome.
"""

from __future__ import annotations

# 관리자 사이드바(최소 크롬) 적용
from src.ui.utils.sider import apply_admin_chrome

# 위임 대상: 루트 레벨의 2필드 UI (admin_prompt.py)
from admin_prompt import main as _delegate_main


def main() -> None:
    # 최소 사이드바 크롬을 먼저 적용(중복 set_page_config는 내부에서 안전 처리)
    try:
        apply_admin_chrome(back_page="app.py", icon_only=True)
    except Exception:
        # 사이드바 유틸이 비치지 않은 환경에서도 UI는 계속 진행
        pass

    # 2필드 UI 실행
    _delegate_main()


if __name__ == "__main__":
    main()
# ===== [01] FILE: pages/90_admin_prompt.py — END =====
