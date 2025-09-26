# [AP-KANON-UPDATE] START: src/ui/admin_prompt.py — ko/en canonicalization + prefill + save/publish
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import yaml
import requests as req
import streamlit as st

# ✅ 사이드바(SSOT)
try:
    from .utils.sider import render_sidebar
except Exception:
    from src.ui.utils.sider import render_sidebar  # fallback

# ✅ persist 경로(로컬 저장용)
try:
    from src.core.persist import effective_persist_dir
except Exception:
    effective_persist_dir = lambda: Path.home() / ".maic" / "persist"  # 폴백

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
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        for k in ("prompt", "text", "full", "system", "value", "content"):
            vs = v.get(k)
            if isinstance(vs, str) and vs.strip():
                return vs
        return json.dumps(v, ensure_ascii=False, indent=2)
    if isinstance(v, (list, tuple)):
        return "\n".join(str(x) for x in v)
    return str(v)

def _canon_via_core_modes(label: str) -> Optional[str]:
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
                return {"문법":"grammar","문장":"sentence","지문":"passage"}[s]
        key = getattr(res, "key", None)
        if isinstance(key, str) and key in ("grammar", "sentence", "passage"):
            return key
    return None

_SYNONYMS = {
    "grammar": {"grammar","pt","문법","문법설명","문법해설","문법규칙","품사","품사판별","문장성분","문법검사","문법풀이","문법 문제"},
    "sentence": {"sentence","sent","문장","문장분석","문장해석","문장구조","문장구조분석","문장성분분석","문장완성","문장구조해석","문장구조파악"},
    "passage": {"passage","para","지문","지문분석","독해","독해지문","독해분석","지문해석","독해 문제","장문","장문독해"},
}
_SUBSTR_HINTS: List[Tuple[str, Tuple[str, ...]]] = [
    ("grammar", ("문법","품사","성분")),
    ("sentence", ("문장","구조","성분","완성")),
    ("passage", ("지문","독해","장문")),
]

def _canon_mode_key(label_or_key: Any) -> str:
    s = str(label_or_key or "").strip()
    if not s:
        return ""
    via_core = _canon_via_core_modes(s)
    if via_core:
        return via_core
    t = _norm_token(s)
    for key, names in _SYNONYMS.items():
        if any(_norm_token(n) == t for n in names):
            return key
    low = s.lower()
    for key, hints in _SUBSTR_HINTS:
        if any(h in low for h in hints):
            return key
    if t in ("pt","mn","mina"):
        return "sentence" if t != "pt" else "grammar"
    return ""

# ---- file resolve ------------------------------------------------------------
def _resolve_release_prompts_file() -> Path | None:
    base = Path(st.session_state.get("_release_dir", "release")).resolve()
    for p in [base/"assets/prompts.yaml", base/"prompts.yaml",
              Path("assets/prompts.yaml").resolve(), Path("prompts.yaml").resolve()]:
        try:
            if p.exists() and p.is_file():
                return p
        except Exception:
            continue
    return None

# ---- extract ------------------------------------------------------------
def _extract_prompts(doc: Dict[str, Any]) -> Dict[str, str]:
    out = {K_PERSONA:"", K_GRAMMAR:"", K_SENTENCE:"", K_PASSAGE:""}

    def _assign(canon: str, payload: Any) -> None:
        if not canon: return
        text = _coerce_yaml_to_text(payload)
        if not text:   return
        if canon == "grammar":  out[K_GRAMMAR]  = text
        if canon == "sentence": out[K_SENTENCE] = text
        if canon == "passage":  out[K_PASSAGE]  = text

    def _maybe_persona(k: Any, v: Any) -> bool:
        kk = str(k or "").strip().lower()
        if kk in {"persona","common","profile","system","페르소나","공통","프로필"}:
            out[K_PERSONA] = _coerce_yaml_to_text(v); return True
        return False

    # 1) shallow
    for k, v in (doc or {}).items():
        if _maybe_persona(k, v): continue
        _assign(_canon_mode_key(k), v)

    # 2) mn/pt
    mn = doc.get("mn") or doc.get("mina")
    if isinstance(mn, dict):
        for nk, nv in mn.items(): _assign(_canon_mode_key(nk), nv)
    pt = doc.get("pt") if isinstance(doc.get("pt"), dict) else None
    if isinstance(pt, dict) and not out[K_GRAMMAR]:
        for k in ("grammar","prompt","text","full","system","설명"):
            if k in pt: _assign("grammar", pt[k]); break

    # 3) modes: dict/list/한글키
    for key in ("modes","모드","mode_prompts","modeprompts","prompts_by_mode"):
        sect = doc.get(key)
        if isinstance(sect, dict):
            for mk, mv in sect.items(): _assign(_canon_mode_key(mk), mv)
        elif isinstance(sect, list):
            for e in sect:
                if not isinstance(e, dict): continue
                label = e.get("key") or e.get("label") or e.get("name") or e.get("라벨")
                canon = _canon_mode_key(label)
                text = None
                for tk in ("prompt","text","full","system","value","content","지시","규칙"):
                    if isinstance(e.get(tk), str) and e.get(tk).strip(): text = e.get(tk); break
                if text is None: text = e
                if canon: _assign(canon, text)

    # 4) recursive (≤3)
    def _walk(node: Any, depth=0):
        if depth >= 3: return
        if isinstance(node, dict):
            for k, v in node.items():
                if _maybe_persona(k, v): continue
                _assign(_canon_mode_key(k), v); _walk(v, depth+1)
        elif isinstance(node, list):
            for it in node: _walk(it, depth+1)
    _walk(doc)
    return out

