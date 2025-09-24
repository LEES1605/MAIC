# -*- coding: utf-8 -*-
"""Admin UI — Prompts: 3 modes with single free-text input per mode."""
from __future__ import annotations

import base64
import importlib
from pathlib import Path
from typing import Any, Callable, Dict, Tuple

import yaml
from src.ui.assist.prompt_normalizer import normalize_to_yaml  # ruff: E402 ok

# dynamic imports
st: Any = importlib.import_module("streamlit")
req: Any = importlib.import_module("requests")

# sider helpers
ensure_admin_sidebar: Callable[[], None]
render_minimal_admin_sidebar: Callable[..., None]
try:
    _sider = importlib.import_module("src.ui.utils.sider")
    ensure_admin_sidebar = getattr(_sider, "ensure_admin_sidebar")
    render_minimal_admin_sidebar = getattr(_sider, "render_minimal_admin_sidebar")
except Exception:
    def ensure_admin_sidebar() -> None:
        return
    def render_minimal_admin_sidebar(*_: Any, **__: Any) -> None:
        return

# ===== [02] yaml/schema helpers — START =====
ELLIPSIS_UC = "\u2026"


def _sanitize_ellipsis(text: str) -> Tuple[str, int]:
    c = text.count(ELLIPSIS_UC)
    return text.replace(ELLIPSIS_UC, "..."), c


def _load_schema() -> Dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    sp = root / "schemas" / "prompts.schema.json"
    if not sp.exists():
        raise FileNotFoundError(f"Schema not found: {sp}")
    import json
    return json.loads(sp.read_text(encoding="utf-8"))


def _validate_yaml_text(yaml_text: str) -> Tuple[bool, list[str]]:
    try:
        data = yaml.safe_load(yaml_text)
        if not isinstance(data, dict):
            return False, ["<root>: mapping(object) required"]
    except Exception as exc:  # noqa: BLE001
        return False, [f"YAML parse error: {exc}"]

    try:
        js = importlib.import_module("jsonschema")
        validator = getattr(js, "Draft202012Validator", None)
        if validator is None:
            return False, ["jsonschema.Draft202012Validator not found"]
        schema = _load_schema()
        errs = sorted(validator(schema).iter_errors(data), key=lambda e: list(e.path))
    except Exception as exc:  # noqa: BLE001
        return False, [f"schema check failed: {exc}"]

    if errs:
        msgs = []
        for e in errs:
            loc = "/".join(str(p) for p in e.path) or "<root>"
            msgs.append(f"{loc}: {e.message}")
        return False, msgs
    return True, []
# ===== [02] yaml/schema helpers — END =====

# ===== [03] publish helpers — START =====
def _gh_dispatch_workflow(
    *,
    owner: str,
    repo: str,
    workflow: str,
    ref: str,
    token: str | None,
    yaml_text: str,
    prerelease: bool = False,
    promote_latest: bool = True,
) -> None:
    s, n = _sanitize_ellipsis(yaml_text)
    if n:
        st.info(f"U+2026 {n}개를 '...'로 치환했습니다.")
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
    payload = {"ref": ref, "inputs": {
        "yaml_b64": base64.b64encode(s.encode("utf-8")).decode("ascii"),
        "prerelease": "true" if prerelease else "false",
        "promote_latest": "true" if promote_latest else "false",
    }}
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = req.post(url, headers=headers, json=payload, timeout=20)
    if r.status_code not in (201, 204):
        raise RuntimeError(f"workflow_dispatch failed: {r.status_code} — {r.text}")
# ===== [03] publish helpers — END =====

# ===== [04] page init (no password) — START =====
def _init_admin_page() -> None:
    # 페이지 구성
    st.set_page_config(page_title="Prompts Admin", page_icon="🛠️", layout="wide")
    # 관리자: 바로 사이드바 펼침 + 최소 메뉴 렌더
    ensure_admin_sidebar()          # 관리자는 펼침, 학생이면 숨김(프로젝트 정책)
    from src.ui.utils.sider import show_sidebar
    try:
        show_sidebar()  # 이 페이지에선 무조건 보이도록 강제
    except Exception:
        pass
    render_minimal_admin_sidebar(back_page="app.py")  # 기본 네비 전부 숨김 + 2버튼만
