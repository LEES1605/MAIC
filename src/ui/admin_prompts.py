# ===== [01] FILE: src/ui/admin_prompts.py — START =====
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Admin UI — Prompts SSOT & Release Restore."""
from __future__ import annotations

import base64
import importlib
import io
import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

import yaml
from src.ui.assist.prompt_normalizer import normalize_to_yaml  # ruff: E402 ok

# ---- dynamic libs ----
st: Any = importlib.import_module("streamlit")
req: Any = importlib.import_module("requests")

# ---- sidebar helpers (sider → sidebar → no-op) ----
ensure_admin_sidebar: Callable[[], None]
render_minimal_admin_sidebar: Callable[..., None]
try:
    _sider = importlib.import_module("src.ui.utils.sider")
    ensure_admin_sidebar = getattr(_sider, "ensure_admin_sidebar")
    render_minimal_admin_sidebar = getattr(_sider, "render_minimal_admin_sidebar")
except Exception:
    try:
        _sider = importlib.import_module("src.ui.utils.sidebar")
        ensure_admin_sidebar = getattr(_sider, "ensure_admin_sidebar")
        def render_minimal_admin_sidebar(*_: Any, **__: Any) -> None:
            return
    except Exception:
        def ensure_admin_sidebar() -> None:
            return
        def render_minimal_admin_sidebar(*_: Any, **__: Any) -> None:
            return

# ===== [02] schema/validate utils — START =====
ELLIPSIS_UC = "\u2026"


def _sanitize_ellipsis(text: str) -> Tuple[str, int]:
    c = text.count(ELLIPSIS_UC)
    return text.replace(ELLIPSIS_UC, "..."), c


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
            return False, ["<root>: mapping(object) required"]
    except Exception as exc:  # noqa: BLE001
        return False, [f"YAML parse error: {exc}"]

    schema = _load_schema()
    try:
        js = importlib.import_module("jsonschema")
    except Exception as exc:  # noqa: BLE001
        return False, [f"jsonschema import failed: {exc}"]

    validator = getattr(js, "Draft202012Validator", None)
    if validator is None:
        return False, ["jsonschema.Draft202012Validator not found"]

    errs = sorted(validator(schema).iter_errors(data), key=lambda e: list(e.path))
    if errs:
        msgs = []
        for e in errs:
            loc = "/".join(str(p) for p in e.path) or "<root>"
            msgs.append(f"{loc}: {e.message}")
        return False, msgs
    return True, []
# ===== [02] schema/validate utils — END =====

# ===== [03] GH dispatch (publish) — START =====
def _gh_dispatch_workflow(
    *,
    owner: str,
    repo: str,
    workflow: str,
    ref: str,
    token: Optional[str],
    yaml_text: str,
    prerelease: bool = False,
    promote_latest: bool = True,
) -> None:
    s, n = _sanitize_ellipsis(yaml_text)
    if n:
        st.info(f"U+2026 {n}개를 '...'로 치환했습니다.")
    yaml_b64 = base64.b64encode(s.encode("utf-8")).decode("ascii")
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
    payload = {"ref": ref, "inputs": {
        "yaml_b64": yaml_b64,
        "prerelease": "true" if prerelease else "false",
        "promote_latest": "true" if promote_latest else "false",
    }}
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = req.post(url, headers=headers, json=payload, timeout=20)
    if r.status_code not in (201, 204):
        raise RuntimeError(f"workflow_dispatch failed: {r.status_code} — {r.text}")
# ===== [03] GH dispatch (publish) — END =====

# ===== [04] release restore helpers — START =====
def _effective_persist_dir(cli_dir: Optional[str] = None) -> Path:
    """SSOT 우선, 실패 시 ~/.maic/persist 폴백."""
    if cli_dir:
        return Path(cli_dir).expanduser().resolve()
    # secrets 우선
    if os.environ.get("MAIC_PERSIST_DIR"):
        return Path(os.environ["MAIC_PERSIST_DIR"]).expanduser().resolve()
    if st.secrets.get("MAIC_PERSIST_DIR"):
        return Path(st.secrets["MAIC_PERSIST_DIR"]).expanduser().resolve()
    # 앱 헬퍼 시도
    try:
        from src.core.persist import effective_persist_dir
        p = effective_persist_dir()
        return p if isinstance(p, Path) else Path(str(p)).expanduser().resolve()
    except Exception:
        pass
    return (Path.home() / ".maic" / "persist").resolve()


def _safe_extract_zip(zip_bytes: bytes, dest: Path) -> None:
    """Zip Path Traversal 방지 추출."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for m in zf.infolist():
            # skip directories
            if m.is_dir():
                continue
            # resolve safe path
            tgt = (dest / m.filename).resolve()
            if not str(tgt).startswith(str(dest.resolve())):
                raise RuntimeError(f"unsafe path in zip: {m.filename}")
            tgt.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(m) as s, open(tgt, "wb") as t:
                t.write(s.read())


