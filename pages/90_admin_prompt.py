#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Streamlit multipage wiring for Admin Prompts UI.
This page delegates to `src.ui.admin_prompts.main()`.
"""

from __future__ import annotations

from src.ui.admin_prompts import main as admin_main


def main() -> None:
    admin_main()


if __name__ == "__main__":
    main()
