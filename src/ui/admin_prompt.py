# ===== [01] FILE: src/ui/admin_prompt.py — START =====
# -*- coding: utf-8 -*-
"""
관리자 프롬프트 편집기 — 페르소나 + 모드별 프롬프트(문법/문장/지문)
SSOT: docs/_gpt/ (Workspace Pointer)  /  최신 불러오기: Releases → SSOT 폴백
"""
from __future__ import annotations
import base64, importlib
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml
st: Any = importlib.import_module("streamlit")
req: Any = importlib.import_module("requests")

# 사이드바 유틸(있으면 사용)
try:
    _sider = importlib.import_module("src.ui.utils.sider")
    ensure_admin_sidebar = getattr(_sider, "ensure_admin_sidebar")
    render_minimal_admin_sidebar = getattr(_sider, "render_minimal_admin_sidebar")
    show_sidebar = getattr(_sider, "show_sidebar")
except Exception:
    def ensure_admin_sidebar() -> None: ...
    def render_minimal_admin_sidebar(*_: Any, **__: Any) -> None: ...
    def show_sidebar() -> None: ...

# 로더(릴리스→SSOT 폴백)
try:
    _loader = importlib.import_module("src.ui.assist.prompts_loader")
except Exception:
    _loader = importlib.import_module("prompts_loader")  # 응급 폴백
load_prompts_from_release = getattr(_loader, "load_prompts_from_release")
apply_prompts_to_session = getattr(_loader, "apply_prompts_to_session")

# (옵션) LLM 변환기
try:
    normalize_to_yaml = importlib.import_module("src.ui.assist.prompt_normalizer").normalize_to_yaml
except Exception:
    normalize_to_yaml = None  # type: ignore

# ===== schema/publish helpers =====
ELLIPSIS_UC = "\u2026"
def _sanitize_ellipsis(text: str) -> Tuple[str, int]:
    c = text.count(ELLIPSIS_UC)
    return text.replace(ELLIPSIS_UC, "..."), c

def _validate_yaml_text(yaml_text: str) -> Tuple[bool, list[str]]:
    try:
        data = yaml.safe_load(yaml_text)
        if not isinstance(data, dict):
            return False, ["<root>: mapping(object) required"]
    except Exception as exc:
        return False, [f"YAML parse error: {exc}"]
    try:
        js = importlib.import_module("jsonschema")
        validator = getattr(js, "Draft202012Validator", None)
        if validator is None:
            return False, ["jsonschema.Draft202012Validator not found"]
        root = Path(__file__).resolve().parents[1]
        sp = root / "schemas" / "prompts.schema.json"
        if sp.exists():
            import json
            schema = json.loads(sp.read_text(encoding="utf-8"))
            errs = sorted(validator(schema).iter_errors(data), key=lambda e: list(e.path))
        else:
            errs = []
    except Exception as exc:
        return False, [f"schema check failed: {exc}"]
    if errs:
        msgs = []
        for e in errs:
            loc = "/".join(str(p) for p in e.path) or "<root>"
            msgs.append(f"{loc}: {e.message}")
        return False, msgs
    return True, []

def _gh_dispatch_workflow(*, owner: str, repo: str, workflow: str, ref: str,
                          token: str | None, yaml_text: str,
                          prerelease: bool = False, promote_latest: bool = True) -> None:
    s, n = _sanitize_ellipsis(yaml_text)
    if n: st.info(f"U+2026 {n}개를 '...'로 치환했습니다.")
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
    payload = {"ref": ref, "inputs": {
        "yaml_b64": base64.b64encode(s.encode("utf-8")).decode("ascii"),
        "prerelease": "true" if prerelease else "false",
        "promote_latest": "true" if promote_latest else "false",
    }}
    headers = {"Accept": "application/vnd.github+json"}
    if token: headers["Authorization"] = f"Bearer {token}"
    r = req.post(url, headers=headers, json=payload, timeout=20)
    if r.status_code not in (201, 204):
        raise RuntimeError(f"workflow_dispatch failed: {r.status_code} — {r.text}")

def _init_admin_page() -> None:
    st.set_page_config(page_title="Prompts Admin", page_icon="🛠️", layout="wide")
    ensure_admin_sidebar()
    try: show_sidebar()
    except Exception: pass
    render_minimal_admin_sidebar(back_page="app.py")