def _verify_persist_ready(persist: Path) -> Tuple[bool, str]:
    """scripts/verify_index_ready와 동일 규칙 사용."""
    # 1) chunks.jsonl 찾기
    root = persist / "chunks.jsonl"
    chunks: Optional[Path] = None
    if root.exists() and root.stat().st_size > 0:
        chunks = root
    else:
        for p in persist.rglob("chunks.jsonl"):
            if p.is_file() and p.stat().st_size > 0:
                chunks = p
                break
    if chunks is None:
        return False, "missing: chunks.jsonl"

    # 2) .ready 검사 ('ready' or 'ok')
    ready = persist / ".ready"
    if not ready.exists():
        return False, "missing: .ready"
    raw = ""
    try:
        raw = ready.read_text(encoding="utf-8", errors="ignore").strip().lower()
    except Exception:
        raw = ""
    if raw in {"ready", "ok"}:
        return True, f"OK: chunks.jsonl & .ready='{raw}'"
    return False, f"mismatch: .ready='{raw or '(empty)'}'"
# ===== [04] release restore helpers — END =====

# ===== [05] default YAML builder — START =====
def _default_yaml() -> str:
    c = Path("docs/_gpt/prompts.sample.yaml")
    if c.exists():
        return c.read_text(encoding="utf-8")
    return (
        'version: "1970-01-01T00:00:00Z#000"\n'
        "modes:\n"
        "  grammar:\n"
        '    persona: ""\n'
        '    system_instructions: ""\n'
        "    guardrails: {}\n"
        "    examples: []\n"
        '    citations_policy: "[이유문법]/[문법서적]/[AI지식]"\n'
        '    routing_hints: { model: "gpt-5-pro" }\n'
        "  sentence:\n"
        '    persona: ""\n'
        '    system_instructions: ""\n'
        "    guardrails: {}\n"
        "    examples: []\n"
        '    citations_policy: "[이유문법]/[문법서적]/[AI지식]"\n'
        '    routing_hints: { model: "gemini-pro" }\n'
        "  passage:\n"
        '    persona: ""\n'
        '    system_instructions: ""\n'
        "    guardrails: {}\n"
        "    examples: []\n"
        '    citations_policy: "[이유문법]/[문법서적]/[AI지식]"\n'
        '    routing_hints: { model: "gpt-5-pro" }\n'
    )
# ===== [05] default YAML builder — END =====

