# ===== [01] FILE: src/ui/admin_prompt.py — START =====
# -*- coding: utf-8 -*-
"""
관리자 프롬프트 편집기 — 페르소나 + 모드별 프롬프트(문법/문장/지문)
- 요구사항:
  (1) 릴리스에서 최신 prompts.yaml을 불러오면 3개 모드 칸까지 정확히 채워질 것
  (2) 편집 → YAML 미리보기 → 검증 → 출판(워크플로 dispatch)
  (3) GITHUB_REPO 시크릿이 비어도 '편집'은 가능하고, 출판만 비활성화

SSOT/정책:
- 문서 단일 진실 소스는 docs/_gpt/ (Workspace Pointer 참조). :contentReference[oaicite:2]{index=2}
- 헤더/상태 표시는 MASTERPLAN vNext 합의안(H1)에 따름. :contentReference[oaicite:3]{index=3}
"""
from __future__ import annotations

import base64
import importlib
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml

# Streamlit & Requests
st: Any = importlib.import_module("streamlit")
req: Any = importlib.import_module("requests")

# Admin sider(있으면 사용)
try:
    _sider = importlib.import_module("src.ui.utils.sider")
    ensure_admin_sidebar = getattr(_sider, "ensure_admin_sidebar")
    render_minimal_admin_sidebar = getattr(_sider, "render_minimal_admin_sidebar")
    show_sidebar = getattr(_sider, "show_sidebar")
except Exception:
    def ensure_admin_sidebar() -> None: ...
    def render_minimal_admin_sidebar(*_: Any, **__: Any) -> None: ...
    def show_sidebar() -> None: ...

# 관용 로더(릴리스 → 페르소나+3모드)
try:
    _loader = importlib.import_module("src.ui.assist.prompts_loader")
    load_prompts_from_release = getattr(_loader, "load_prompts_from_release")
    apply_prompts_to_session = getattr(_loader, "apply_prompts_to_session")
except Exception:
    load_prompts_from_release = apply_prompts_to_session = None  # type: ignore

# (옵션) LLM 변환기
try:
    normalize_to_yaml = importlib.import_module("src.ui.assist.prompt_normalizer").normalize_to_yaml
except Exception:
    normalize_to_yaml = None  # type: ignore


# ===== [02] schema helpers — START =====
ELLIPSIS_UC = "\u2026"

def _sanitize_ellipsis(text: str) -> Tuple[str, int]:
    c = text.count(ELLIPSIS_UC)
    return text.replace(ELLIPSIS_UC, "..."), c


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
        # schemas/prompts.schema.json 가정(없으면 관용 통과)
        root = Path(__file__).resolve().parents[1]
        sp = root / "schemas" / "prompts.schema.json"
        if sp.exists():
            import json
            schema = json.loads(sp.read_text(encoding="utf-8"))
            errs = sorted(validator(schema).iter_errors(data), key=lambda e: list(e.path))
        else:
            errs = []
    except Exception as exc:  # noqa: BLE001
        return False, [f"schema check failed: {exc}"]

    if errs:
        msgs = []
        for e in errs:
            loc = "/".join(str(p) for p in e.path) or "<root>"
            msgs.append(f"{loc}: {e.message}")
        return False, msgs
    return True, []
# ===== [02] schema helpers — END =====


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


# ===== [04] page init — START =====
def _init_admin_page() -> None:
    st.set_page_config(page_title="Prompts Admin", page_icon="🛠️", layout="wide")
    ensure_admin_sidebar()
    try:
        show_sidebar()  # 이 페이지에선 사이드바 강제 노출
    except Exception:
        pass
    render_minimal_admin_sidebar(back_page="app.py")
# ===== [04] page init — END =====