# ===== [04] page init (no password) — END =====

# ===== [05] main — START =====
def main() -> None:
    _init_admin_page()

    repo_full = st.secrets.get("GITHUB_REPO", "")
    owner: str = ""
    repo: str = ""
    repo_config_error = False

    if repo_full and "/" in repo_full:
        owner, repo = repo_full.split("/", 1)
        if not owner or not repo:
            repo_config_error = True
            st.error("GITHUB_REPO 형식이 잘못되었습니다. 예: OWNER/REPO")
    elif repo_full:
        repo_config_error = True
        st.error("GITHUB_REPO 형식이 잘못되었습니다. 예: OWNER/REPO")
    else:
        repo_config_error = True
        st.info(
            "GITHUB_REPO 시크릿이 비어 있어 출판 기능이 비활성화됩니다."
            " 편집과 저장은 계속 사용할 수 있습니다."
        )

    token = st.secrets.get("GITHUB_TOKEN")
    ref = st.secrets.get("GITHUB_BRANCH", "main")
    workflow = st.secrets.get("GITHUB_WORKFLOW", "publish-prompts.yml")

    # 탭: 문법/문장/지문 — 각 탭은 자연어 1개 입력만
    tab_g, tab_s, tab_p = st.tabs(["문법", "문장", "지문"])
    with tab_g:
        g_text = st.text_area("문법(자연어 한 덩어리)", height=160, key="g_text")
    with tab_s:
        s_text = st.text_area("문장(자연어 한 덩어리)", height=160, key="s_text")
    with tab_p:
        p_text = st.text_area("지문(자연어 한 덩어리)", height=160, key="p_text")

    # 하단: 일원화 버튼(LLM→병합→검증→출판)
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🧠 전체 정리(LLM)", use_container_width=True, key="llm_all"):
            y = normalize_to_yaml(
                grammar_text=g_text or "",
                sentence_text=s_text or "",
                passage_text=p_text or "",
                openai_key=st.secrets.get("OPENAI_API_KEY"),
                openai_model=st.secrets.get("OPENAI_MODEL", "gpt-4o-mini"),
            )
            st.session_state["_merged_yaml"] = y
    with c2:
        if st.button("🔎 스키마 검증", use_container_width=True, key="validate_all"):
            y = st.session_state.get("_merged_yaml", "")
            ok, msgs = _validate_yaml_text(y)
            st.success("검증 통과") if ok else st.error("\n".join(f"- {m}" for m in msgs))
    with c3:
        publish_disabled = repo_config_error or not owner or not repo
        publish_clicked = st.button(
            "🚀 출판(Publish)",
            type="primary",
            use_container_width=True,
            key="publish_all",
            disabled=publish_disabled,
            help="GITHUB_REPO 시크릿이 설정되어 있어야 출판할 수 있습니다."
            if publish_disabled
            else None,
        )

        if publish_clicked:
            y = st.session_state.get("_merged_yaml", "")
            ok, msgs = _validate_yaml_text(y)
            if not ok:
                st.error("스키마 검증 실패 — 먼저 오류를 해결하세요.")
                if msgs:
                    st.write("\n".join(f"- {m}" for m in msgs))
            else:
                try:
                    _gh_dispatch_workflow(
                        owner=owner,
                        repo=repo,
                        workflow=workflow,
                        ref=ref,
                        token=token,
                        yaml_text=y,
                    )
                    st.success("출판 요청 전송 완료 — Actions에서 처리 중입니다.")
                    st.markdown(
                        f"[열기: Actions › {workflow}]"
                        f"(https://github.com/{owner}/{repo}/actions/workflows/{workflow})"
                    )
                except Exception as exc:  # noqa: BLE001
                    st.exception(exc)

    if st.session_state.get("_merged_yaml"):
        st.code(st.session_state["_merged_yaml"], language="yaml")
# ===== [05] main — END =====
