# ===== [01] FILE: src/ui/admin_prompt.py — START =====
# -*- coding: utf-8 -*-
"""
관리자 프롬프트 편집기 — 페르소나 + 모드별 프롬프트(문법/문장/지문)
- 요구사항:
  (1) 릴리스에서 최신 prompts.yaml을 불러오면 3개 모드 칸까지 정확히 채워질 것
  (2) 편집 → YAML 미리보기 → 검증 → 출판(워크플로 dispatch)
  (3) GITHUB_REPO 시크릿이 비어도 '편집'은 가능하고, 출판만 비활성화

SSOT/정책:
- 문서 단일 진실 소스는 docs/_gpt/ (Workspace Pointer 참조).
- 헤더/상태 표시는 MASTERPLAN vNext 합의안(H1)에 따름.
"""
from __future__ import annotations

# ================================ [02] imports =======================================
import base64
import importlib
import io
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

# Third‑party
try:
    import yaml  # PyYAML
except Exception:  # pragma: no cover
    yaml = None  # type: ignore
try:
    js = importlib.import_module("jsonschema")
except Exception:  # pragma: no cover
    js = None
try:
    req = importlib.import_module("requests")
except Exception:  # pragma: no cover
    req = None

# Streamlit (lazy import)
st: Any = importlib.import_module("streamlit")

# Admin sider helpers (best‑effort, non‑fatal)
try:
    _sider = importlib.import_module("src.ui.utils.sider")
    ensure_admin_sidebar = getattr(_sider, "ensure_admin_sidebar")
    render_minimal_admin_sidebar = getattr(_sider, "render_minimal_admin_sidebar")
    show_sidebar = getattr(_sider, "show_sidebar")
    apply_admin_chrome = getattr(_sider, "apply_admin_chrome")
except Exception:
    def ensure_admin_sidebar() -> None: ...
    def render_minimal_admin_sidebar(*_: Any, **__: Any) -> None: ...
    def show_sidebar() -> None: ...
    def apply_admin_chrome(*_: Any, **__: Any) -> None: ...

# (옵션) LLM 변환기
try:
    normalize_to_yaml = importlib.import_module(
        "src.ui.assist.prompt_normalizer"
    ).normalize_to_yaml
except Exception:
    normalize_to_yaml = None  # type: ignore

# ================================ [03] schema helpers ================================
ELLIPSIS_UC = "\u2026"

def _sanitize_ellipsis(text: str) -> Tuple[str, int]:
    c = text.count(ELLIPSIS_UC)
    return text.replace(ELLIPSIS_UC, "..."), c


def _find_schema_path() -> Optional[Path]:
    here = Path(__file__).resolve()
    for p in (
        here.parent / "schemas" / "prompts.schema.json",
        here.parent.parent / "schemas" / "prompts.schema.json",
        Path.cwd() / "schemas" / "prompts.schema.json",
    ):
        if p.exists():
            return p
    return None


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
        sp = _find_schema_path()
        if sp is None:
            return True, ["schema file not found — structural checks skipped"]
        import json
        schema = json.loads(sp.read_text(encoding="utf-8"))
        errs = sorted(validator(schema).iter_errors(data), key=lambda e: list(e.path))
    except Exception as exc:  # noqa: BLE001
        return False, [f"schema check failed: {exc}"]

    if errs:
        for e in errs:
            loc = "/".join(str(p) for p in e.path) or "<root>"
            msgs.append(f"{loc}: {e.message}")
        return False, msgs
    return True, []

# ================================ [04] tolerant parser ===============================
# 모드/필드 별칭(국문/영문 혼용 지원)
_MODE_ALIASES = {
    "grammar": {"grammar", "문법", "pt", "피티", "피티쌤"},
    "sentence": {"sentence", "문장", "mn", "미나", "미나쌤"},
    "passage": {"passage", "지문", "reading", "독해"},
}
_FIELD_CANDIDATES = (
    "system","prompt","instruction","instructions","rules","guidelines",
    "text","content","template","value",
    # 한국어 동의어
    "지시","지침","규칙","프롬프트","템플릿","설명","본문",
    # 리스트형 후보
    "lines","bullets","items",
)

def _canon_mode_key(k: str) -> Optional[str]:
    k = (k or "").strip().lower()
    for canon, aliases in _MODE_ALIASES.items():
        if k in aliases or k == canon:
            return canon
    return None

def _norm_text(x: Any) -> str:
    if x is None:
        return ""
    return str(x).replace("\r\n", "\n").strip()