def main() -> None:
    _init_admin_page()

    # ---- 상태 점검 요약 ------------------------------------------------------
    with st.container(border=True):
        st.subheader("🔍 상태 점검", divider="gray")
        repo_full = st.secrets.get("GITHUB_REPO", "")
        token = st.secrets.get("GITHUB_TOKEN")
        ref = st.secrets.get("GITHUB_BRANCH", "main")
        workflow = st.secrets.get("GITHUB_WORKFLOW", "publish-prompts.yml")

        owner = repo = ""
        repo_config_error = False
        if repo_full and "/" in repo_full:
            owner, repo = repo_full.split("/", 1)
            if not owner or not repo:
                repo_config_error = True; st.error("GITHUB_REPO 형식이 잘못되었습니다. 예: OWNER/REPO")
        elif repo_full:
            repo_config_error = True; st.error("GITHUB_REPO 형식이 잘못되었습니다. 예: OWNER/REPO")
        else:
            repo_config_error = True; st.info("GITHUB_REPO 시크릿이 비어 있어 출판 기능이 비활성화됩니다.")

        # 릴리스 prompts.yaml 존재 점검
        try:
            headers = {"Accept": "application/vnd.github+json"}
            if token: headers["Authorization"] = f"Bearer {token}"
            url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/prompts-latest"
            r = req.get(url, headers=headers, timeout=10)
            if r.status_code == 404:
                r = req.get(f"https://api.github.com/repos/{owner}/{repo}/releases/latest", headers=headers, timeout=10)
            rel = r.json() if r.ok else {}
            assets = rel.get("assets") or []
            has_prompts = any((a.get("name") or "").lower() in ("prompts.yaml","prompts.yml") for a in assets)
            if has_prompts:
                st.success(f"릴리스 OK — prompts.yaml 자산 확인 (assets={len(assets)})")
            else:
                st.warning(f"릴리스에 prompts.yaml 자산이 보이지 않습니다. (assets={len(assets)})")
        except Exception as e:
            st.warning(f"릴리스 확인 실패: {e}")

    # ---- 편집 UI ------------------------------------------------------------
    st.markdown("### ① 페르소나(공통)")
    persona = st.text_area("모든 모드에 공통 적용", key="persona_text", height=160)

    st.markdown("### ② 모드별 프롬프트(지시/규칙)")
    c1, c2, c3 = st.columns(3)
    with c1:   st.text_area("문법(Grammar) 프롬프트", key="grammar_prompt", height=220)
    with c2:   st.text_area("문장(Sentence) 프롬프트", key="sentence_prompt", height=220)
    with c3:   st.text_area("지문(Passage) 프롬프트", key="passage_prompt", height=220)

    # ---- 액션 ---------------------------------------------------------------
    st.markdown("### ③ 액션")
    b1, b2, b3, b4 = st.columns(4)

    with b1:
        if st.button("📥 최신 프롬프트 불러오기(릴리스 우선)", use_container_width=True):
            try:
                data = load_prompts_from_release()
                apply_prompts_to_session(data)
                st.success("최신 프롬프트를 세션에 주입했습니다.")
            except Exception as e:
                st.exception(e)

    with b2:
        if st.button("🧠 전체 정리(LLM)", use_container_width=True):
            if callable(normalize_to_yaml):
                y = normalize_to_yaml(
                    grammar_text=st.session_state.get("grammar_prompt","") or "",
                    sentence_text=st.session_state.get("sentence_prompt","") or "",
                    passage_text=st.session_state.get("passage_prompt","") or "",
                    openai_key=st.secrets.get("OPENAI_API_KEY"),
                    openai_model=st.secrets.get("OPENAI_MODEL", "gpt-4o-mini"),
                )
                st.session_state["_merged_yaml"] = y
            else:
                st.info("normalize_to_yaml 모듈이 없어 수동 병합으로 진행하세요.")

    with b3:
        if st.button("🧾 YAML 병합(로컬 필드→YAML)", use_container_width=True):
            doc = {
                "version": "auto",
                "persona": st.session_state.get("persona_text","") or "",
                "modes": [
                    {"key": "grammar",  "prompt": st.session_state.get("grammar_prompt","") or ""},
                    {"key": "sentence", "prompt": st.session_state.get("sentence_prompt","") or ""},
                    {"key": "passage",  "prompt": st.session_state.get("passage_prompt","") or ""},
                ],
            }
            st.session_state["_merged_yaml"] = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)

    with b4:
        publish_disabled = repo_config_error or not owner or not repo
        if st.button("🚀 출판(Publish)", type="primary", disabled=publish_disabled, use_container_width=True):
            y = st.session_state.get("_merged_yaml", "")
            ok, msgs = _validate_yaml_text(y)
            if not ok:
                st.error("스키마 검증 실패 — 먼저 오류를 해결하세요.")
                if msgs: st.write("\n".join(f"- {m}" for m in msgs))
            else:
                try:
                    _gh_dispatch_workflow(owner=owner, repo=repo, workflow=st.secrets.get("GITHUB_WORKFLOW","publish-prompts.yml"),
                                          ref=st.secrets.get("GITHUB_BRANCH","main"), token=st.secrets.get("GITHUB_TOKEN"),
                                          yaml_text=y)
                    st.success("출판 요청 전송 완료 — Actions에서 처리 중입니다.")
                    st.markdown(f"[열기: Actions › publish-prompts.yml](https://github.com/{owner}/{repo}/actions/workflows/publish-prompts.yml)")
                except Exception as exc:
                    st.exception(exc)

    if st.session_state.get("_merged_yaml"):
        st.markdown("### YAML 미리보기")
        st.code(st.session_state["_merged_yaml"], language="yaml")


if __name__ == "__main__":
    main()
# ===== [01] FILE: src/ui/admin_prompt.py — END =====
