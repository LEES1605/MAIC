# ===== [01] FILE: admin_prompt.py — START =====
# -*- coding: utf-8 -*-
"""
Admin Prompt Editor (Persona + 3 Prompts per Mode)
- Persona: shared across all modes
- Prompts: Grammar / Sentence / Passage (three distinct inputs)
- Actions: Build YAML, Validate, Download, Publish
- NEW: Load Latest (from GitHub Release 'prompts-latest' → prompts.yaml), with auto-load toggle

SSOT: docs/_gpt/ (MASTERPLAN/CONVENTIONS). Publishing pushes artifacts to Release.
"""

from __future__ import annotations

import importlib
import io
from pathlib import Path
from typing import Any, Dict, Tuple, Optional

# --- Streamlit (lazy import) ---
st: Any = importlib.import_module("streamlit")

# --- Optional deps (yaml/jsonschema/requests) ---
try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

try:
    js = importlib.import_module("jsonschema")
except Exception:  # pragma: no cover
    js = None

try:
    req = importlib.import_module("requests")
except Exception:  # pragma: no cover
    req = None

# --- Sidebar helpers (best-effort, non-fatal) ---
_apply_admin_chrome = None
try:
    _sider = importlib.import_module("src.ui.utils.sider")
    _apply_admin_chrome = getattr(_sider, "apply_admin_chrome", None)
except Exception:
    _sider = None  # best-effort only