def _join_list(val: Any) -> str:
    if isinstance(val, list):
        parts = [_norm_text(x) for x in val if isinstance(x, str)]
        if parts:
            return "\n".join(parts)
    return ""

def _extract_text_any(val: Any) -> str:
    """dict/list/str 어디서든 '지시문' 텍스트를 최대한 뽑는다(관용)."""
    if isinstance(val, str):
        return _norm_text(val)
    if isinstance(val, dict):
        for k in _FIELD_CANDIDATES:
            if k in val:
                s = _norm_text(val.get(k))
                if s:
                    return s
        s = _join_list(val.get("lines") or val.get("bullets") or val.get("items"))
        if s:
            return s
        msgs = val.get("messages") or val.get("chat")
        if isinstance(msgs, list):
            sys_msgs = [m for m in msgs if (m.get("role") or "").lower() == "system"]
            if sys_msgs and sys_msgs[0].get("content"):
                return _norm_text(sys_msgs[0]["content"])
            return _norm_text("\n".join(_norm_text(m.get("content")) for m in msgs if m.get("content")))
        return ""
    if isinstance(val, list):
        return _join_list(val)
    return ""

def _parse_modes_like(data: dict) -> Dict[str, str]:
    """
    다양한 스키마를 관용적으로 파싱하여 grammar/sentence/passage 3개를 반환.
    지원 형태:
      - data["modes"]가 리스트: [{key|name, prompt|...}] 또는 [{문법:{...}}]
      - data["modes"]가 매핑: {grammar|문법: "..." 또는 {prompt|...}}
      - data["prompts"]가 유사 구조일 때도 동일 처리
    """
    out = {"grammar": "", "sentence": "", "passage": ""}

    def _apply_mapping(m: dict) -> None:
        for raw_k, v in m.items():
            ck = _canon_mode_key(str(raw_k))
            if not ck or ck not in out:
                continue
            out[ck] = _extract_text_any(v)

    modes = data.get("modes")
    if isinstance(modes, dict):
        _apply_mapping(modes)
    elif isinstance(modes, list):
        for item in modes:
            if not isinstance(item, dict):
                continue
            raw_k = item.get("key") or item.get("name") or item.get("mode") or item.get("id")
            if raw_k:
                ck = _canon_mode_key(str(raw_k))
                if ck:
                    out[ck] = _extract_text_any(item)
                    continue
            for k2, v2 in item.items():
                ck = _canon_mode_key(str(k2))
                if ck:
                    out[ck] = _extract_text_any(v2)

    prompts = data.get("prompts")
    if isinstance(prompts, dict):
        _apply_mapping(prompts)

    # 루트 대체 키
    out["grammar"] = out["grammar"] or _norm_text(data.get("grammar"))
    out["sentence"] = out["sentence"] or _norm_text(data.get("sentence"))
    out["passage"] = out["passage"] or _norm_text(data.get("passage"))

    # 상호 보정(한쪽만 있을 때)
    if not out["sentence"] and out["passage"]:
        out["sentence"] = out["passage"]
    if not out["passage"] and out["sentence"]:
        out["passage"] = out["sentence"]

    return out

def _extract_fields_from_yaml(ytext: str) -> Tuple[str, str, str, str]:
    """
    Parse YAML → (persona, grammar, sentence, passage).
    - modes가 '매핑'이든 '리스트'든 흡수
    - 모드 키는 국문/영문/별칭 허용
    - 값 필드는 system/prompt/instructions/지침/규칙/... 모두 허용
    - fallback: root-level persona / grammar|sentence|passage
    """
    if yaml is None:
        return "", "", "", ""
    try:
        data = yaml.safe_load(ytext) or {}
        if not isinstance(data, dict):
            return "", "", "", ""
        modes = _parse_modes_like(data)
        persona = _norm_text(
            data.get("persona")
            or (data.get("modes") or {}).get("persona", "")  # 일부 구형
        )
        # 모드별 persona가 있을 경우 후보로 사용
        if not persona and isinstance(data.get("modes"), dict):
            for v in (data.get("modes") or {}).values():
                if isinstance(v, dict) and v.get("persona"):
                    persona = _norm_text(v.get("persona"))
                    break
        return persona, modes["grammar"], modes["sentence"], modes["passage"]
    except Exception:
        return "", "", "", ""

# ================================ [05] GitHub helpers =================================
def _split_repo(repo_full: str) -> Tuple[str, str]:
    if repo_full and "/" in repo_full:
        owner, repo = repo_full.split("/", 1)
        return owner, repo
    return "", ""

