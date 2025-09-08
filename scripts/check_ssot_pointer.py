# ============== [01] imports & usage — START ==============
"""
SSOT Pointer Checker

- WORKSPACE_INDEX.md 안의 'Source-of-Truth: github://<owner>/<repo>@<ref>/<path>'
  를 파싱/검증합니다.

검증 규칙:
  1) ref는 브랜치여야 함(예: main, release/*). 40자 SHA 금지.
  2) path는 지정한 SSOT 루트(기본: docs/_gpt/) 하위여야 함.
  3) GitHub API로 해당 파일/디렉터리 존재 확인(200 OK).

사용 예:
  python scripts/check_ssot_pointer.py \
    --file WORKSPACE_INDEX.md \
    --allow-refs main,release/* \
    --require-docs-root docs/_gpt/
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import json
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib import request, error, parse
# ============== [01] imports & usage — END =================


# ============== [02] core logic — START ====================
PTR_RE = re.compile(
    r"Source-of-Truth:\s*github://(?P<owner>[^/\s]+)/(?P<repo>[^@\s]+)@"
    r"(?P<ref>[^/\s]+?)/(?P<path>.+?)\s*$"
)

SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")


@dataclass
class Pointer:
    owner: str
    repo: str
    ref: str
    path: str


def _parse_pointer(md_text: str) -> Optional[Pointer]:
    for line in md_text.splitlines():
        m = PTR_RE.search(line.strip())
        if m:
            return Pointer(
                owner=m.group("owner"),
                repo=m.group("repo"),
                ref=m.group("ref"),
                path=m.group("path"),
            )
    return None


def _is_allowed_ref(ref: str, allowed: Iterable[str]) -> bool:
    if SHA_RE.match(ref):
        return False  # SHA 금지
    for pat in allowed:
        pat = pat.strip()
        if not pat:
            continue
        if pat.endswith("/*"):
            if ref.startswith(pat[:-1]):
                return True
        elif ref == pat:
            return True
    return False


def _github_contents_exists(tok: str, p: Pointer) -> bool:
    """
    ref/path 조합이 존재하는지 검사. 파일/디렉터리 모두 허용.
    GET /repos/{owner}/{repo}/contents/{path}?ref={ref}
    """
    base = "https://api.github.com"
    url = f"{base}/repos/{p.owner}/{p.repo}/contents/{parse.quote(p.path)}"
    if p.ref:
        url = f"{url}?ref={parse.quote(p.ref)}"
    req = request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    if tok:
        req.add_header("Authorization", f"token {tok}")
    try:
        with request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                # 존재. 파일이면 dict, 디렉터리면 list 형태가 온다.
                _ = resp.read()  # 소비만
                return True
            return False
    except error.HTTPError as e:
        # 404 등
        try:
            body = e.read().decode("utf-8", "ignore")
            print(f"[pointer] HTTP {e.code}: {body[:200]}", file=sys.stderr)
        except Exception:
            print(f"[pointer] HTTP {e.code}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[pointer] network error: {e}", file=sys.stderr)
        return False


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="WORKSPACE_INDEX.md")
    ap.add_argument("--allow-refs", default="main,release/*")
    ap.add_argument("--require-docs-root", default="docs/_gpt/")
    args = ap.parse_args(argv)

    path = args.file
    try:
        text = open(path, "r", encoding="utf-8").read()
    except Exception as e:
        print(f"[pointer] read error: {e}", file=sys.stderr)
        return 2

    ptr = _parse_pointer(text)
    if not ptr:
        print("[pointer] Source-of-Truth 라인을 찾지 못했습니다.", file=sys.stderr)
        return 2

    allow = [x.strip() for x in args.allow_refs.split(",") if x.strip()]
    if not _is_allowed_ref(ptr.ref, allow):
        print(
            f"[pointer] ref가 허용되지 않습니다: '{ptr.ref}' "
            f"(허용: {', '.join(allow)})",
            file=sys.stderr,
        )
        return 1

    req_root = args.require_docs_root.strip("/")
    if not ptr.path.strip("/").startswith(req_root):
        print(
            f"[pointer] path가 SSOT 루트('{req_root}') 하위가 아닙니다: '{ptr.path}'",
            file=sys.stderr,
        )
        return 1

    tok = os.getenv("GITHUB_TOKEN", "")
    if not _github_contents_exists(tok, ptr):
        print(
            "[pointer] GitHub API에서 path/ref를 찾지 못했습니다. "
            "포인터를 확인하세요.",
            file=sys.stderr,
        )
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "owner": ptr.owner,
                "repo": ptr.repo,
                "ref": ptr.ref,
                "path": ptr.path,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
# ============== [02] core logic — END ======================