# ===== [06] simple YAML builder — START =====
def _build_yaml_from_inputs(*, g_p: str, g_s: str, s_p: str, s_s: str, p_p: str, p_s: str) -> str:
    data: Dict[str, Any] = {
        "version": "auto",
        "modes": {
            "grammar": {
                "persona": g_p.strip(),
                "system_instructions": g_s.strip(),
                "guardrails": {"pii": True},
                "examples": [],
                "citations_policy": "[이유문법]/[문법서적]/[AI지식]",
                "routing_hints": {"model": "gpt-5-pro", "max_tokens": 800, "temperature": 0.2},
            },
            "sentence": {
                "persona": s_p.strip(),
                "system_instructions": s_s.strip(),
                "guardrails": {"pii": True},
                "examples": [],
                "citations_policy": "[이유문법]/[문법서적]/[AI지식]",
                "routing_hints": {"model": "gemini-pro", "max_tokens": 700, "temperature": 0.3},
            },
            "passage": {
                "persona": p_p.strip(),
                "system_instructions": p_s.strip(),
                "guardrails": {"pii": True},
                "examples": [],
                "citations_policy": "[이유문법]/[문법서적]/[AI지식]",
                "routing_hints": {"model": "gpt-5-pro", "max_tokens": 900, "temperature": 0.4},
            },
        },
    }
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
# ===== [06] simple YAML builder — END =====

# ===== [07] admin gate & sidebar — START =====
def _admin_gate() -> None:
    st.set_page_config(page_title="Prompts Admin", page_icon="🛠️", layout="wide")
    with st.sidebar:
        st.subheader("Admin")
        if st.session_state.get("_admin_ok"):
            st.success("관리자 모드 활성")
        else:
            pw = st.text_input("Password", type="password", key="adm_pw")
            if st.button("Unlock", key="adm_unlock"):
                if pw and pw == st.secrets.get("APP_ADMIN_PASSWORD", ""):
                    # 플래그 동기화 + 리런
                    st.session_state["_admin_ok"] = True
                    st.session_state["admin_mode"] = True
                    st.experimental_set_query_params(admin="1")
                    st.rerun()
                else:
                    st.error("비밀번호가 올바르지 않습니다.")
    if not st.session_state.get("_admin_ok"):
        ensure_admin_sidebar()  # 학생: 숨김
        st.stop()
    ensure_admin_sidebar()      # 관리자: 펼침
    render_minimal_admin_sidebar(back_page="app.py")
# ===== [07] admin gate & sidebar — END =====

# ===== [08] release restore (latest) — START =====
def _restore_latest_release(owner: str, repo: str, token: Optional[str]) -> Tuple[bool, str]:
    """최신 릴리스에서 zip 자산을 찾아 persist에 복원하고 검증."""
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    r = req.get(url, headers=h, timeout=20)
    if r.status_code != 200:
        return False, f"latest release failed: {r.status_code}"

    assets = r.json().get("assets", []) or []
    pick = None
    # index/indices zip 우선
    for a in assets:
        n = str(a.get("name", ""))
        if re.search(r"(index|indices).+\.zip$", n, flags=re.I):
            pick = a
            break
    if not pick and assets:
        pick = assets[0]
    if not pick:
        return False, "no release asset"

    dl = pick.get("browser_download_url")
    if not dl:
        return False, "asset has no download url"

    r2 = req.get(dl, timeout=60)
    if r2.status_code != 200:
        return False, f"download failed: {r2.status_code}"

    dest = _effective_persist_dir()
    dest.mkdir(parents=True, exist_ok=True)
    _safe_extract_zip(r2.content, dest)

    # 검증 (CLI 규칙 동일). false positive 방지
    ok, why = _verify_persist_ready(dest)
    if ok:
        # 성공 마커 업데이트
        (dest / ".ready").write_text("ready", encoding="utf-8")
    return ok, why
# ===== [08] release restore (latest) — END =====