# ===== schema helpers =====
def _find_schema_path() -> Path:
    here = Path(__file__).resolve()
    candidates = [
        here.parent / "schemas" / "prompts.schema.json",        # repo root layout
        here.parent.parent / "schemas" / "prompts.schema.json", # nested
        Path.cwd() / "schemas" / "prompts.schema.json",         # fallback
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError("Schema not found (schemas/prompts.schema.json)")


def _load_schema() -> Dict[str, Any]:
    import json
    sp = _find_schema_path()
    return json.loads(sp.read_text(encoding="utf-8"))


def _validate_yaml_text(yaml_text: str) -> Tuple[bool, list[str]]:
    msgs: list[str] = []
    if yaml is None:
        return False, ["PyYAML(yaml) not available"]

    try:
        data = yaml.safe_load(yaml_text)
        if not isinstance(data, dict):
            return False, ["<root>: mapping(object) required"]
    except Exception as exc:  # noqa: BLE001
        return False, [f"YAML parse error: {exc}"]

    if js is None:
        return True, ["jsonschema not installed — structural checks skipped"]

    try:
        validator = getattr(js, "Draft202012Validator", None)
        if validator is None:
            return False, ["jsonschema.Draft202012Validator not found"]
        schema = _load_schema()
        errs = sorted(validator(schema).iter_errors(data), key=lambda e: list(e.path))
    except Exception as exc:  # noqa: BLE001
        return False, [f"schema check failed: {exc}"]

    if errs:
        for e in errs:
            loc = "/".join(str(p) for p in e.path) or "<root>"
            msgs.append(f"{loc}: {e.message}")
        return False, msgs
    return True, []


# ===== normalization helpers =====
try:
    from src.ui.assist.prompt_normalizer import (  # type: ignore
        normalize_to_yaml_from_pairs,
    )
except Exception:
    def normalize_to_yaml_from_pairs(  # type: ignore
        *,
        grammar_persona: str,
        grammar_system: str,
        sentence_persona: str,
        sentence_system: str,
        passage_persona: str,
        passage_system: str,
    ) -> str:
        if yaml is None:
            raise RuntimeError("PyYAML not available for fallback builder")
        data: Dict[str, Any] = {
            "modes": {
                "grammar": {"persona": grammar_persona, "system": grammar_system},
                "sentence": {"persona": sentence_persona, "system": sentence_system},
                "passage": {"persona": passage_persona, "system": passage_system},
            }
        }
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


# ===== GitHub publish helpers =====
try:
    from src.ui.admin_prompts import _gh_dispatch_workflow as _gh_dispatch  # type: ignore
except Exception:
    _gh_dispatch = None  # will use local fallback

ELLIPSIS_UC = "\u2026"

def _sanitize_ellipsis(text: str) -> Tuple[str, int]:
    c = text.count(ELLIPSIS_UC)
    return text.replace(ELLIPSIS_UC, "..."), c

def _gh_dispatch_fallback(
    *,
    owner: str,
    repo: str,
    workflow: str,
    ref: str,
    token: str | None,
    yaml_text: str,
) -> None:
    s, n = _sanitize_ellipsis(yaml_text)
    if n:
        st.info(f"U+2026 {n}개를 '...'로 치환했습니다.")
    if req is None:
        raise RuntimeError("requests not available")
    import base64
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


def _publish_yaml_via_github(yaml_text: str) -> None:
    repo_full = st.secrets.get("GITHUB_REPO", "")
    token = st.secrets.get("GITHUB_TOKEN")
    ref = st.secrets.get("GITHUB_BRANCH", "main")
    workflow = st.secrets.get("GITHUB_WORKFLOW", "publish-prompts.yml")

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
        st.info("GITHUB_REPO 시크릿이 비어 있어 출판 기능이 비활성화됩니다.")

    if repo_config_error or not owner or not repo:
        st.warning("출판이 비활성화되었습니다. 시크릿을 설정하거나 형식을 수정하세요.")
        return

    ok, msgs = _validate_yaml_text(yaml_text)
    if not ok:
        st.error("스키마 검증 실패 — 먼저 오류를 해결하세요.")
        if msgs:
            st.write("\n".join(f"- {m}" for m in msgs))
        return

    try:
        if _gh_dispatch is not None:
            _gh_dispatch(owner=owner, repo=repo, workflow=workflow, ref=ref, token=token, yaml_text=yaml_text)
        else:
            _gh_dispatch_fallback(owner=owner, repo=repo, workflow=workflow, ref=ref, token=token, yaml_text=yaml_text)
        st.success("출판 요청 전송 완료 — Actions에서 처리 중입니다.")
        st.markdown(
            f"[열기: Actions › {workflow}](https://github.com/{owner}/{repo}/actions/workflows/{workflow})"
        )
    except Exception as exc:  # noqa: BLE001
        st.exception(exc)


# ===== helpers: Load Latest (Release / Repo / Local) =====
def _split_repo(repo_full: str) -> Tuple[str, str]:
    owner, repo = "", ""
    if repo_full and "/" in repo_full:
        owner, repo = repo_full.split("/", 1)
    return owner, repo


def _http_get_json(url: str, token: Optional[str] = None, timeout: int = 20) -> Dict[str, Any]:
    if req is None:
        raise RuntimeError("requests not available")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = req.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _http_get_text(url: str, token: Optional[str] = None, timeout: int = 20, accept: Optional[str] = None) -> str:
    if req is None:
        raise RuntimeError("requests not available")
    headers = {}
    if accept:
        headers["Accept"] = accept
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = req.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text


def _fetch_release_prompts_yaml(owner: str, repo: str, token: Optional[str]) -> Optional[str]:
    """
    Try: /releases/tags/prompts-latest → /releases/latest
    Then download asset 'prompts.yaml' (case-insensitive).
    """
    try:
        # Prefer tag 'prompts-latest'
        url_tag = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/prompts-latest"
        rel = _http_get_json(url_tag, token=token)
    except Exception:
        # Fallback: latest published release
        url_latest = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        try:
            rel = _http_get_json(url_latest, token=token)
        except Exception:
            return None

    assets = rel.get("assets") or []
    target = None
    for a in assets:
        name = (a.get("name") or "").lower()
        if name in ("prompts.yaml", "prompts.yml"):
            target = a
            break
    if not target:
        return None

    # Prefer browser_download_url; fallback to API assets/{id}
    dl = target.get("browser_download_url")
    if dl:
        try:
            return _http_get_text(dl, token=None, accept="application/octet-stream")
        except Exception:
            pass

    asset_id = target.get("id")
    if asset_id:
        url_asset = f"https://api.github.com/repos/{owner}/{repo}/releases/assets/{asset_id}"
        try:
            return _http_get_text(url_asset, token=token, accept="application/octet-stream")
        except Exception:
            return None
    return None


def _fetch_repo_file(owner: str, repo: str, path: str, ref: str, token: Optional[str]) -> Optional[str]:
    """
    Private repos: use contents API with raw accept header.
    Public repos: this also works. Avoid raw.githubusercontent.com for private.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={ref}"
    try:
        return _http_get_text(url, token=token, accept="application/vnd.github.raw")
    except Exception:
        return None


def _load_yaml_from_local_candidates() -> Optional[str]:
    candidates = [
        Path(__file__).resolve().parent / "docs" / "_gpt" / "prompts.yaml",
        Path(__file__).resolve().parent / "docs" / "_gpt" / "prompts.sample.yaml",
        Path.cwd() / "docs" / "_gpt" / "prompts.yaml",
        Path.cwd() / "docs" / "_gpt" / "prompts.sample.yaml",
    ]
    for p in candidates:
        try:
            if p.exists():
                return p.read_text(encoding="utf-8")
        except Exception:
            continue
    return None


def _extract_fields_from_yaml(ytext: str) -> Tuple[str, str, str, str]:
    """
    Parse YAML to (persona, g_prompt, s_prompt, p_prompt).
    Supports the project's canonical shape:
      modes.grammar.persona/system, modes.sentence.persona/system, modes.passage.persona/system
    With best-effort fallbacks for older shapes.
    """
    persona, g, s, p = "", "", "", ""
    if yaml is None:
        return persona, g, s, p
    try:
        data = yaml.safe_load(ytext) or {}
        modes = data.get("modes") or {}
        def pick(mode: str, *keys: str) -> str:
            m = modes.get(mode) or {}
            for k in keys:
                v = (m.get(k) or "").strip() if isinstance(m, dict) else ""
                if v:
                    return v
            return ""
        # primary fields
        gp = pick("grammar", "persona")
        sp = pick("sentence", "persona")
        pp = pick("passage", "persona")
        persona = gp or sp or pp or (data.get("persona") or "").strip()  # global fallback
        g = pick("grammar", "system", "prompt")
        s = pick("sentence", "system", "prompt")
        p = pick("passage", "system", "prompt")

        # last resort fallbacks (old formats)
        if not g:
            g = (data.get("grammar") or "").strip()
        if not s:
            s = (data.get("sentence") or "").strip()
        if not p:
            p = (data.get("passage") or "").strip()
        return persona, g, s, p
    except Exception:
        return "", "", "", ""


def _apply_yaml_to_fields(ytext: str) -> None:
    persona, g, s, p = _extract_fields_from_yaml(ytext)
    if persona:
        st.session_state["ap_persona"] = persona
    if g:
        st.session_state["ap_prompt_g"] = g
    if s:
        st.session_state["ap_prompt_s"] = s
    if p:
        st.session_state["ap_prompt_p"] = p
    st.session_state["_PROMPTS_YAML"] = ytext


def _load_latest_into_fields(source_hint: str = "release") -> None:
    """
    Load latest prompts.yaml and prefill fields:
    - source_hint = 'release' → release (prompts-latest → prompts.yaml)
    - 'repo' → docs/_gpt/prompts.yaml (contents API)
    - 'local' → local file fallback
    """
    repo_full = st.secrets.get("GITHUB_REPO", "")
    token = st.secrets.get("GITHUB_TOKEN")
    ref = st.secrets.get("GITHUB_BRANCH", "main")
    owner, repo = _split_repo(repo_full)

    ytext: Optional[str] = None

    if source_hint == "release" and owner and repo:
        ytext = _fetch_release_prompts_yaml(owner, repo, token)

    if ytext is None and owner and repo:
        # try repo tree (docs/_gpt/prompts.yaml → prompts.sample.yaml)
        ytext = _fetch_repo_file(owner, repo, "docs/_gpt/prompts.yaml", ref, token) \
            or _fetch_repo_file(owner, repo, "docs/_gpt/prompts.sample.yaml", ref, token)

    if ytext is None:
        # local fallback inside the app filesystem
        ytext = _load_yaml_from_local_candidates()

    if not ytext:
        st.warning("불러올 최신 프롬프트를 찾지 못했습니다. (Release/Repo/Local 모두 실패)")
        return

    ok, msgs = _validate_yaml_text(ytext)
    if not ok:
        st.warning("가져온 YAML이 스키마 검증을 통과하지 못했습니다. (내용은 칸에 주입합니다)")
        if msgs:
            st.write("\n".join(f"- {m}" for m in msgs))
    _apply_yaml_to_fields(ytext)
    st.success("최신 프롬프트를 칸에 주입했습니다.")


# ===== page init =====
def _init_admin_page() -> None:
    st.set_page_config(page_title="Prompts Admin (2-field + 3 prompts)", page_icon="🛠️", layout="wide")
    try:
        if callable(_apply_admin_chrome):
            _apply_admin_chrome(back_page="app.py", icon_only=True)
    except Exception:
        pass


# ===== main UI =====
def main() -> None:
    _init_admin_page()

    st.markdown("### 관리자 프롬프트 편집기 — 페르소나 + 모드별 프롬프트(3)")
    st.caption("SSOT: `docs/_gpt/`의 규약·마스터플랜에 맞춰 편집하세요. (로드/병합/검증/다운로드/출판)")

    # --- Auto-load controls (top) ---
    c0a, c0b, c0c = st.columns([0.32, 0.34, 0.34])
    with c0a:
        auto_load = st.checkbox("로그인 후 진입 시 최신 프리필(릴리스)", value=st.session_state.get("ap_auto_load_enabled", True), key="ap_auto_load_enabled")
    with c0b:
        if st.button("🔄 최신 프롬프트 불러오기(릴리스 우선)", use_container_width=True, key="ap_load_latest"):
            _load_latest_into_fields("release")
    with c0c:
        if st.button("📂 레포에서 불러오기(docs/_gpt)", use_container_width=True, key="ap_load_repo"):
            _load_latest_into_fields("repo")

    # One-shot autoload per session
    if auto_load and not st.session_state.get("_ap_loaded_once"):
        try:
            _load_latest_into_fields("release")
            st.session_state["_ap_loaded_once"] = True
        except Exception as exc:  # noqa: BLE001
            st.info(f"자동 로드 실패 — 수동으로 불러오기를 시도하세요. ({exc})")

    # --- Inputs: Persona + 3 Prompts (Grammar/Sentence/Passage) ---
    persona = st.text_area("① 페르소나(Persona) — 모든 모드에 공통 적용", height=240, key="ap_persona")

    st.markdown("#### ② 모드별 프롬프트(지시/규칙)")
    c1, c2, c3 = st.columns(3)
    with c1:
        g_prompt = st.text_area("문법(Grammar) 프롬프트", height=300, key="ap_prompt_g")
    with c2:
        s_prompt = st.text_area("문장(Sentence) 프롬프트", height=300, key="ap_prompt_s")
    with c3:
        p_prompt = st.text_area("지문(Passage) 프롬프트", height=300, key="ap_prompt_p")

    st.divider()

    # --- Actions: Build YAML / Validate / Download ---
    c_left, c_mid, c_right = st.columns(3)
    with c_left:
        if st.button("🧠 YAML 병합(모드별)", use_container_width=True, key="ap_build_yaml"):
            ytext = normalize_to_yaml_from_pairs(
                grammar_persona=(persona or "").strip(),
                grammar_system=(g_prompt or "").strip(),
                sentence_persona=(persona or "").strip(),
                sentence_system=(s_prompt or "").strip(),
                passage_persona=(persona or "").strip(),
                passage_system=(p_prompt or "").strip(),
            )
            st.session_state["_PROMPTS_YAML"] = ytext
            st.success("YAML 병합 완료 — 아래 미리보기에서 확인하세요.")

    with c_mid:
        if st.button("🔎 스키마 검증", use_container_width=True, key="ap_validate_yaml"):
            ytext = st.session_state.get("_PROMPTS_YAML", "")
            if not ytext:
                st.warning("먼저 ‘YAML 병합(모드별)’을 눌러 YAML을 생성하세요.")
            else:
                ok, msgs = _validate_yaml_text(ytext)
                if ok:
                    if msgs:
                        st.info("검증 통과 (참고):\n- " + "\n- ".join(msgs))
                    else:
                        st.success("검증 통과")
                else:
                    st.error("스키마 검증 실패 — 아래 메시지를 확인해 수정하세요.")
                    if msgs:
                        st.code("\n".join(f"- {m}" for m in msgs), language="text")

    with c_right:
        ytext = st.session_state.get("_PROMPTS_YAML", "")
        disabled = not bool(ytext)
        bio = io.BytesIO((ytext or "").encode("utf-8"))
        st.download_button(
            "📥 YAML 다운로드",
            data=bio,
            file_name="prompts.yaml",
            mime="text/yaml",
            use_container_width=True,
            disabled=disabled,
        )

    # --- Publish ---
    st.markdown("#### ③ 출판(Publish)")
    repo_full = st.secrets.get("GITHUB_REPO", "")
    repo_bad = (not repo_full) or ("/" not in repo_full)
    if repo_bad:
        st.info("출판을 사용하려면 `GITHUB_REPO` 시크릿을 `OWNER/REPO` 형식으로 설정하세요.")
    publish_disabled = (not bool(st.session_state.get("_PROMPTS_YAML"))) or repo_bad

    if st.button(
        "🚀 출판(Publish)",
        type="primary",
        use_container_width=True,
        key="ap_publish_yaml",
        disabled=publish_disabled,
        help="먼저 YAML을 생성하고(GITHUB_REPO=OWNER/REPO) 시크릿이 준비되어야 합니다." if publish_disabled else None,
    ):
        ytext = st.session_state.get("_PROMPTS_YAML", "")
        if not ytext:
            st.warning("YAML이 없습니다. ‘🧠 YAML 병합(모드별)’을 먼저 수행하세요.")
        else:
            _publish_yaml_via_github(yaml_text=ytext)

    # --- Preview ---
    ytext = st.session_state.get("_PROMPTS_YAML", "")
    if ytext:
        st.markdown("#### YAML 미리보기")
        st.code(ytext, language="yaml")
    else:
        st.info("아직 생성된 YAML이 없습니다. 위의 ‘🧠 YAML 병합(모드별)’을 눌러 주세요.")


if __name__ == "__main__":
    main()
# ===== [01] FILE: admin_prompt.py — END =====
