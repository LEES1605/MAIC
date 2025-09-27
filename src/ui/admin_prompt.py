# [AP-KANON-VERT-PUBLISH-FIX] START: src/ui/admin_prompt.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import base64
import json
import yaml
import requests as req
import streamlit as st

# ✅ 사이드바(SSOT)
try:
    from .utils.sider import render_sidebar
except Exception:
    from src.ui.utils.sider import render_sidebar  # fallback

# ✅ persist 경로(로컬 저장 폴백)
try:
    from src.core.persist import effective_persist_dir
except Exception:
    effective_persist_dir = lambda: Path.home() / ".maic" / "persist"  # type: ignore

# ---- UI Widget Keys (SSOT) ---------------------------------------------------
K_PERSONA  = "persona_text"
K_GRAMMAR  = "grammar_prompt"
K_SENTENCE = "sentence_prompt"
K_PASSAGE  = "passage_prompt"

# ---- canon helpers -----------------------------------------------------------
def _norm_token(x: Any) -> str:
    s = str(x or "").strip().lower()
    return "".join(ch for ch in s if ch.isalnum())

def _coerce_yaml_to_text(v: Any) -> str:
    """
    dict/list도 보기 좋게 문자열화.
    ⚠️ dict일 때는 'prompt'/'text'를 우선, 'full'/'system'은 최후 폴백.
    """
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        for k in ("prompt", "text"):
            s = v.get(k)
            if isinstance(s, str) and s.strip():
                return s
        for k in ("full", "system", "value", "content"):
            s = v.get(k)
            if isinstance(s, str) and s.strip():
                return s
        return json.dumps(v, ensure_ascii=False, indent=2)
    if isinstance(v, (list, tuple)):
        return "\n".join(str(x) for x in v)
    return str(v)

def _canon_via_core_modes(label: str) -> Optional[str]:
    """가능하면 core.modes의 정규화 유틸을 우선 사용."""
    try:
        import src.core.modes as _m
    except Exception:
        return None
    for cand in ("canon_mode", "canon_key", "normalize_mode", "normalize_key", "find_mode_by_label"):
        fn = getattr(_m, cand, None)
        if not callable(fn):
            continue
        try:
            res = fn(label)
        except Exception:
            continue
        if isinstance(res, str):
            s = res.strip().lower()
            if s in ("grammar", "sentence", "passage"):
                return s
            if s in ("문법", "문장", "지문"):
                return {"문법": "grammar", "문장": "sentence", "지문": "passage"}[s]
        key = getattr(res, "key", None)
        if isinstance(key, str) and key in ("grammar", "sentence", "passage"):
            return key
    return None

_SYNONYMS = {
    "grammar": {"grammar", "pt", "문법", "문법설명", "문법해설", "문법규칙", "품사", "품사판별", "문장성분", "문법검사", "문법풀이", "문법 문제"},
    "sentence": {"sentence", "sent", "문장", "문장분석", "문장해석", "문장구조", "문장구조분석", "문장성분분석", "문장완성", "문장구조해석", "문장구조파악"},
    "passage": {"passage", "para", "지문", "지문분석", "독해", "독해지문", "독해분석", "지문해석", "독해 문제", "장문", "장문독해"},
}
_SUBSTR_HINTS: List[Tuple[str, Tuple[str, ...]]] = [
    ("grammar", ("문법", "품사", "성분")),
    ("sentence", ("문장", "구조", "성분", "완성")),
    ("passage", ("지문", "독해", "장문")),
]

def _canon_mode_key(label_or_key: Any) -> str:
    """한국어/영문/약어 라벨을 표준 키('grammar'|'sentence'|'passage')로 정규화."""
    s = str(label_or_key or "").strip()
    if not s:
        return ""
    via = _canon_via_core_modes(s)
    if via:
        return via
    t = _norm_token(s)
    for key, names in _SYNONYMS.items():
        if any(_norm_token(n) == t for n in names):
            return key
    low = s.lower()
    for key, hints in _SUBSTR_HINTS:
        if any(h in low for h in hints):
            return key
    if t in ("pt", "mn", "mina"):
        return "sentence" if t != "pt" else "grammar"
    return ""

