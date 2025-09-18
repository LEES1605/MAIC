#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Index Status — Release/Local persist 상태 배지와 수동 복원
"""

from __future__ import annotations

import os
from pathlib import Path

from src.ui.widgets.index_status import render_index_status_panel


def main() -> None:
    persist_dir = Path(os.path.expanduser("~/.maic/persist"))

    tag_candidates = ["indices-latest", "index-latest", "latest"]
    asset_candidates = ["indices.zip", "persist.zip", "hq_index.zip", "prepared.zip"]

    render_index_status_panel(
        dest_dir=persist_dir,
        tag_candidates=tag_candidates,
        asset_candidates=asset_candidates,
    )


if __name__ == "__main__":
    main()
