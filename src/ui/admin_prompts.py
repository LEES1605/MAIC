#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Admin UI — Prompts SSOT (Publish to GitHub Releases)

기능
- 탭1: YAML 직접 편집 → 스키마 검증 → 출판
- 탭2: 한글 입력으로 간단 템플릿 YAML 생성 → 검증 → 출판
- 출판은 GitHub Actions workflow_dispatch (publish-prompts.yml / inputs.yaml_b64)

필수 secrets (.streamlit/secrets.toml)
- APP_ADMIN_PASSWORD          : 간단 비밀번호 게이트
- GITHUB_REPO                 : "OWNER/REPO" (예: "LEES1605/MAIC")
- GITHUB_TOKEN                : GitHub PAT (공개 repo면 생략 가능)
- GITHUB_BRANCH               : ref (기본 "main")
- GITHUB_WORKFLOW             : "publish-prompts.yml" (워크플로 파일명)

의존:
- requests, pyyaml (UI 실행 환경)
"""
from __future__ import annotations

import base64
import importlib
import json
from pathlib import Path
from typing import Any, Dict, Tuple

# mypy: 외부 라이브러리 타입 스텁 이슈를 피하기 위해 동적 임포트 사용
st: Any = importlib.import_module("streamlit")
req: Any = importlib.import_module("requests")
import yaml  # pyyaml은 보통 타입 스텁 없이 사용해도 무방


# ----------------------------- Utilities -----------------------------

ELLIPSIS_UC = "\u2026"  # Unicode ellipsis. Keep source free of the actual character.


def _sanitize_ellipsis(text: str) -> Tuple[str, int]:
    """Replace Unicode ellipsis U+2026(...) with ASCII '...' to pass our CI gate."""
    count = text.count(ELLIPSIS_UC)
    return (text.replace(ELLIPSIS_UC, "..."), count)


def _load_schema() -> Dict[str, Any]:
    """Load JSON Schema from repo (schemas/prompts.schema.json)."""
    root = Path(__file__).resolve().parents[1]
    sp = root / "schemas" / "prompts.schema.json"
    if not sp.exists():
        raise FileNotFoundError(f"Schema not found: {sp}")
    return json.loads(sp.read_text(encoding="utf-8"))


def _validate_yaml_text(yaml_text: str) -> Tuple[bool, list[str]]:
    """Validate YAML (string) against Prompts schema; returns (ok, messages)."""
    try:
        data = yaml.safe_load(yaml_text)
        if not isinstance(data, dict):
            return (False, ["<root>: YAML must be a mapping (object)."])
    except Exception as e:  # noqa: BLE001
        return (False, [f"YAML parse error: {e}"])

    schema = _load_schema()
    try:
        js = importlib.import_module("jsonschema")
    except Exception as e:  # noqa: BLE001
        return (False, [f"jsonschema import failed: {e}"])

    validator_cls = getattr(js, "Draft202012Validator", None)
    if validator_cls is None:
        return (False, ["jsonschema.Draft202012Validator not found"])
    errors = sorted(validator_cls(schema).iter_errors(data), key=lambda e: list(e.path))
    if errors:
        msgs = []
        for e in errors:
            loc = "/".join(str(p) for p in e.path) or "<root>"
            msgs.append(f"{loc}: {e.message}")
        return (False, msgs)
    return (True, [])


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
    """Trigger GitHub Actions workflow_dispatch with inline YAML (base64)."""
    sanitized, replaced = _sanitize_ellipsis(yaml_text)
    if replaced:
        st.info(f"U+2026(...) {replaced}개를 '...'로 치환했습니다.")

    yaml_b64 = base64.b64encode(sanitized.encode("utf-8")).decode("ascii")
    url = (
        f"https://api.github.com/repos/{owner}/{repo}"
        f"/actions/workflows/{workflow}/dispatches"
    )
    payload = {
        "ref": ref,
        "inputs": {
            "yaml_b64": yaml_b64,
            "prerelease": "true" if prerelease else "false",
            "promote_latest": "true" if promote_latest else "false",
        },
    }
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    r = req.post(url, headers=headers, json=payload, timeout=20)
    if r.status_code not in (201, 204):
        raise RuntimeError(f"workflow_dispatch failed: HTTP {r.status_code} — {r.text}")


def _default_yaml() -> str:
    """Load sample YAML from repo or return minimal template."""
    candidate = Path("docs/_gpt/prompts.sample.yaml")
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
    # Minimal fallback (schema-conform)
    return """version: "1970-01-01T00:00:00Z#000"