# ---- file resolve ------------------------------------------------------------
def _resolve_release_prompts_file() -> Path | None:
    """release/assets → release → ./assets → ./ 순으로 prompts.yaml 탐색."""
    base = Path(st.session_state.get("_release_dir", "release")).resolve()
    for p in [base / "assets" / "prompts.yaml",
              base / "prompts.yaml",
              Path("assets/prompts.yaml").resolve(),
              Path("prompts.yaml").resolve()]:
        try:
            if p.exists() and p.is_file():
                return p
        except Exception:
            continue
    return None

# ---- persona-safe helpers / robust extractor ---------------------------------
def _strip_persona_prefix(text: str, persona: str) -> str:
    """'full'(=페르소나+지시문)에서 페르소나가 앞부분에 붙은 경우만 안전 제거."""
    if not text or not persona:
        return text
    t = text.lstrip()
    p = persona.strip()
    if not p:
        return text
    if t.startswith(p):
        return t[len(p):].lstrip(" \r\n-*")
    head = p[:64]
    if head and head in t[:512]:
        idx = t.find(head)
        if 0 <= idx <= 8:
            return t[idx + len(head):].lstrip(" \r\n-*")
    return text

def _extract_prompts(doc: Dict[str, Any]) -> Dict[str, str]:
    """
    다양한 YAML 스키마를 견고하게 수용해 UI 키로 매핑.
    - Top-level 한/영 라벨 → 정규화
    - Nested: { mn:{ sentence, passage } }, { pt:{ grammar/prompt/text/... } }
    - modes: dict/list/한글키
    - 'full'만 있는 경우 페르소나 prefix-strip
    """
    out = {K_PERSONA: "", K_GRAMMAR: "", K_SENTENCE: "", K_PASSAGE: ""}

    # 0) 페르소나 1차 수집
    def _maybe_persona(k: Any, v: Any) -> bool:
        kk = str(k or "").strip().lower()
        if kk in {"persona", "common", "profile", "system", "페르소나", "공통", "프로필"}:
            out[K_PERSONA] = _coerce_yaml_to_text(v)
            return True
        return False

    for k, v in (doc or {}).items():
        if _maybe_persona(k, v):
            continue

    # pt/mn 내부 system도 전역 페르소나 후보로 흡수(비어 있을 때만)
    for nested_key in ("pt", "mn", "mina"):
        nv = doc.get(nested_key)
        if isinstance(nv, dict) and not out[K_PERSONA]:
            sys_txt = nv.get("system")
            if isinstance(sys_txt, str) and sys_txt.strip():
                out[K_PERSONA] = sys_txt

    persona_hint = out[K_PERSONA]

    def _assign(canon: str, payload: Any) -> None:
        if not canon:
            return
        raw = payload
        txt = _coerce_yaml_to_text(raw)
        # dict에서 prompt/text가 없어 full/system을 쓰게 된 경우 → 페르소나 제거 시도
        if isinstance(raw, dict):
            has_direct = any(isinstance(raw.get(k), str) and raw.get(k).strip() for k in ("prompt", "text"))
            if not has_direct:
                txt = _strip_persona_prefix(txt, persona_hint)
        if not txt:
            return
        if canon == "grammar":
            out[K_GRAMMAR] = txt
        elif canon == "sentence":
            out[K_SENTENCE] = txt
        elif canon == "passage":
            out[K_PASSAGE] = txt

    # 1) 얕은 스캔(라벨 정규화)
    for k, v in (doc or {}).items():
        if _maybe_persona(k, v):
            continue
        _assign(_canon_mode_key(k), v)

    # 2) mn/pt 보정
    mn = doc.get("mn") or doc.get("mina")
    if isinstance(mn, dict):
        for nk, nv in mn.items():
            _assign(_canon_mode_key(nk), nv)

    pt = doc.get("pt") if isinstance(doc.get("pt"), dict) else None
    if isinstance(pt, dict):
        if not out[K_GRAMMAR]:
            for k in ("grammar", "prompt", "text", "full"):
                if k in pt:
                    _assign("grammar", pt[k])
                    break
        # pt.system은 페르소나 후보로만 사용

    # 3) modes 섹션: dict/list/한글키
    for key in ("modes", "모드", "mode_prompts", "modeprompts", "prompts_by_mode"):
        sect = doc.get(key)
        if isinstance(sect, dict):
            for mk, mv in sect.items():
                _assign(_canon_mode_key(mk), mv)
        elif isinstance(sect, list):
            for e in sect:
                if not isinstance(e, dict):
                    continue
                label = e.get("key") or e.get("label") or e.get("name") or e.get("라벨")
                canon = _canon_mode_key(label)
                payload = e  # prompt/text가 없으면 full일 수 있으므로 e 그대로 넘겨 strip 처리
                if canon:
                    _assign(canon, payload)

    # 4) 제한 재귀(≤3)
    def _walk(node: Any, depth: int = 0) -> None:
        if depth >= 3:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                if _maybe_persona(k, v):
                    continue
                canon = _canon_mode_key(k)
                if canon:
                    _assign(canon, v)
                _walk(v, depth + 1)
        elif isinstance(node, list):
            for it in node:
                _walk(it, depth + 1)

    _walk(doc)
    return out

