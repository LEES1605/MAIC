# ===== [01] FILE: src/ui/admin_prompt.py — START =====
# -*- coding: utf-8 -*-
"""
관리자 프롬프트 편집기 — 페르소나 + 모드별 프롬프트(문법/문장/지문)

핵심:
- 프롬프트 페이지에서도 app.py와 동일하게
  (1) 기본 멀티페이지 네비 CSS 숨김
  (2) 관리자 미니 사이드바(apply_admin_chrome) 렌더
- 최신 프롬프트 불러오기는 '프리필 예약 → rerun → 위젯 렌더 전 주입' 핸드셰이크로 예외 제거

SSOT:
- 문서/프롬프트의 단일 진실 소스는 docs/_gpt/ (Workspace Pointer 정책). :contentReference[oaicite:2]{index=2}
"""

from __future__ import annotations

import base64
import io
import importlib
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml

# -- deps
st: Any = importlib.import_module("streamlit")
req: Any = importlib.import_module("requests")

# -- loader: 릴리스 → SSOT 폴백(페르소나+3모드 추출)
#    (release pages 순회 + docs/_gpt/prompts.yaml 폴백) :contentReference[oaicite:3]{index=3}
_loader = importlib.import_module("src.ui.assist.prompts_loader")
load_prompts_from_release = getattr(_loader, "load_prompts_from_release")
apply_prompts_to_session = getattr(_loader, "apply_prompts_to_session")

# -- sider: 관리자 미니바(app.py와 동일한 버튼 구색) :contentReference[oaicite:4]{index=4}
try:
    _sider = importlib.import_module("src.ui.utils.sider")
    apply_admin_chrome = getattr(_sider, "apply_admin_chrome")
except Exception:
    def apply_admin_chrome(**_: Any) -> None:  # 폴백
        return


# ===== [02] 공통: 기본 네비 숨김 + 스키마 검증 + GH dispatch =====
def _hide_default_page_nav() -> None:
    """app.py에서 쓰는 CSS와 동일하게 페이지 네비를 숨긴다. :contentReference[oaicite:5]{index=5}"""
    st.markdown(
        "<style>"
        "nav[data-testid='stSidebarNav']{display:none!important;}"
        "div[data-testid='stSidebarNav']{display:none!important;}"
        "section[data-testid='stSidebar'] [data-testid='stSidebarNav']{display:none!important;}"
        "section[data-testid='stSidebar'] ul[role='list']{display:none!important;}"
        "</style>",
        unsafe_allow_html=True,
    )

ELLIPSIS_UC = "\u2026"

def _sanitize_ellipsis(text: str) -> Tuple[str, int]:
    c = text.count(ELLIPSIS_UC)
    return text.replace(ELLIPSIS_UC, "..."), c


def _load_schema() -> Optional[dict]:
    """schemas/prompts.schema.json이 있을 때만 스키마 체크."""
    root = Path(__file__).resolve().parents[1]
    sp = root / "schemas" / "prompts.schema.json"
    if not sp.exists():
        return None
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
        if not validator:
            return True, ["jsonschema 미탑재 — 구조 검사는 건너뜀"]
        schema = _load_schema()
        if not schema:
            return True, []
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


def _gh_dispatch_workflow(
    *, owner: str, repo: str, workflow: str, ref: str, token: Optional[str], yaml_text: str
) -> None:
    s, n = _sanitize_ellipsis(yaml_text)
    if n:
        st.info(f"U+2026 {n}개를 '...'로 치환했습니다.")
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
    payload = {"ref": ref, "inputs": {
        "yaml_b64": base64.b64encode(s.encode("utf-8")).decode("ascii"),
        "prerelease": "false",
        "promote_latest": "true",
    }}
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = req.post(url, headers=headers, json=payload, timeout=20)
    if r.status_code not in (201, 204):
        raise RuntimeError(f"workflow_dispatch failed: {r.status_code} — {r.text}")


# ===== [03] 프리필 핸드셰이크(충돌 방지 핵심) =====
def _apply_pending_prefill() -> None:
    """
    버튼 클릭 런에서는 _PREFILL_PROMPTS에만 저장 → rerun.
    다음 런 초반(위젯 생성 전) 여기서 한 번에 주입.
    """
    pending = st.session_state.pop("_PREFILL_PROMPTS", None)
    if isinstance(pending, dict) and pending:
        # 관용 키 매핑으로 세션키(persona_text, grammar_prompt, ...) 주입. :contentReference[oaicite:6]{index=6}
        apply_prompts_to_session(pending)