def _http_get_json(url: str, token: Optional[str] = None, timeout: int = 20) -> Any:
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

def _iter_release_candidates(owner: str, repo: str, token: Optional[str], *, max_pages: int = 5) -> Iterator[Dict[str, Any]]:
    """Yield unique release JSONs (prompts-latest → latest → paginated)."""
    seen: set[str] = set()

    def _remember(rel: Dict[str, Any], hint: str) -> bool:
        key = str(rel.get("id") or rel.get("node_id") or rel.get("tag_name") or hint)
        if key in seen:
            return False
        seen.add(key)
        return True

    special = [
        ("prompts-latest", f"https://api.github.com/repos/{owner}/{repo}/releases/tags/prompts-latest"),
        ("latest",        f"https://api.github.com/repos/{owner}/{repo}/releases/latest"),
    ]
    for hint, url in special:
        try:
            rel = _http_get_json(url, token=token)
        except Exception:
            continue
        if isinstance(rel, dict) and _remember(rel, hint):
            yield rel

    for page in range(1, max_pages + 1):
        url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=20&page={page}"
        try:
            rels = _http_get_json(url, token=token)
        except Exception:
            break
        if not isinstance(rels, list) or not rels:
            break
        for idx, rel in enumerate(rels):
            if isinstance(rel, dict) and _remember(rel, f"page{page}-{idx}"):
                yield rel
        if len(rels) < 20:
            break

def _pick_release_asset(rel: Dict[str, Any], names: tuple[str, ...]) -> Optional[Dict[str, Any]]:
    assets = rel.get("assets") or []
    for a in assets:
        name = (a.get("name") or "").lower()
        if name in names:
            return a
    return None

def _download_release_asset(asset: Dict[str, Any], *, owner: str, repo: str, token: Optional[str]) -> Optional[str]:
    dl = asset.get("browser_download_url")
    if dl:
        try:
            return _http_get_text(dl, token=None, accept="application/octet-stream")
        except Exception:
            pass
    asset_id = asset.get("id")
    if asset_id:
        try:
            url_asset = f"https://api.github.com/repos/{owner}/{repo}/releases/assets/{asset_id}"
            return _http_get_text(url_asset, token=token, accept="application/octet-stream")
        except Exception:
            pass
    api_url = asset.get("url")
    if api_url:
        try:
            return _http_get_text(api_url, token=token, accept="application/octet-stream")
        except Exception:
            pass
    return None

def _fetch_release_prompts_yaml(owner: str, repo: str, token: Optional[str]) -> Optional[str]:
    """최근 릴리스들에서 prompts.yaml(.yml)을 찾아 텍스트를 반환."""
    for rel in _iter_release_candidates(owner, repo, token):
        asset = _pick_release_asset(rel, ("prompts.yaml", "prompts.yml"))
        if not asset:
            continue
        ytext = _download_release_asset(asset, owner=owner, repo=repo, token=token)
        if ytext:
            return ytext
    return None

def _fetch_repo_prompts_yaml(owner: str, repo: str, ref: str, token: Optional[str]) -> Optional[str]:
    """레포 SSOT 경로에서 prompts.yaml 폴백 로드."""
    # SSOT: docs/_gpt/ — Workspace Pointer 정책
    for path in ("docs/_gpt/prompts.yaml", "docs/_gpt/prompts.yml"):
        try:
            u = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={ref}"
            return _http_get_text(u, token=token, accept="application/vnd.github.raw")
        except Exception:
            continue
    return None

# ================================ [06] UI helpers =====================================
def _init_admin_page() -> None:
    st.set_page_config(page_title="Prompts Admin (Persona+3)", page_icon="🛠️", layout="wide")
    try:
        apply_admin_chrome(back_page="app.py", icon_only=True)
    except Exception:
        pass
    ensure_admin_sidebar()
    try:
        show_sidebar()
    except Exception:
        pass
    render_minimal_admin_sidebar(back_page="app.py")

def _publish_via_github(yaml_text: str) -> None:
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

    if req is None:
        st.error("requests 모듈이 필요합니다.")
        return

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
    st.success("출판 요청 전송 완료 — Actions에서 처리 중입니다.")
    st.markdown(f"[열기: Actions › {workflow}](https://github.com/{owner}/{repo}/actions/workflows/{workflow})")