modes:
  grammar:
    persona: ""
    system_instructions: ""
    guardrails: {}
    examples: []
    citations_policy: "[이유문법]/[문법서적]/[AI지식]"
    routing_hints: { model: "gpt-5-pro" }
  sentence:
    persona: ""
    system_instructions: ""
    guardrails: {}
    examples: []
    citations_policy: "[이유문법]/[문법서적]/[AI지식]"
    routing_hints: { model: "gemini-pro" }
  passage:
    persona: ""
    system_instructions: ""
    guardrails: {}
    examples: []
    citations_policy: "[이유문법]/[문법서적]/[AI지식]"
    routing_hints: { model: "gpt-5-pro" }
"""


def _build_yaml_from_simple_inputs(
    *,
    grammar_persona: str,
    grammar_sys: str,
    sentence_persona: str,
    sentence_sys: str,
    passage_persona: str,
    passage_sys: str,
) -> str:
    data: Dict[str, Any] = {
        "version": "auto",  # 서버(워크플로)에서 최종 태깅
        "modes": {
            "grammar": {
                "persona": grammar_persona.strip(),
                "system_instructions": grammar_sys.strip(),
                "guardrails": {"pii": True},
                "examples": [],
                "citations_policy": "[이유문법]/[문법서적]/[AI지식]",
                "routing_hints": {"model": "gpt-5-pro", "max_tokens": 800, "temperature": 0.2},
            },
            "sentence": {
                "persona": sentence_persona.strip(),
                "system_instructions": sentence_sys.strip(),
                "guardrails": {"pii": True},
                "examples": [],
                "citations_policy": "[이유문법]/[문법서적]/[AI지식]",
                "routing_hints": {"model": "gemini-pro", "max_tokens": 700, "temperature": 0.3},
            },
            "passage": {
                "persona": passage_persona.strip(),
                "system_instructions": passage_sys.strip(),
                "guardrails": {"pii": True},
                "examples": [],
                "citations_policy": "[이유문법]/[문법서적]/[AI지식]",
                "routing_hints": {"model": "gpt-5-pro", "max_tokens": 900, "temperature": 0.4},
            },
        },
    }
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


# ----------------------------- UI -----------------------------


def _admin_gate() -> None:
    st.set_page_config(page_title="Prompts Admin", page_icon="🛠️", layout="wide")
    st.title("Prompts Admin")
    with st.sidebar:
        st.subheader("Admin")
        pw = st.text_input("Password", type="password")
        if st.button("Unlock"):
            if pw and pw == st.secrets.get("APP_ADMIN_PASSWORD", ""):
                st.session_state["_admin_ok"] = True
            else:
                st.error("비밀번호가 올바르지 않습니다.")
    if not st.session_state.get("_admin_ok"):
        st.stop()


def main() -> None:
    _admin_gate()

    # Secrets → owner/repo/workflow/ref
    repo_full = st.secrets.get("GITHUB_REPO", "")
    if "/" not in repo_full:
        st.error("GITHUB_REPO 형식이 잘못되었습니다. 예: 'OWNER/REPO'")
        st.stop()
    owner, repo = repo_full.split("/", 1)
    token = st.secrets.get("GITHUB_TOKEN")
    ref = st.secrets.get("GITHUB_BRANCH", "main")
    workflow = st.secrets.get("GITHUB_WORKFLOW", "publish-prompts.yml")

    tab_yaml, tab_simple = st.tabs(["YAML 편집", "한글 → YAML 템플릿"])

    with tab_yaml:
        st.subheader("YAML 직접 편집")
        yaml_text = st.text_area(
            "Prompts YAML",
            value=_default_yaml(),
            height=420,
            placeholder="여기에 YAML을 붙여넣으세요.",
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔎 스키마 검증", use_container_width=True):
                ok, msgs = _validate_yaml_text(yaml_text)
                if ok:
                    st.success("스키마 검증 통과")
                else:
                    st.error("스키마 검증 실패")
                    st.write("\n".join(f"- {m}" for m in msgs))
        with col2:
            if st.button("🚀 출판(Publish)", type="primary", use_container_width=True):
                ok, msgs = _validate_yaml_text(yaml_text)
                if not ok:
                    st.error("스키마 검증 실패 — 먼저 오류를 해결하세요.")
                    st.write("\n".join(f"- {m}" for m in msgs))
                else:
                    try:
                        _gh_dispatch_workflow(
                            owner=owner,
                            repo=repo,
                            workflow=workflow,
                            ref=ref,
                            token=token,
                            yaml_text=yaml_text,
                            prerelease=False,
                            promote_latest=True,
                        )
                        st.success("출판 요청 전송 완료 — Actions에서 처리 중입니다.")
                        st.markdown(
                            f"[열기: Actions › {workflow}]"
                            f"(https://github.com/{owner}/{repo}/actions/workflows/{workflow})"
                        )
                    except Exception as e:  # noqa: BLE001
                        st.exception(e)

    with tab_simple:
        st.subheader("한글 입력으로 YAML 생성(간단 템플릿)")
        with st.expander("문법(Grammar)", expanded=True):
            g_persona = st.text_area(
                "persona",
                value="친절한 선생님 톤, 이유문법/깨알문법 근거를 먼저 인용",
                height=80,
            )
            g_sys = st.text_area(
                "system_instructions",
                value="규칙→근거→예문→요약 순서로 답해",
                height=80,
            )
        with st.expander("문장(Sentence)", expanded=True):
            s_persona = st.text_area(
                "persona",
                value='분석가 톤, 사용자 괄호규칙/기타 규칙과 "괄호 규칙 라벨 표준"을 준수',
                height=80,
            )
            s_sys = st.text_area(
                "system_instructions",
                value="토큰화→구문(괄호규칙)→어감/의미분석",
                height=80,
            )
        with st.expander("지문(Passage)", expanded=False):
            p_persona = st.text_area("persona", value="쉬운 비유로 요지/주제/제목 정리", height=80)
            p_sys = st.text_area(
                "system_instructions",
                value="요지→예시/비유→주제→제목",
                height=80,
            )

        built_yaml = _build_yaml_from_simple_inputs(
            grammar_persona=g_persona,
            grammar_sys=g_sys,
            sentence_persona=s_persona,
            sentence_sys=s_sys,
            passage_persona=p_persona,
            passage_sys=p_sys,
        )
        st.code(built_yaml, language="yaml")

        col3, col4 = st.columns(2)
        with col3:
            if st.button("🔎 스키마 검증(템플릿)", use_container_width=True):
                ok, msgs = _validate_yaml_text(built_yaml)
                if ok:
                    st.success("스키마 검증 통과(템플릿)")
                else:
                    st.error("스키마 검증 실패(템플릿)")
                    st.write("\n".join(f"- {m}" for m in msgs))
        with col4:
            if st.button("🚀 출판(Publish, 템플릿)", type="primary", use_container_width=True):
                ok, msgs = _validate_yaml_text(built_yaml)
                if not ok:
                    st.error("스키마 검증 실패 — 먼저 오류를 해결하세요.")
                    st.write("\n".join(f"- {m}" for m in msgs))
                else:
                    try:
                        _gh_dispatch_workflow(
                            owner=owner,
                            repo=repo,
                            workflow=workflow,
                            ref=ref,
                            token=token,
                            yaml_text=built_yaml,
                        )
                        st.success("출판 요청 전송 완료 — Actions에서 처리 중입니다.")
                        st.markdown(
                            f"[열기: Actions › {workflow}]"
                            f"(https://github.com/{owner}/{repo}/actions/workflows/{workflow})"
                        )
                    except Exception as e:  # noqa: BLE001
                        st.exception(e)


if __name__ == "__main__":
    main()