def _load_prompts_from_release() -> tuple[Dict[str, str], Path]:
    p = _resolve_release_prompts_file()
    if not p:
        raise FileNotFoundError("prompts.yaml을 release/assets 또는 프로젝트 루트에서 찾지 못했습니다.")
    with p.open("r", encoding="utf-8") as f:
        y = yaml.safe_load(f) or {}
    return _extract_prompts(y), p

# ---- prefill handshake -------------------------------------------------------
def _apply_pending_prefill() -> None:
    ss = st.session_state
    data = ss.pop("_PREFILL_PROMPTS", None)
    if isinstance(data, dict):
        ss[K_PERSONA]  = data.get(K_PERSONA,  "")
        ss[K_GRAMMAR]  = data.get(K_GRAMMAR,  "")
        ss[K_SENTENCE] = data.get(K_SENTENCE, "")
        ss[K_PASSAGE]  = data.get(K_PASSAGE,  "")

# ---- yaml build/validate/save ------------------------------------------------
def _build_yaml_from_fields() -> str:
    doc = {
        "version": "auto",
        "persona": st.session_state.get(K_PERSONA, "") or "",
        "modes": [
            {"key": "grammar",  "prompt": st.session_state.get(K_GRAMMAR,  "") or ""},
            {"key": "sentence", "prompt": st.session_state.get(K_SENTENCE, "") or ""},
            {"key": "passage",  "prompt": st.session_state.get(K_PASSAGE,  "") or ""},
        ],
    }
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)

def _validate_yaml_text(text: str) -> tuple[bool, List[str]]:
    msgs: List[str] = []
    try:
        y = yaml.safe_load(text) or {}
    except Exception as e:
        return False, [f"YAML 파싱 실패: {e}"]
    d = json.loads(json.dumps(y))  # normalize
    ok_modes = isinstance(d.get("modes"), list) and len(d["modes"]) > 0
    has_any = any(k in d for k in ("grammar", "sentence", "passage"))
    if not (ok_modes or has_any):
        msgs.append("modes 리스트 또는 grammar/sentence/passage 중 1개 이상이 필요합니다.")
    return (len(msgs) == 0), msgs

def _save_yaml_local(yaml_text: str) -> Path:
    root = Path(effective_persist_dir()).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    p = root / "prompts.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    return p

# ---- GitHub workflow helpers (inputs 자동탐지 + 폴백) ------------------------
def _gh_headers(token: Optional[str]) -> Dict[str, str]:
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h