# ================================ [07] loaders (release/repo/local) ===================
def _apply_yaml_to_fields(ytext: str) -> None:
    persona, g, s, p = _extract_fields_from_yaml(ytext)
    if persona:
        st.session_state["persona_text"] = persona
    if g:
        st.session_state["grammar_prompt"] = g
    if s:
        st.session_state["sentence_prompt"] = s
    if p:
        st.session_state["passage_prompt"] = p
    st.session_state["_PROMPTS_YAML_RAW"] = ytext

def _load_latest(source_hint: str = "release") -> None:
    repo_full = st.secrets.get("GITHUB_REPO", "")
    token = st.secrets.get("GITHUB_TOKEN")
    ref = st.secrets.get("GITHUB_BRANCH", "main")
    owner, repo = _split_repo(repo_full)

    ytext: Optional[str] = None
    if source_hint == "release" and owner and repo:
        ytext = _fetch_release_prompts_yaml(owner, repo, token)

    if ytext is None and owner and repo:
        ytext = _fetch_repo_prompts_yaml(owner, repo, ref, token)

    if ytext is None:
        # 로컬 폴백(개발 환경)
        for p in (
            Path.cwd() / "docs" / "_gpt" / "prompts.yaml",
            Path.cwd() / "docs" / "_gpt" / "prompts.sample.yaml",
        ):
            if p.exists():
                ytext = p.read_text(encoding="utf-8")
                break

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

# ================================ [08] Health check ===================================
def _probe_app_url(url: str, timeout: int = 8) -> Tuple[bool, str, Optional[int]]:
    if req is None:
        return False, "requests not available", None
    try:
        t0 = time.perf_counter()
        r = req.get(url, headers={"User-Agent": "MAIC-HealthCheck/1.0"}, timeout=timeout, allow_redirects=True)
        ms = int((time.perf_counter() - t0) * 1000)
        return True, f"HTTP {r.status_code}, {ms} ms", r.status_code
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}", None

def _describe_release(owner: str, repo: str, token: Optional[str]) -> Tuple[bool, str]:
    """
    릴리스에 prompts.yaml이 있는지 여부와 간단 메타 설명을 반환.
    """
    fallback_info: Optional[str] = None
    for rel in _iter_release_candidates(owner, repo, token):
        tag = rel.get("tag_name") or rel.get("name") or "latest"
        published = rel.get("published_at") or rel.get("created_at")
        try:
            ts = (
                datetime.fromisoformat(published.replace("Z", "+00:00")).astimezone(timezone.utc)
                if published
                else None
            )
            when = ts.strftime("%Y-%m-%d %H:%M UTC") if ts else "unknown"
        except Exception:
            when = str(published or "unknown")

        assets = rel.get("assets") or []
        info = f"tag={tag}, published={when}, assets={len(assets)}"
        asset = _pick_release_asset(rel, ("prompts.yaml", "prompts.yml"))
        if asset:
            size = asset.get("size")
            if size is not None:
                info += f", prompts.yaml={size}B"
            return True, info
        fallback_info = fallback_info or info
    return False, fallback_info or "Release not found"