def _load_prompts_from_release() -> tuple[Dict[str,str], Path]:
    p = _resolve_release_prompts_file()
    if not p: raise FileNotFoundError("prompts.yaml을 release/assets 또는 루트에서 찾지 못했습니다.")
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

# ---- yaml build/validate/save/publish ---------------------------------------
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
    # 최소 스키마: persona 허용, modes 또는 3필드 존재
    ok_modes = isinstance(d.get("modes"), list) and len(d["modes"]) > 0
    # 보수적으로 grammar/sentence/passage 셋 중 1개라도 있어야 함
    has_any = any(k in d for k in ("grammar","sentence","passage"))
    if not (ok_modes or has_any):
        msgs.append("modes 리스트 또는 grammar/sentence/passage 중 1개 이상이 필요합니다.")
    return (len(msgs) == 0), msgs

def _save_yaml_local(yaml_text: str) -> Path:
    root = Path(effective_persist_dir()).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    p = root / "prompts.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    return p

def _gh_dispatch_workflow(*, owner: str, repo: str, workflow: str, ref: str, token: str, yaml_text: str) -> Dict[str, Any]:
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}"}
    payload = {"ref": ref, "inputs": {"prompts_yaml": yaml_text}}
    r = req.post(url, headers=headers, json=payload, timeout=15)
    try:
        js = r.json() if r.content else {}
    except Exception:
        js = {}
    if not (200 <= r.status_code < 300):
        raise RuntimeError(f"workflow dispatch 실패(status={r.status_code}): {js or r.text}")
    return {"status": r.status_code, "detail": js or "ok"}

# ---- Page Main ---------------------------------------------------------------
def main() -> None:
    render_sidebar()
    _apply_pending_prefill()

    ok = st.session_state.pop("_flash_success", None)
    er = st.session_state.pop("_flash_error",   None)
    if ok: st.success(ok)
    if er: st.error(er)

    # 상태 박스
    with st.container(border=True):
        st.subheader("🔍 상태 점검", divider="gray")
        rp = _resolve_release_prompts_file()
        if rp: st.success(f"경로 OK — prompts.yaml 확인: {rp}")
        else:  st.warning("prompts.yaml을 release/assets 또는 루트에서 찾지 못했습니다.")

    # 편집 UI
    st.markdown("### ① 페르소나(공통)")
    st.text_area("모든 모드에 공통 적용", key=K_PERSONA, height=160, placeholder="페르소나 텍스트...")

    st.markdown("### ② 모드별 프롬프트(지시/규칙)")
    c1, c2, c3 = st.columns(3)
    with c1: st.text_area("문법(Grammar) 프롬프트", key=K_GRAMMAR,  height=220, placeholder="문법 모든 지시/규칙...")
    with c2: st.text_area("문장(Sentence) 프롬프트", key=K_SENTENCE, height=220, placeholder="문장 모든 지시/규칙...")
    with c3: st.text_area("지문(Passage) 프롬프트",  key=K_PASSAGE,  height=220, placeholder="지문 모든 지시/규칙...")

    # 액션
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
                st.rerun()
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
                    r = _gh_dispatch_workflow(owner=owner, repo=repo, workflow=workflow, ref=ref, token=token, yaml_text=y)
                    st.success("출판 요청을 전송했습니다. Actions에서 처리 중입니다.")
                    st.caption(f"status={r.get('status')}, workflow={workflow}, ref={ref}")
                except Exception as exc:
                    st.exception(exc)

    # YAML 미리보기/편집
    st.markdown("### YAML 미리보기/편집")
    st.text_area("YAML", key="_merged_yaml", height=320, placeholder="여기에 병합된 YAML이 표시됩니다. 필요하면 직접 수정하세요.")
    if st.session_state.get("_last_prompts_source"):
        st.caption(f"최근 소스: {st.session_state['_last_prompts_source']}")

if __name__ == "__main__":
    main()
# [AP-KANON-UPDATE] END