# ===== [04] 메인 =====
def main() -> None:
    st.set_page_config(page_title="Prompts Admin", page_icon="🛠️", layout="wide")

    # 1) 기본 네비 숨김 + 관리자 미니바(app.py와 동일한 버튼)  :contentReference[oaicite:7]{index=7}
    _hide_default_page_nav()
    apply_admin_chrome(back_page="app.py", icon_only=True)

    # 2) 위젯 생성 전에 프리필 예약분을 세션키에 주입(핵심)
    _apply_pending_prefill()

    # 3) 상태 박스(간단)
    with st.container(border=True):
        st.subheader("🩺 상태 점검")
        repo_full = st.secrets.get("GITHUB_REPO", "")
        token = st.secrets.get("GITHUB_TOKEN")
        ref = st.secrets.get("GITHUB_BRANCH", "main")
        workflow = st.secrets.get("GITHUB_WORKFLOW", "publish-prompts.yml")

        owner = repo = ""
        repo_bad = True
        if repo_full and "/" in repo_full:
            owner, repo = repo_full.split("/", 1)
            repo_bad = not owner or not repo
        if repo_bad:
            st.warning("출판 비활성화: GITHUB_REPO 시크릿이 필요합니다. 형식: OWNER/REPO")

        st.caption(f"GITHUB_REPO = {repo_full or '(unset)'}")

    # 4) 입력 UI
    st.markdown("### ① 페르소나(공통)")
    st.text_area("모든 모드에 공통 적용", key="persona_text", height=180,
                 placeholder="페르소나 텍스트...")

    st.markdown("### ② 모드별 프롬프트(지시/규칙)")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.text_area("문법(Grammar) 프롬프트", key="grammar_prompt", height=220,
                     placeholder="문법 모드 지시/규칙...")
    with c2:
        st.text_area("문장(Sentence) 프롬프트", key="sentence_prompt", height=220,
                     placeholder="문장 모드 지시/규칙...")
    with c3:
        st.text_area("지문(Passage) 프롬프트", key="passage_prompt", height=220,
                     placeholder="지문 모드 지시/규칙...")

    # 5) 액션들
    st.markdown("### ③ 액션")
    a, b, c, d, e = st.columns(5)

    # (A) 최신 프롬프트 불러오기 — 릴리스 우선, 실패 시 SSOT 폴백  :contentReference[oaicite:8]{index=8}
    with a:
        if st.button("📥 최신 프롬프트 불러오기(릴리스 우선)", use_container_width=True):
            try:
                data = load_prompts_from_release()  # persona + grammar/sentence/passage
                # ❗️같은 런에서 위젯 키를 직접 덮지 않는다 → 예약 후 rerun
                st.session_state["_PREFILL_PROMPTS"] = data
                st.rerun()
            except Exception as e:
                st.exception(e)

    # (B) YAML 병합(로컬 필드→YAML)
    with b:
        if st.button("🧾 YAML 병합(로컬 필드→YAML)", use_container_width=True):
            doc = {
                "version": "auto",
                "persona": st.session_state.get("persona_text", "") or "",
                "modes": [
                    {"key": "grammar", "prompt": st.session_state.get("grammar_prompt", "") or ""},
                    {"key": "sentence", "prompt": st.session_state.get("sentence_prompt", "") or ""},
                    {"key": "passage", "prompt": st.session_state.get("passage_prompt", "") or ""},
                ],
            }
            st.session_state["_PROMPTS_YAML"] = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
            st.success("YAML 병합 완료 — 아래 미리보기 확인")

    # (C) 스키마 검증
    with c:
        if st.button("🔎 스키마 검증", use_container_width=True):
            y = st.session_state.get("_PROMPTS_YAML", "") or ""
            if not y:
                st.warning("먼저 ‘🧾 YAML 병합’을 실행하세요.")
            else:
                ok, msgs = _validate_yaml_text(y)
                if ok:
                    st.success("검증 통과")
                else:
                    st.error("스키마 검증 실패")
                    if msgs:
                        st.code("\n".join(f"- {m}" for m in msgs))

    # (D) YAML 다운로드
    with d:
        y = st.session_state.get("_PROMPTS_YAML", "") or ""
        st.download_button("📥 YAML 다운로드", data=io.BytesIO(y.encode("utf-8")),
                           file_name="prompts.yaml", mime="text/yaml",
                           use_container_width=True, disabled=not bool(y))

    # (E) 출판
    with e:
        repo_full = st.secrets.get("GITHUB_REPO", "")
        token = st.secrets.get("GITHUB_TOKEN")
        ref = st.secrets.get("GITHUB_BRANCH", "main")
        workflow = st.secrets.get("GITHUB_WORKFLOW", "publish-prompts.yml")

        owner = repo = ""
        disabled = True
        if repo_full and "/" in repo_full:
            owner, repo = repo_full.split("/", 1)
            disabled = not (owner and repo and st.session_state.get("_PROMPTS_YAML"))

        if st.button("🚀 출판(Publish)", type="primary", use_container_width=True,
                     disabled=disabled,
                     help=None if not disabled else "GITHUB_REPO 시크릿과 병합된 YAML이 필요합니다."):
            y = st.session_state.get("_PROMPTS_YAML", "") or ""
            ok, msgs = _validate_yaml_text(y)
            if not ok:
                st.error("스키마 검증 실패 — 먼저 오류를 해결하세요.")
                if msgs:
                    st.code("\n".join(f"- {m}" for m in msgs))
            else:
                try:
                    _gh_dispatch_workflow(owner=owner, repo=repo, workflow=workflow, ref=ref, token=token, yaml_text=y)
                    st.success("출판 요청 전송 완료 — Actions에서 처리 중입니다.")
                    st.markdown(
                        f"[열기: Actions › {workflow}]"
                        f"(https://github.com/{owner}/{repo}/actions/workflows/{workflow})"
                    )
                except Exception as exc:  # noqa: BLE001
                    st.exception(exc)

    # 6) 미리보기
    ytext = st.session_state.get("_PROMPTS_YAML")
    if ytext:
        st.markdown("### YAML 미리보기")
        st.code(ytext, language="yaml")


if __name__ == "__main__":
    main()
# ===== [01] FILE: src/ui/admin_prompt.py — END =====
