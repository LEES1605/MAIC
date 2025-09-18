# [FILE: src/ui/admin_prompts.py] START
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Admin UI — Prompts SSOT (Publish to GitHub Releases)

탭:
- YAML 직접 편집
- 한글 → YAML 템플릿
- 한글 → LLM 정리 → YAML

출판은 GitHub Actions workflow_dispatch로 트리거합니다.
"""
from __future__ import annotations

import base64
import importlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, Tuple

import yaml

# ---- 정적 import(파일 상단 유지: ruff E402 대응) ----
from src.ui.assist.prompt_normalizer import normalize_to_yaml  # noqa: E402

# ---- ensure_admin_sidebar: 동적 import 폴백 (mypy-safe) ----
#   - 우선순위: src.ui.utils.sider → src.ui.utils.sidebar → no-op
ensure_admin_sidebar: Callable[[], None]
try:
    _mod = importlib.import_module("src.ui.utils.sider")
    ensure_admin_sidebar = getattr(_mod, "ensure_admin_sidebar")
except Exception:
    try:
        _mod = importlib.import_module("src.ui.utils.sidebar")
        ensure_admin_sidebar = getattr(_mod, "ensure_admin_sidebar")
    except Exception:
        def _noop() -> None:
            return
        ensure_admin_sidebar = _noop

# ---- 외부 라이브러리 동적 import ----
st: Any = importlib.import_module("streamlit")
req: Any = importlib.import_module("requests")

# ----------------------------- Utilities -----------------------------

ELLIPSIS_UC = "\u2026"


def _sanitize_ellipsis(text: str) -> Tuple[str, int]:
    count = text.count(ELLIPSIS_UC)
    return text.replace(ELLIPSIS_UC, "..."), count


def _load_schema() -> Dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    sp = root / "schemas" / "prompts.schema.json"
    if not sp.exists():
        raise FileNotFoundError(f"Schema not found: {sp}")
    return json.loads(sp.read_text(encoding="utf-8"))


def _validate_yaml_text(yaml_text: str) -> Tuple[bool, list[str]]:
    try:
        data = yaml.safe_load(yaml_text)
        if not isinstance(data, dict):
            return False, ["<root>: YAML must be a mapping (object)."]
    except Exception as exc:  # noqa: BLE001
        return False, [f"YAML parse error: {exc}"]

    schema = _load_schema()
    try:
        js = importlib.import_module("jsonschema")
    except Exception as exc:  # noqa: BLE001
        return False, [f"jsonschema import failed: {exc}"]

    validator_cls = getattr(js, "Draft202012Validator", None)
    if validator_cls is None:
        return False, ["jsonschema.Draft202012Validator not found"]

    validation_errors = sorted(
        validator_cls(schema).iter_errors(data),
        key=lambda err: list(err.path),
    )
    if validation_errors:
        msgs: list[str] = []
        for verr in validation_errors:
            loc = "/".join(str(p) for p in verr.path) or "<root>"
            msgs.append(f"{loc}: {verr.message}")
        return False, msgs
    return True, []


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
    sanitized, replaced = _sanitize_ellipsis(yaml_text)
    if replaced:
        st.info(f"U+2026(...) {replaced}개를 '...'로 치환했습니다.")

    yaml_b64 = base64.b64encode(sanitized.encode("utf-8")).decode("ascii")
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
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
    candidate = Path("docs/_gpt/prompts.sample.yaml")
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
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
        "version": "auto",
        "modes": {
            "grammar": {
                "persona": grammar_persona.strip(),
                "system_instructions": grammar_sys.strip(),
                "guardrails": {"pii": True},
                "examples": [],
                "citations_policy": "[이유문법]/[문법서적]/[AI지식]",
                "routing_hints": {
                    "model": "gpt-5-pro",
                    "max_tokens": 800,
                    "temperature": 0.2,
                },
            },
            "sentence": {
                "persona": sentence_persona.strip(),
                "system_instructions": sentence_sys.strip(),
                "guardrails": {"pii": True},
                "examples": [],
                "citations_policy": "[이유문법]/[문법서적]/[AI지식]",
                "routing_hints": {
                    "model": "gemini-pro",
                    "max_tokens": 700,
                    "temperature": 0.3,
                },
            },
            "passage": {
                "persona": passage_persona.strip(),
                "system_instructions": passage_sys.strip(),
                "guardrails": {"pii": True},
                "examples": [],
                "citations_policy": "[이유문법]/[문법서적]/[AI지식]",
                "routing_hints": {
                    "model": "gpt-5-pro",
                    "max_tokens": 900,
                    "temperature": 0.4,
                },
            },
        },
    }
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


# ----------------------------- UI -----------------------------

def _admin_gate() -> None:
    st.set_page_config(page_title="Prompts Admin", page_icon="🛠️", layout="wide")
    with st.sidebar:
        st.subheader("Admin")
        if st.session_state.get("_admin_ok"):
            st.success("관리자 모드 활성")
        else:
            pw = st.text_input("Password", type="password")
            if st.button("Unlock"):
                if pw and pw == st.secrets.get("APP_ADMIN_PASSWORD", ""):
                    st.session_state["_admin_ok"] = True
                else:
                    st.error("비밀번호가 올바르지 않습니다.")
    if not st.session_state.get("_admin_ok"):
        # 학생 모드: 사이드바 숨김
        ensure_admin_sidebar()  # 내부에서 숨김 처리
        st.stop()
    # 관리자 모드: 사이드바 보이기
    ensure_admin_sidebar()


def main() -> None:
    _admin_gate()

    repo_full = st.secrets.get("GITHUB_REPO", "")
    if "/" not in repo_full:
        st.error("GITHUB_REPO 형식이 잘못되었습니다. 예: 'OWNER/REPO'")
        st.stop()
    owner, repo = repo_full.split("/", 1)
    token = st.secrets.get("GITHUB_TOKEN")
    ref = st.secrets.get("GITHUB_BRANCH", "main")
    workflow = st.secrets.get("GITHUB_WORKFLOW", "publish-prompts.yml")

    tab_yaml, tab_simple, tab_llm = st.tabs(
        ["YAML 편집", "한글 → YAML 템플릿", "한글 → LLM 정리 → YAML"]
    )

    # ---------------- YAML 직접 편집 ----------------
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
            if st.button("🔎 스키마 검증", use_container_width=True, key="v_yaml"):
                ok, msgs = _validate_yaml_text(yaml_text)
                if ok:
                    st.success("스키마 검증 통과")
                else:
                    st.error("스키마 검증 실패")
                    st.write("\n".join(f"- {m}" for m in msgs))
        with col2:
            if st.button(
                "🚀 출판(Publish)",
                type="primary",
                use_container_width=True,
                key="p_yaml",
            ):
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
                    except Exception as exc:  # noqa: BLE001
                        st.exception(exc)

    # ---------------- 한글 → 템플릿 ----------------
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
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔎 검증(템플릿)", use_container_width=True, key="v_tpl"):
                ok, msgs = _validate_yaml_text(built_yaml)
                st.success("검증 통과") if ok else st.error("\n".join(f"- {m}" for m in msgs))
        with c2:
            if st.button("🚀 출판(템플릿)", type="primary", use_container_width=True, key="p_tpl"):
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
                    except Exception as exc:  # noqa: BLE001
                        st.exception(exc)

    # ---------------- 한글 → LLM 정리 → YAML ----------------
    with tab_llm:
        st.subheader("자연어로 쓰면 LLM이 YAML로 정리합니다")
        g = st.text_area(
            "문법 원문",
            height=100,
            placeholder="문법 페르소나/지시를 자유롭게 적어주세요.",
        )
        s = st.text_area(
            "문장 원문",
            height=100,
            placeholder="문장 페르소나/지시를 자유롭게 적어주세요.",
        )
        p = st.text_area(
            "지문 원문",
            height=100,
            placeholder="지문 페르소나/지시를 자유롭게 적어주세요.",
        )

        if st.button("🧩 정리하기(LLM)", use_container_width=True, key="llm_build"):
            openai_key = st.secrets.get("OPENAI_API_KEY")
            yaml_out = normalize_to_yaml(
                grammar_text=g,
                sentence_text=s,
                passage_text=p,
                openai_key=openai_key,
                openai_model=st.secrets.get("OPENAI_MODEL", "gpt-4o-mini"),
            )
            st.code(yaml_out, language="yaml")
            st.session_state["_llm_yaml"] = yaml_out

        if st.session_state.get("_llm_yaml"):
            colx, coly = st.columns(2)
            with colx:
                if st.button("🔎 검증(LLM)", use_container_width=True, key="v_llm"):
                    ok, msgs = _validate_yaml_text(st.session_state["_llm_yaml"])
                    if ok:
                        st.success("스키마 검증 통과")
                    else:
                        st.error("스키마 검증 실패")
                        st.write("\n".join(f"- {m}" for m in msgs))
            with coly:
                if st.button("🚀 출판(LLM)", type="primary", use_container_width=True, key="p_llm"):
                    ok, msgs = _validate_yaml_text(st.session_state["_llm_yaml"])
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
                                yaml_text=st.session_state["_llm_yaml"],
                            )
                            st.success("출판 요청 전송 완료 — Actions에서 처리 중입니다.")
                        except Exception as exc:  # noqa: BLE001
                            st.exception(exc)


if __name__ == "__main__":
    main()
# [FILE: src/ui/admin_prompts.py] END