# ===== [05] main — START =====
def main() -> None:
    _init_admin_page()

    # --- 상태점검 박스 -------------------------------------------------------------
    with st.container(border=True):
        st.subheader("🔍 상태 점검", divider="gray")
        app_url = st.query_params.get("_", None)  # dummy to keep example; 실제 환경에선 base_url 사용
        st.text_input("앱 주소(.streamlit.app)", value=st.runtime.scriptrunner.script_run_context.get_script_run_ctx().session_id if hasattr(st, "runtime") else "", key="app_url", disabled=True)

        repo_full = st.secrets.get("GITHUB_REPO", "")
        token = st.secrets.get("GITHUB_TOKEN")
        ref = st.secrets.get("GITHUB_BRANCH", "main")
        workflow = st.secrets.get("GITHUB_WORKFLOW", "publish-prompts.yml")

        owner = repo = ""
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
            st.info("GITHUB_REPO 시크릿이 비어 있어 출판 기능이 비활성화됩니다. 편집과 저장은 계속 사용할 수 있습니다.")

        # 릴리스 체크(최신 + prompts.yaml 존재)
        with st.status("릴리스 점검 중...", expanded=False) as stx:
            rel_ok = False
            asset_count = 0
            try:
                url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/prompts-latest"
                headers = {"Accept": "application/vnd.github+json"}
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                r = req.get(url, headers=headers, timeout=10)
                if r.status_code == 404:  # fallback
                    r = req.get(f"https://api.github.com/repos/{owner}/{repo}/releases/latest", headers=headers, timeout=10)
                r.raise_for_status()
                rel = r.json()
                assets = rel.get("assets") or []
                asset_count = len(assets)
                rel_ok = any((a.get("name") or "").lower() in ("prompts.yaml", "prompts.yml") for a in assets)
            except Exception as e:
                stx.update(label=f"릴리스 조회 실패: {e}", state="error")
            else:
                if rel_ok:
                    stx.update(label=f"릴리스 OK — assets={asset_count}, prompts.yaml 존재", state="complete")
                else:
                    stx.update(label=f"릴리스 경고 — prompts.yaml 자산이 보이지 않습니다(assets={asset_count})", state="error")

    # --- 편집 UI ------------------------------------------------------------------
    st.markdown("### ① 페르소나(공통)")
    persona = st.text_area("모든 모드에 공통 적용", key="persona_text", height=160, placeholder="페르소나 텍스트...", help="모든 모드 공통 지침")

    st.markdown("### ② 모드별 프롬프트(지시/규칙)")
    c1, c2, c3 = st.columns(3)
    with c1:
        grammar_prompt = st.text_area("문법(Grammar) 프롬프트", key="grammar_prompt", height=200, placeholder="문법 모드 지시/규칙...")
    with c2:
        sentence_prompt = st.text_area("문장(Sentence) 프롬프트", key="sentence_prompt", height=200, placeholder="문장 모드 지시/규칙...")
    with c3:
        passage_prompt = st.text_area("지문(Passage) 프롬프트", key="passage_prompt", height=200, placeholder="지문 모드 지시/규칙...")

    # 액션 버튼
    st.markdown("### ③ 액션")
    b1, b2, b3, b4 = st.columns(4, vertical_alignment="center")

    # (a) 최신 프롬프트 불러오기(릴리스)
    with b1:
        if st.button("📥 최신 프롬프트 불러오기(릴리스 우선)", use_container_width=True, key="btn_fetch_prompts"):
            try:
                if callable(load_prompts_from_release) and callable(apply_prompts_to_session):
                    data = load_prompts_from_release()
                    apply_prompts_to_session(data)
                    st.success("최신 프롬프트를 세션에 주입했습니다. 아래 YAML 미리보기로 확인하세요.")
                else:
                    st.error("prompts_loader 모듈을 불러오지 못했습니다.")
            except Exception as e:
                st.exception(e)

    # (b) YAML 병합(LLM) — 선택 사항
    with b2:
        if st.button("🧠 전체 정리(LLM)", use_container_width=True, key="llm_all"):
            if callable(normalize_to_yaml):
                y = normalize_to_yaml(
                    grammar_text=st.session_state.get("grammar_prompt", "") or "",
                    sentence_text=st.session_state.get("sentence_prompt", "") or "",
                    passage_text=st.session_state.get("passage_prompt", "") or "",
                    openai_key=st.secrets.get("OPENAI_API_KEY"),
                    openai_model=st.secrets.get("OPENAI_MODEL", "gpt-4o-mini"),
                )
                st.session_state["_merged_yaml"] = y
            else:
                st.warning("LLM 정리기(normalize_to_yaml)를 찾지 못했습니다. 수동 YAML 미리보기로 진행하세요.")

    # (c) 수동 병합/미리보기 — LLM 없어도 동작
    with b3:
        if st.button("🧾 YAML 병합(로컬 필드→YAML)", use_container_width=True, key="merge_local"):
            # 관용 YAML 스냅샷(간결 포맷)
            doc = {
                "version": "auto",
                "persona": st.session_state.get("persona_text", "") or "",
                "modes": [
                    {"key": "grammar", "prompt": st.session_state.get("grammar_prompt", "") or ""},
                    {"key": "sentence", "prompt": st.session_state.get("sentence_prompt", "") or ""},
                    {"key": "passage", "prompt": st.session_state.get("passage_prompt", "") or ""},
                ],
            }
            st.session_state["_merged_yaml"] = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)

    # (d) 출판(Publish)
    with b4:
        publish_disabled = repo_config_error or not owner or not repo
        publish_clicked = st.button(
            "🚀 출판(Publish)",
            type="primary",
            use_container_width=True,
            key="publish_all",
            disabled=publish_disabled,
            help="GITHUB_REPO 시크릿이 설정되어 있어야 출판할 수 있습니다." if publish_disabled else None,
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

    # YAML 미리보기
    if st.session_state.get("_merged_yaml"):
        st.markdown("### YAML 미리보기")
        st.code(st.session_state["_merged_yaml"], language="yaml")


if __name__ == "__main__":
    main()
# ===== [01] FILE: src/ui/admin_prompt.py — END =====
