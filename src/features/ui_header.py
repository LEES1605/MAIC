# ===== START OF [01] COMPACT HEADER (overlay badges + 3D title) =====
# file: src/features/ui_header.py

from __future__ import annotations
from typing import Literal, Optional
import streamlit as st

Status = Literal["ready", "warn", "error"]

def render_compact_header(
    title_text: str,
    anchor_left_text: str,
    middle_text: str,
    anchor_right_text: str,
    *,
    status: Status = "ready",
    settings_href: Optional[str] = None,
    subtitle_font_min_px: int = 22,
    subtitle_font_max_px: int = 36,
) -> None:
    """
    Render a compact header with:
      - 3D/embossed title
      - Subtitle where a status badge is overlaid above the *left anchor word*
      - Settings (gear) control overlaid above the *right anchor word*
    Notes
    -----
    - The overlaid elements are sized at 70% of the subtitle font size.
    - On very narrow viewports, they 'dock' slightly higher to avoid overlap.
    - settings_href: if provided (e.g., '?admin=1'), clicking the gear navigates there.
                     Use query params in app to toggle admin state on reload.
    """

    # Decide badge text/color from status
    if status == "ready":
        badge_text = "🟢 준비완료"
        badge_class = "badge-green"
    elif status == "warn":
        badge_text = "🟡 점검필요"
        badge_class = "badge-yellow"
    else:
        badge_text = "🔴 미연결"
        badge_class = "badge-red"

    # CSS + HTML — scoped to .lees-header to avoid side effects
    css = f"""
    <style>
      .lees-header {{
        margin: 0 0 0.25rem 0;  /* tighten vertical space */
      }}
      .lees-header .title-3d {{
        font-size: clamp(24px, 3.6vw, 42px);
        font-weight: 800;
        letter-spacing: 0.3px;
        line-height: 1.05;
        /* Subtle embossed effect */
        color: #222;
        text-shadow:
          0 1px 0 #fff,
          0 2px 0 #e9e9e9,
          0 3px 0 #dadada,
          0 4px 0 #cfcfcf,
          0 6px 12px rgba(0,0,0,0.18);
        margin: 0;  /* remove default h1 margins */
      }}

      .lees-header .subhead-wrap {{
        position: relative;
        margin-top: 0.25rem;   /* reduce space between title & subtitle */
      }}

      .lees-header .subhead {{
        position: relative;
        font-weight: 700;
        font-size: clamp({subtitle_font_min_px}px, 3.2vw, {subtitle_font_max_px}px);
        line-height: 1.25;
        color: #1f2937; /* neutral-800 */
        word-break: keep-all;
        white-space: normal;
      }}

      .lees-header .anchor {{
        position: relative; /* anchor for absolute children */
        display: inline-block;
      }}

      /* Overlaid controls — 70% of subtitle size */
      .lees-header .badge,
      .lees-header .gear {{
        position: absolute;
        left: 0;
        transform: translateY(-90%); /* place above the word */
        font-size: 0.7em;            /* 70% of subtitle font size */
        line-height: 1;
        padding: 0.15em 0.5em;
        border-radius: 999px;
        text-decoration: none;
        user-select: none;
        -webkit-tap-highlight-color: transparent;
        z-index: 2;
      }}

      .lees-header .badge {{ top: 0; }}
      .lees-header .gear  {{
        top: 0;
        left: 100%;
        margin-left: -1.2em;     /* pull it toward the word end */
        padding: 0.15em 0.35em;  /* a bit smaller pill */
        border-radius: 10px;
      }}

      /* Badge color variants */
      .lees-header .badge-green {{ background: #e7f7ef; color: #0a7f49; border: 1px solid #bfead7; }}
      .lees-header .badge-yellow{{ background: #fff7e6; color: #9a6a00; border: 1px solid #ffe2a8; }}
      .lees-header .badge-red   {{ background: #fde8e8; color: #a61b29; border: 1px solid #f5b5bb; }}

      /* Gear visual */
      .lees-header .gear {{
        background: #f3f4f6;
        color: #111827;
        border: 1px solid #e5e7eb;
      }}
      .lees-header .gear:hover {{ filter: brightness(0.96); }}

      /* Touch target */
      .lees-header .badge, .lees-header .gear {{ min-width: 40px; min-height: 28px; text-align: center; }}

      /* Narrow viewport fallback: lift controls slightly higher to avoid overlaps */
      @media (max-width: 380px) {{
        .lees-header .badge, .lees-header .gear {{
          transform: translateY(-110%);
        }}
      }}
    </style>
    """

    # Build HTML (no divider between title and subtitle)
    gear_html = (
        f'<a class="gear" href="{settings_href or "#"}" aria-label="관리자 설정">⚙</a>'
        if settings_href else
        '<span class="gear" aria-hidden="true">⚙</span>'
    )
    html = f"""
    <div class="lees-header" id="lees-header">
      <h1 class="title-3d">{title_text}</h1>
      <div class="subhead-wrap">
        <div class="subhead">
          <span class="anchor anchor-left">{anchor_left_text}
            <span class="badge {badge_class}">{badge_text}</span>
          </span>
          {middle_text}
          <span class="anchor anchor-right">{anchor_right_text}
            {gear_html}
          </span>
        </div>
      </div>
    </div>
    """

    st.markdown(css + html, unsafe_allow_html=True)
# ===== END OF [01] COMPACT HEADER (overlay badges + 3D title) =====