def _gh_fetch_workflow_yaml(*, owner: str, repo: str, workflow: str, ref: str, token: Optional[str]) -> Optional[str]:
    """
    1) contents API로 경로 추정(.github/workflows/<workflow>)
    2) 실패하면 actions/workflows API로 path 얻은 뒤 다시 contents 호출
    """
    headers = _gh_headers(token)
    # 시도 1: 파일명으로 바로 contents
    paths = [f".github/workflows/{workflow}"]
    # 시도 2: actions/workflows에서 path 알아내기
    try:
        r = req.get(f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}",
                    headers=headers, timeout=10)
        if r.ok:
            wf = r.json()
            path = wf.get("path")
            if isinstance(path, str) and path:
                if path not in paths:
                    paths.append(path)
    except Exception:
        pass

    for path in paths:
        try:
            url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
            if ref:
                url += f"?ref={ref}"
            r2 = req.get(url, headers=headers, timeout=10)
            if not r2.ok:
                continue
            js = r2.json()
            content = js.get("content")
            enc = js.get("encoding")
            if isinstance(content, str) and enc == "base64":
                return base64.b64decode(content.encode("utf-8")).decode("utf-8", "ignore")
        except Exception:
            continue
    return None

def _discover_workflow_inputs_from_yaml(yaml_text: str) -> Dict[str, Dict[str, Any]]:
    """
    on: { workflow_dispatch: { inputs: {...} } } 구조에서 inputs를 추출.
    dict/list 변형도 완화 처리.
    """
    try:
        y = yaml.safe_load(yaml_text) or {}
    except Exception:
        return {}
    on = y.get("on") or y.get(True) or {}
    inputs: Dict[str, Dict[str, Any]] = {}

    if isinstance(on, dict):
        wd = on.get("workflow_dispatch")
        if wd is None:
            # 'workflow_dispatch'만 키로 있는 경우도 있음 (입력 없음)
            return {}
        if isinstance(wd, dict):
            ins = wd.get("inputs") or {}
            if isinstance(ins, dict):
                for k, spec in ins.items():
                    if isinstance(k, str) and isinstance(spec, dict):
                        inputs[k] = spec
    elif isinstance(on, list):
        # ['workflow_dispatch', ...] 형태면 입력 없음
        if "workflow_dispatch" in on:
            return {}
    return inputs

def _discover_workflow_inputs(owner: str, repo: str, workflow: str, ref: str, token: Optional[str]) -> Dict[str, Dict[str, Any]]:
    yml = _gh_fetch_workflow_yaml(owner=owner, repo=repo, workflow=workflow, ref=ref, token=token)
    if not yml:
        return {}
    return _discover_workflow_inputs_from_yaml(yaml_text=yml)