# ===== [09] main UI — START =====
def main() -> None:
    _admin_gate()

    repo_full = st.secrets.get("GITHUB_REPO", "")
    if "/" not in repo_full:
        st.error("GITHUB_REPO 형식이 잘못되었습니다. 예: OWNER/REPO")
        st.stop()
    owner, repo = repo_full.split("/", 1)
    token = st.secrets.get("GITHUB_TOKEN")
    ref = st.secrets.get("GITHUB_BRANCH", "main")
    workflow = st.secrets.get("GITHUB_WORKFLOW", "publish-prompts.yml")

    # 상단: 릴리스 복원 섹션
    with st.expander("🗄️ 인덱스 릴리스 복원 (최신)", expanded=False):
        if st.button("⬇️ 최신 릴리스에서 복원", type="primary", key="restore_btn"):
            with st.spinner("복원 중..."):
                ok, why = _restore_latest_release(owner, repo, token)
            if ok:
                st.success(f"복원 성공 — {why}")
            else:
                st.error(f"복원 실패 — {why}")

    # 탭: 문법/문장/지문
    tab_g, tab_s, tab_p = st.tabs(["문법", "문장", "지문"])

    with tab_g:
        g_p = st.text_area("문법 persona", height=80, key="g_p")
        g_s = st.text_area("문법 system_instructions", height=80, key="g_s")
    with tab_s:
        s_p = st.text_area("문장 persona", height=80, key="s_p")
        s_s = st.text_area("문장 system_instructions", height=80, key="s_s")
    with tab_p:
        p_p = st.text_area("지문 persona", height=80, key="p_p")
        p_s = st.text_area("지문 system_instructions", height=80, key="p_s")

    col_a, col_b, col_c = st.columns(3)
    yaml_merged = _build_yaml_from_inputs(g_p=g_p or "", g_s=g_s or "",
                                          s_p=s_p or "", s_s=s_s or "",
                                          p_p=p_p or "", p_s=p_s or "")
    with col_a:
        if st.button("🧩 병합 미리보기", use_container_width=True, key="merge"):
            st.session_state["_merged_yaml"] = yaml_merged
    with col_b:
        if st.button("🔎 스키마 검증", use_container_width=True, key="validate"):
            ok, msgs = _validate_yaml_text(yaml_merged)
            st.success("검증 통과") if ok else st.error("\n".join(f"- {m}" for m in msgs))
    with col_c:
        if st.button("🚀 출판(Publish)", type="primary", use_container_width=True, key="publish"):
            ok, msgs = _validate_yaml_text(yaml_merged)
            if not ok:
                st.error("스키마 검증 실패 — 먼저 오류를 해결하세요.")
                st.write("\n".join(f"- {m}" for m in msgs))
            else:
                try:
                    _gh_dispatch_workflow(owner=owner, repo=repo, workflow=workflow,
                                          ref=ref, token=token, yaml_text=yaml_merged)
                    st.success("출판 요청 전송 완료 — Actions에서 처리 중입니다.")
                    st.markdown(
                        f"[열기: Actions › {workflow}]"
                        f"(https://github.com/{owner}/{repo}/actions/workflows/{workflow})"
                    )
                except Exception as exc:  # noqa: BLE001
                    st.exception(exc)

    if st.session_state.get("_merged_yaml"):
        st.code(st.session_state["_merged_yaml"], language="yaml")

    # 보조 탭(선택): LLM / 템플릿
    with st.expander("보조: 한글 → LLM 정리 → YAML", expanded=False):
        g = st.text_area("문법 원문", height=80, key="llm_g")
        s = st.text_area("문장 원문", height=80, key="llm_s")
        p = st.text_area("지문 원문", height=80, key="llm_p")
        if st.button("🧠 LLM 정리", key="llm_run"):
            openai_key = st.secrets.get("OPENAI_API_KEY")
            y = normalize_to_yaml(grammar_text=g or "", sentence_text=s or "",
                                  passage_text=p or "", openai_key=openai_key,
                                  openai_model=st.secrets.get("OPENAI_MODEL", "gpt-4o-mini"))
            st.code(y, language="yaml")
            st.session_state["_merged_yaml"] = y

    with st.expander("보조: 한글 → YAML 템플릿", expanded=False):
        st.write("간단 템플릿 입력은 위 3탭과 동일 흐름으로 병합됩니다.")
# ===== [09] main UI — END =====


if __name__ == "__main__":
    main()
# ===== [01] FILE: src/ui/admin_prompts.py — END =====