# ================================ [09] main UI ========================================
def main() -> None:
    _init_admin_page()

    st.markdown("### 관리자 프롬프트 편집기 — 페르소나 + 모드별 프롬프트(3)")
    st.caption("SSOT: `docs/_gpt/` 규약·마스터플랜 기준으로 편집/출판합니다.")

    # --- 0) 상태 점검 -----------------------------------------------------------------
    st.markdown("#### 🩺 상태 점검")
    default_app_url = st.secrets.get("APP_URL") or "https://fkygwdujjljdz9z9pugasr.streamlit.app"
    col_h1, col_h2, col_h3 = st.columns([0.5, 0.25, 0.25])
    with col_h1:
        app_url = st.text_input("앱 주소(.streamlit.app)", value=default_app_url, key="ap_health_app_url")
    with col_h2:
        run_health = st.button("상태 점검 실행", use_container_width=True, key="ap_health_run")
    with col_h3:
        st.link_button("앱 열기", url=app_url, use_container_width=True)

    repo_full = st.secrets.get("GITHUB_REPO", "")
    owner, repo = _split_repo(repo_full)
    token = st.secrets.get("GITHUB_TOKEN")
    ref = st.secrets.get("GITHUB_BRANCH", "main")
    workflow = st.secrets.get("GITHUB_WORKFLOW", "publish-prompts.yml")

    if run_health:
        ok_app, app_info, status = _probe_app_url(app_url)
        if ok_app and status and status < 500:
            st.success(f"앱 URL OK — {app_info}")
        else:
            st.error(f"앱 URL 점검 실패 — {app_info}")

        if owner and repo:
            has_prompts, rel_info = _describe_release(owner, repo, token)
            if has_prompts:
                st.success(f"릴리스 OK — {rel_info}")
            else:
                st.warning(f"릴리스는 있으나 prompts.yaml 미발견 — {rel_info}")
            st.markdown(f"- 릴리스 보기: https://github.com/{owner}/{repo}/releases")
        else:
            st.info("GITHUB_REPO가 비어있거나 형식이 잘못되었습니다. (예: OWNER/REPO)")

        if not (owner and repo):
            st.error("시크릿 점검: GITHUB_REPO 형식 오류 또는 미설정")
        else:
            st.success(f"시크릿 점검: GITHUB_REPO OK — `{owner}/{repo}`")

    st.divider()

    # --- 1) 자동/수동 불러오기 ---------------------------------------------------------
    c0a, c0b, c0c = st.columns([0.32, 0.34, 0.34])
    with c0a:
        auto_load = st.checkbox(
            "로그인 후 진입 시 최신 프리필(릴리스)",
            value=st.session_state.get("ap_auto_load_enabled", True),
            key="ap_auto_load_enabled",
        )
    with c0b:
        if st.button("🔄 최신 프롬프트 불러오기(릴리스 우선)", use_container_width=True, key="ap_load_latest"):
            _load_latest("release")
    with c0c:
        if st.button("📂 레포에서 불러오기(docs/_gpt)", use_container_width=True, key="ap_load_repo"):
            _load_latest("repo")

    if auto_load and not st.session_state.get("_ap_loaded_once"):
        try:
            _load_latest("release")
            st.session_state["_ap_loaded_once"] = True
        except Exception as exc:  # noqa: BLE001
            st.info(f"자동 로드 실패 — 수동으로 불러오기를 시도하세요. ({exc})")

    # --- 2) 입력칸 (페르소나 + 3모드) ---------------------------------------------------
    persona = st.text_area("① 페르소나(Persona) — 모든 모드에 공통 적용", height=240, key="persona_text")

    st.markdown("#### ② 모드별 프롬프트(지시/규칙)")
    c1, c2, c3 = st.columns(3)
    with c1:
        g_prompt = st.text_area("문법(Grammar) 프롬프트", height=300, key="grammar_prompt")
    with c2:
        s_prompt = st.text_area("문장(Sentence) 프롬프트", height=300, key="sentence_prompt")
    with c3:
        p_prompt = st.text_area("지문(Passage) 프롬프트", height=300, key="passage_prompt")

    st.divider()

    # --- 3) YAML 병합/검증/다운로드 ------------------------------------------------------
    c_left, c_mid, c_right = st.columns(3)
    with c_left:
        if st.button("🧠 YAML 병합(모드별)", use_container_width=True, key="ap_build_yaml"):
            if normalize_to_yaml:
                ytext = normalize_to_yaml(
                    grammar_text=g_prompt or "",
                    sentence_text=s_prompt or "",
                    passage_text=p_prompt or "",
                    openai_key=st.secrets.get("OPENAI_API_KEY"),
                    openai_model=st.secrets.get("OPENAI_MODEL", "gpt-4o-mini"),
                )
            else:
                # 가장 간결한 스냅샷 포맷
                doc = {
                    "version": "auto",
                    "persona": persona or "",
                    "modes": [
                        {"key": "grammar", "prompt": g_prompt or ""},
                        {"key": "sentence", "prompt": s_prompt or ""},
                        {"key": "passage", "prompt": p_prompt or ""},
                    ],
                }
                ytext = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False) if yaml else ""
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
        st.download_button(
            "📥 YAML 다운로드",
            data=io.BytesIO((ytext or "").encode("utf-8")),
            file_name="prompts.yaml",
            mime="text/yaml",
            use_container_width=True,
            disabled=not bool(ytext),
        )

    # --- 4) 출판(Publish) --------------------------------------------------------------
    st.markdown("#### ③ 출판(Publish)")
    repo_bad = (not repo_full) or ("/" not in repo_full)
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
            _publish_via_github(yaml_text=ytext)

    # --- 5) 미리보기 -------------------------------------------------------------------
    ytext = st.session_state.get("_PROMPTS_YAML", "")
    if ytext:
        st.markdown("#### YAML 미리보기")
        st.code(ytext, language="yaml")
    else:
        st.info("아직 생성된 YAML이 없습니다. 위의 ‘🧠 YAML 병합(모드별)’을 눌러 주세요.")


if __name__ == "__main__":
    main()
# ===== [01] FILE: src/ui/admin_prompt.py — END =====