def _gh_dispatch_workflow(*, owner: str, repo: str, workflow: str, ref: str,
                          token: str, yaml_text: str, input_key: Optional[str]) -> Dict[str, Any]:
    """
    1차: input_key가 있으면 그 키로 디스패치
    2차 폴백: 422(Unexpected inputs)면 'inputs' 없이 디스패치 재시도
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
    headers = _gh_headers(token)
    def _post(payload: Dict[str, Any]) -> req.Response:
        return req.post(url, headers=headers, json=payload, timeout=15)

    # 1) 시도
    payload: Dict[str, Any] = {"ref": ref}
    if input_key:
        payload["inputs"] = {input_key: yaml_text}
    r = _post(payload)
    if 200 <= r.status_code < 300:
        return {"status": r.status_code, "detail": "ok"}

    # 2) 폴백: 422 · Unexpected inputs → 입력 없이 재시도
    try:
        js = r.json() if r.content else {}
    except Exception:
        js = {}
    msg = (js or {}).get("message", "").lower()
    if r.status_code == 422 and "unexpected inputs" in msg:
        r2 = _post({"ref": ref})
        if 200 <= r2.status_code < 300:
            return {"status": r2.status_code, "detail": "ok (fallback: no inputs)"}
        try:
            js2 = r2.json() if r2.content else {}
        except Exception:
            js2 = {}
        raise RuntimeError(f"workflow dispatch 실패(status={r2.status_code}): {js2 or r2.text}")

    # 3) 그 외 에러
    raise RuntimeError(f"workflow dispatch 실패(status={r.status_code}): {js or r.text}")

# ---- Page Main ---------------------------------------------------------------
def main() -> None:
    render_sidebar()
    _apply_pending_prefill()

    ok = st.session_state.pop("_flash_success", None)
    er = st.session_state.pop("_flash_error",   None)
    if ok: st.success(ok)
    if er: st.error(er)

    # ===== 상태 박스 ============================================================
    with st.container(border=True):
        st.subheader("🔍 상태 점검", divider="gray")

        # app.py의 시크릿 키 규칙을 그대로 사용 :contentReference[oaicite:2]{index=2}
        repo_full = st.secrets.get("GITHUB_REPO", "")
        token = st.secrets.get("GITHUB_TOKEN", "")
        ref = st.secrets.get("GITHUB_BRANCH", "main")
        workflow = st.secrets.get("GITHUB_WORKFLOW", "publish-prompts.yml")
        owner = repo = ""
        if repo_full and "/" in str(repo_full):
            owner, repo = str(repo_full).split("/", 1)

        if not (owner and repo):
            st.info("GITHUB_REPO 시크릿이 비어 있어 출판 기능이 비활성화됩니다. 편집과 저장은 계속 사용할 수 있습니다.")
        else:
            st.success(f"Repo OK — {owner}/{repo}, workflow={workflow}, ref={ref}")

        # 워크플로우 입력 자동 탐지
        wf_inputs: Dict[str, Dict[str, Any]] = {}
        if owner and repo:
            try:
                wf_inputs = _discover_workflow_inputs(owner, repo, workflow, ref, token)
            except Exception as e:
                st.warning(f"워크플로우 입력 탐지 실패: {e}")

        # 입력 키 선택 UI (여러 개일 때만 노출)
        input_key_default = st.secrets.get("GITHUB_WORKFLOW_INPUT_KEY", "") or ""
        discovered_keys = list(wf_inputs.keys())
        chosen_key: Optional[str] = None

        if discovered_keys:
            # 기본값 결정: 시크릿 > 'prompts_yaml' > 첫 번째
            if input_key_default and input_key_default in discovered_keys:
                chosen_key = input_key_default
            elif "prompts_yaml" in discovered_keys:
                chosen_key = "prompts_yaml"
            else:
                chosen_key = discovered_keys[0]

            st.caption(f"워크플로우 입력 감지: {', '.join(discovered_keys)}")
            chosen_key = st.selectbox(
                "출판에 사용할 입력 키",
                options=discovered_keys,
                index=discovered_keys.index(chosen_key),
                help="GitHub Workflow의 workflow_dispatch.inputs 키 중 하나를 선택하세요.",
                key="_publish_input_key",
            )
        else:
            st.caption("워크플로우 입력이 정의되어 있지 않습니다.(inputs 없음) → 입력 없이 디스패치합니다.")

    # ===== 편집 UI — 세로 배열 ==================================================
    st.markdown("### ① 페르소나(공통)")
    st.text_area("모든 모드에 공통 적용", key=K_PERSONA, height=160, placeholder="페르소나 텍스트…")

    st.markdown("### ② 모드별 프롬프트(지시/규칙)")
    st.text_area("문법(Grammar) 프롬프트",  key=K_GRAMMAR,  height=220, placeholder="문법 모드 지시/규칙…")
    st.text_area("문장(Sentence) 프롬프트", key=K_SENTENCE, height=220, placeholder="문장 모드 지시/규칙…")
    st.text_area("지문(Passage) 프롬프트",  key=K_PASSAGE,  height=220, placeholder="지문 모드 지시/규칙…")

    # ===== 액션 ================================================================
    st.markdown("### ③ 액션")
    b1, b2, b3, b4 = st.columns(4)

    # (a) 최신 프롬프트 불러오기(릴리스)
    with b1:
        if st.button("📥 최신 프롬프트 불러오기(릴리스 우선)", use_container_width=True, key="btn_fetch_prompts"):
            try:
                texts, src = _load_prompts_from_release()
                st.session_state["_PREFILL_PROMPTS"] = {
                    K_PERSONA:  texts.get(K_PERSONA, ""),
                    K_GRAMMAR:  texts.get(K_GRAMMAR, ""),
                    K_SENTENCE: texts.get(K_SENTENCE, ""),
                    K_PASSAGE:  texts.get(K_PASSAGE, ""),
                }
                st.session_state["_last_prompts_source"] = str(src)
                st.session_state["_flash_success"] = f"릴리스에서 프롬프트를 불러왔습니다: {src}"
                st.rerun()  # 콜백 외부이므로 경고 없음
            except FileNotFoundError as e:
                st.session_state["_flash_error"] = str(e); st.rerun()
            except Exception:
                st.session_state["_flash_error"] = "프롬프트 로딩 중 오류가 발생했습니다."; st.rerun()

    # (b) YAML 병합(로컬 필드→YAML)
    with b2:
        if st.button("🧾 YAML 병합(로컬→YAML)", use_container_width=True, key="merge_local"):
            st.session_state["_merged_yaml"] = _build_yaml_from_fields()
            st.toast("로컬 필드를 YAML로 병합했습니다.", icon="🧾")

    # (c) 💾 업데이트 저장(로컬 persist)
    with b3:
        if st.button("💾 업데이트 저장(로컬)", use_container_width=True, key="save_local"):
            y = st.session_state.get("_merged_yaml") or _build_yaml_from_fields()
            okv, msgs = _validate_yaml_text(y)
            if not okv:
                st.error("스키마 검증 실패 — 먼저 YAML을 병합/수정하세요.")
                if msgs: st.write("\n".join(f"- {m}" for m in msgs))
            else:
                try:
                    p = _save_yaml_local(y)
                    st.success(f"로컬 persist에 저장했습니다: {p}")
                except Exception as exc:
                    st.exception(exc)

    # (d) 🚀 출판(Publish → GitHub Actions dispatch)
    with b4:
        repo_full = st.secrets.get("GITHUB_REPO", "")
        token = st.secrets.get("GITHUB_TOKEN", "")
        ref = st.secrets.get("GITHUB_BRANCH", "main")
        workflow = st.secrets.get("GITHUB_WORKFLOW", "publish-prompts.yml")

        disabled = not (repo_full and "/" in str(repo_full) and token)
        clicked = st.button("🚀 출판(Publish)", type="primary",
                            disabled=disabled, use_container_width=True,
                            help=None if not disabled else "GITHUB_REPO와 GITHUB_TOKEN 시크릿이 필요합니다.")
        if clicked:
            y = st.session_state.get("_merged_yaml") or _build_yaml_from_fields()
            okv, msgs = _validate_yaml_text(y)
            if not okv:
                st.error("스키마 검증 실패 — 먼저 YAML을 병합/수정하세요.")
                if msgs: st.write("\n".join(f"- {m}" for m in msgs))
            else:
                try:
                    owner, repo = str(repo_full).split("/", 1)
                    # 선택된 입력 키: 없으면 None → 입력 없이 디스패치
                    input_key = st.session_state.get("_publish_input_key")
                    if input_key is not None and not str(input_key).strip():
                        input_key = None
                    r = _gh_dispatch_workflow(owner=owner, repo=repo, workflow=workflow,
                                              ref=ref, token=token, yaml_text=y,
                                              input_key=input_key)
                    st.success("출판 요청을 전송했습니다. Actions에서 처리 중입니다.")
                    st.caption(f"status={r.get('status')}, workflow={workflow}, ref={ref}, input={input_key or '(none)'}")
                    st.markdown(
                        f"[열기: Actions › {workflow}]"
                        f"(https://github.com/{owner}/{repo}/actions/workflows/{workflow})"
                    )
                except Exception as exc:
                    st.exception(exc)

    # YAML 미리보기/편집
    st.markdown("### YAML 미리보기/편집")
    st.text_area("YAML", key="_merged_yaml", height=320, placeholder="여기에 병합된 YAML이 표시됩니다. 필요하면 직접 수정하세요.")
    if st.session_state.get("_last_prompts_source"):
        st.caption(f"최근 소스: {st.session_state['_last_prompts_source']}")

if __name__ == "__main__":
    main()
# [AP-KANON-VERT-PUBLISH-FIX] END
