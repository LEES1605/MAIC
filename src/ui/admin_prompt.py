# [AP-STATUS-RUNID+SCHEMA] START: src/ui/admin_prompt.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import base64
import json
import time
import datetime as dt

import yaml
import requests as req
import streamlit as st

# ✅ 진짜 사이드바
try:
    from .utils.sider import render_sidebar
except Exception:
    from src.ui.utils.sider import render_sidebar  # fallback

# ---- UI Widget Keys (SSOT) ---------------------------------------------------
K_PERSONA  = "persona_text"
K_GRAMMAR  = "grammar_prompt"
K_SENTENCE = "sentence_prompt"
K_PASSAGE  = "passage_prompt"

# ---- Publish State Keys ------------------------------------------------------
S_PUB_STATE       = "_PUBLISH_STATE"          # "idle" | "running" | "done" | "error"
S_PUB_LAST_STATE  = "_PUBLISH_LAST_STATE"
S_PUB_DISPATCH_AT = "_PUBLISH_DISPATCH_AT"    # float epoch
S_PUB_RUN_ID      = "_PUBLISH_RUN_ID"         # int | None
S_PUB_RUN_URL     = "_PUBLISH_RUN_URL"        # str | None
S_PUB_NEXT_POLL   = "_PUBLISH_NEXT_POLL"      # float epoch (throttle)
S_PUB_INPUT_KEY   = "_publish_input_key"      # 선택된 입력키(UI)

# ======================================================================================
# YAML 로더(릴리스/로컬) + 파서(ko/en 라벨 대응)
# ======================================================================================
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
            s = v.get(k)
            if isinstance(s, str) and s.strip():
                return s
        return json.dumps(v, ensure_ascii=False, indent=2)
    if isinstance(v, (list, tuple)):
        return "\n".join(str(x) for x in v)
    return str(v)

_SYNONYMS = {
    "grammar": {"grammar","pt","문법","문법설명","문법해설","문법규칙","품사","문장성분","문법검사"},
    "sentence": {"sentence","sent","문장","문장분석","문장해석","문장구조","문장구조분석","문장성분분석","문장완성"},
    "passage": {"passage","para","지문","지문분석","독해","독해지문","독해분석","지문해석","장문독해"},
}

def _canon_mode_key(label_or_key: Any) -> str:
    s = str(label_or_key or "").strip()
    if not s:
        return ""
    t = _norm_token(s)
    for key, names in _SYNONYMS.items():
        if any(_norm_token(n) == t for n in names):
            return key
    return ""

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

def _extract_prompts(doc: Dict[str, Any]) -> Dict[str, str]:
    out = {K_PERSONA:"", K_GRAMMAR:"", K_SENTENCE:"", K_PASSAGE:""}
    data = {(k.lower() if isinstance(k, str) else k): v for k,v in (doc or {}).items()}

    # persona/common
    for yk in ("persona","common","profile","system","페르소나","공통","프로필"):
        if yk in data:
            out[K_PERSONA] = _coerce_yaml_to_text(data[yk]); break

    # top-level keys (ko/en)
    for raw_key, val in list(data.items()):
        canon = _canon_mode_key(raw_key)
        if not canon: continue
        txt = _coerce_yaml_to_text(val)
        if canon == "grammar":  out[K_GRAMMAR]  = txt
        if canon == "sentence": out[K_SENTENCE] = txt
        if canon == "passage":  out[K_PASSAGE]  = txt

    # nested mn/pt
    mn = data.get("mn") or data.get("mina")
    if isinstance(mn, dict):
        for nk, nv in mn.items():
            canon = _canon_mode_key(nk)
            if canon == "sentence": out[K_SENTENCE] = _coerce_yaml_to_text(nv)
            if canon == "passage":  out[K_PASSAGE]  = _coerce_yaml_to_text(nv)

    pt = data.get("pt") if isinstance(data.get("pt"), dict) else None
    if isinstance(pt, dict) and not out[K_GRAMMAR]:
        for k in ("grammar","prompt","text","full","system"):
            if k in pt:
                out[K_GRAMMAR] = _coerce_yaml_to_text(pt[k]); break

    # modes section(dict/list)
    sect = data.get("modes") if isinstance(data.get("modes"), (dict, list)) else None
    if sect is None and isinstance(data.get("모드"), (dict, list)):
        sect = data.get("모드")

    if isinstance(sect, dict):
        for k,v in sect.items():
            canon = _canon_mode_key(k)
            if canon == "grammar":  out[K_GRAMMAR]  = _coerce_yaml_to_text(v)
            if canon == "sentence": out[K_SENTENCE] = _coerce_yaml_to_text(v)
            if canon == "passage":  out[K_PASSAGE]  = _coerce_yaml_to_text(v)
    elif isinstance(sect, list):
        for e in sect:
            if not isinstance(e, dict): continue
            label = e.get("key") or e.get("label") or e.get("name") or e.get("라벨")
            canon = _canon_mode_key(label)
            payload = e.get("prompt") or e.get("text") or e.get("full") or e.get("system") or e
            if canon == "grammar":  out[K_GRAMMAR]  = _coerce_yaml_to_text(payload)
            if canon == "sentence": out[K_SENTENCE] = _coerce_yaml_to_text(payload)
            if canon == "passage":  out[K_PASSAGE]  = _coerce_yaml_to_text(payload)

    return out

def _load_prompts_from_release() -> tuple[Dict[str,str], Path]:
    p = _resolve_release_prompts_file()
    if not p:
        raise FileNotFoundError("prompts.yaml을 release/assets 또는 루트에서 찾지 못했습니다.")
    with p.open("r", encoding="utf-8") as f:
        y = yaml.safe_load(f) or {}
    return _extract_prompts(y), p

def _apply_pending_prefill() -> None:
    ss = st.session_state
    data = ss.pop("_PREFILL_PROMPTS", None)
    if isinstance(data, dict):
        ss[K_PERSONA]  = data.get(K_PERSONA,  "")
        ss[K_GRAMMAR]  = data.get(K_GRAMMAR,  "")
        ss[K_SENTENCE] = data.get(K_SENTENCE, "")
        ss[K_PASSAGE]  = data.get(K_PASSAGE,  "")

# ======================================================================================
# YAML build/validate/save  (✅ 검증 스키마와 100% 일치)
# ======================================================================================
def _build_yaml_from_fields() -> str:
    """
    검증기 요구 스키마에 맞춘 정규 YAML 생성.
    {
      version: "1",
      persona: "<string>",
      modes: { grammar: "<string>", sentence: "<string>", passage: "<string>" }
    }
    """
    doc = {
        "version": "1",
        "persona": st.session_state.get(K_PERSONA, "") or "",
        "modes": {
            "grammar":  st.session_state.get(K_GRAMMAR,  "") or "",
            "sentence": st.session_state.get(K_SENTENCE, "") or "",
            "passage":  st.session_state.get(K_PASSAGE,  "") or "",
        },
    }
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)

def _validate_yaml_text(text: str) -> tuple[bool, List[str]]:
    """
    스키마 사전 점검:
    - version 필수
    - modes는 dict이며 grammar/sentence/passage 3키만 허용
    - 각 값은 문자열
    """
    msgs: List[str] = []
    try:
        y = yaml.safe_load(text) or {}
    except Exception as e:
        return False, [f"YAML 파싱 실패: {e}"]

    if not isinstance(y.get("version"), (str, int, float)):
        msgs.append("'version' 필드가 필요합니다.")

    modes = y.get("modes")
    if not isinstance(modes, dict):
        msgs.append("'modes'는 매핑(dict)이어야 합니다.")
    else:
        required = ("grammar", "sentence", "passage")
        for k in required:
            v = modes.get(k, "")
            if not isinstance(v, str) or not v.strip():
                msgs.append(f"'modes.{k}' 문자열이 필요합니다.")
        extras = [k for k in modes.keys() if k not in required]
        if extras:
            msgs.append(f"'modes'에 허용되지 않은 키: {extras}")

    return (len(msgs) == 0), msgs

def _save_yaml_local(yaml_text: str) -> Path:
    try:
        from src.core.persist import effective_persist_dir
    except Exception:
        effective_persist_dir = lambda: Path.home() / ".maic" / "persist"  # type: ignore

    root = Path(effective_persist_dir()).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    p = root / "prompts.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    return p

# ======================================================================================
# GitHub Actions — 입력 자동탐지 + 디스패치 + 정확 폴링(run id)
# ======================================================================================
def _gh_headers(token: Optional[str]) -> Dict[str, str]:
    h = {"Accept": "application/vnd.github+json"}
    if token: h["Authorization"] = f"Bearer {token}"
    return h

def _fetch_workflow_yaml(owner: str, repo: str, workflow: str, ref: str, token: Optional[str]) -> Optional[str]:
    headers = _gh_headers(token)
    try:
        r = req.get(f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}",
                    headers=headers, timeout=10)
        if r.ok:
            path = r.json().get("path")
            if isinstance(path, str) and path:
                r2 = req.get(f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={ref}",
                             headers=headers, timeout=10)
                if r2.ok and r2.json().get("encoding") == "base64":
                    return base64.b64decode(r2.json()["content"].encode("utf-8")).decode("utf-8","ignore")
    except Exception:
        pass
    try:
        r3 = req.get(f"https://api.github.com/repos/{owner}/{repo}/contents/.github/workflows/{workflow}?ref={ref}",
                     headers=headers, timeout=10)
        if r3.ok and r3.json().get("encoding") == "base64":
            return base64.b64decode(r3.json()["content"].encode("utf-8")).decode("utf-8","ignore")
    except Exception:
        pass
    return None

def _discover_inputs(owner: str, repo: str, workflow: str, ref: str, token: Optional[str]) -> List[str]:
    yml = _fetch_workflow_yaml(owner, repo, workflow, ref, token) or ""
    try:
        y = yaml.safe_load(yml) or {}
    except Exception:
        return []
    on = y.get("on")
    if isinstance(on, dict):
        wd = on.get("workflow_dispatch")
        if isinstance(wd, dict):
            ins = wd.get("inputs") or {}
            if isinstance(ins, dict):
                return [k for k in ins.keys() if isinstance(k, str)]
    elif isinstance(on, list) and "workflow_dispatch" in on:
        return []
    return []

def _dispatch_workflow(owner: str, repo: str, workflow: str, ref: str,
                       token: str, yaml_text: str, input_key: Optional[str]) -> Dict[str, Any]:
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
    headers = _gh_headers(token)
    def _post(payload): return req.post(url, headers=headers, json=payload, timeout=15)

    payload: Dict[str, Any] = {"ref": ref}
    if input_key:
        payload["inputs"] = {input_key: yaml_text}
    r = _post(payload)
    if 200 <= r.status_code < 300:
        return {"status": r.status_code, "detail": "ok"}

    # 폴백: 422 Unexpected inputs → 입력 없이 재시도
    try:
        js = r.json() if r.content else {}
    except Exception:
        js = {}
    if r.status_code == 422 and "unexpected" in (js.get("message","").lower()):
        r2 = _post({"ref": ref})
        if 200 <= r2.status_code < 300:
            return {"status": r2.status_code, "detail": "ok (fallback: no inputs)"}
        raise RuntimeError(f"workflow dispatch 실패(status={r2.status_code}): {r2.text}")
    raise RuntimeError(f"workflow dispatch 실패(status={r.status_code}): {js or r.text}")

def _iso_to_epoch(s: str) -> float:
    try:
        return dt.datetime.fromisoformat(s.replace("Z","+00:00")).timestamp()
    except Exception:
        return 0.0

def _list_runs(owner: str, repo: str, workflow: str, ref: str, token: Optional[str]) -> List[Dict[str, Any]]:
    headers = _gh_headers(token)
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/runs"
    params = {"event": "workflow_dispatch", "branch": ref, "per_page": 10}
    try:
        r = req.get(url, headers=headers, params=params, timeout=10)
        if not r.ok:
            return []
        js = r.json()
        runs = js.get("workflow_runs") or []
        return runs if isinstance(runs, list) else []
    except Exception:
        return []

def _poll_run_by_id(owner: str, repo: str, run_id: int, token: Optional[str]) -> Tuple[str, Optional[str]]:
    headers = _gh_headers(token)
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}"
    try:
        r = req.get(url, headers=headers, timeout=10)
        if not r.ok:
            return "running", None
        run = r.json()
    except Exception:
        return "running", None

    status = (run.get("status") or "").lower()         # queued | in_progress | completed
    conclusion = (run.get("conclusion") or "").lower() # success | failure | cancelled ...
    url = run.get("html_url")

    if status != "completed":
        return "running", url
    if conclusion == "success":
        return "done", url
    return "error", url

def _find_recent_run_after_dispatch(owner: str, repo: str, workflow: str, ref: str,
                                    token: Optional[str], since_ts: float) -> Optional[Dict[str, Any]]:
    runs = _list_runs(owner, repo, workflow, ref, token)
    if not runs:
        return None
    threshold = max(0.0, float(since_ts or 0.0) - 30.0)
    cands: List[Tuple[int, Dict[str, Any]]] = []
    for r in runs:
        try:
            created = _iso_to_epoch(str(r.get("created_at") or ""))
            rid = int(r.get("id"))
            if created >= threshold:
                cands.append((rid, r))
        except Exception:
            continue
    if not cands:
        return None
    cands.sort(key=lambda x: x[0], reverse=True)
    return cands[0][1]

# -- status css/ui ---------------------------------------------------------------------
def _inject_status_css_once() -> None:
    if st.session_state.get("_status_css_v2"):
        return
    st.session_state["_status_css_v2"] = True
    st.markdown("""
<style>
  .status-wrap{display:flex;align-items:center;gap:8px;margin-top:6px}
  .status-btn{cursor:default;border:0;padding:8px 12px;border-radius:10px;font-weight:800;color:#111;box-shadow:0 1px 2px rgba(0,0,0,.08)}
  .status-btn.running{background:#FFE083}
  .status-btn.done{background:#34D399;color:#fff}
  .status-btn.error{background:#EF4444;color:#fff}
  .status-hint{font-size:12px;color:#555}
</style>""", unsafe_allow_html=True)

def _render_status_button() -> None:
    _inject_status_css_once()
    st.session_state.setdefault(S_PUB_STATE, "idle")
    state = st.session_state[S_PUB_STATE]
    url = st.session_state.get(S_PUB_RUN_URL)

    label = "대기"; klass = ""
    if state == "running": label, klass = "🟡 처리중…", "running"
    elif state == "done":  label, klass = "🟢 처리완료", "done"
    elif state == "error": label, klass = "🔴 실패", "error"

    st.markdown(
        f'<div class="status-wrap"><button class="status-btn {klass}">{label}</button>'
        + (f'<a href="{url}" target="_blank" class="status-hint">Actions 열기</a>' if url else "")
        + "</div>",
        unsafe_allow_html=True,
    )

def _tick_auto_poll(interval: float = 6.0) -> None:
    now = time.time()
    nxt = float(st.session_state.get(S_PUB_NEXT_POLL, 0.0) or 0.0)
    if now < nxt:
        return
    st.session_state[S_PUB_NEXT_POLL] = now + max(2.0, float(interval))
    time.sleep(0.3)
    try:
        st.rerun()
    except Exception:
        try: st.experimental_rerun()
        except Exception: pass

def _handle_publish_state(owner: str, repo: str, workflow: str, ref: str, token: Optional[str]) -> None:
    ss = st.session_state
    ss.setdefault(S_PUB_STATE, "idle")
    cur = ss[S_PUB_STATE]
    prev = ss.get(S_PUB_LAST_STATE)
    if prev and prev != cur:
        if cur == "done":  st.toast("출판 완료!", icon="✅")
        if cur == "error": st.toast("출판 실패. Actions 로그를 확인하세요.", icon="❌")
    ss[S_PUB_LAST_STATE] = cur

    if cur != "running":
        return

    run_id = ss.get(S_PUB_RUN_ID)
    if isinstance(run_id, int) and run_id > 0:
        state, url = _poll_run_by_id(owner, repo, run_id, token)
        if url: ss[S_PUB_RUN_URL] = url
        if state == "running":
            _tick_auto_poll(6.0)
        else:
            ss[S_PUB_STATE] = state
        return

    found = _find_recent_run_after_dispatch(owner, repo, workflow, ref, token,
                                            since_ts=float(ss.get(S_PUB_DISPATCH_AT, 0.0) or 0.0))
    if found:
        try:
            ss[S_PUB_RUN_ID] = int(found.get("id"))
        except Exception:
            ss[S_PUB_RUN_ID] = None
        url = found.get("html_url")
        if isinstance(url, str) and url:
            ss[S_PUB_RUN_URL] = url
    _tick_auto_poll(6.0)

# ======================================================================================
# 페이지 본문
# ======================================================================================
def main() -> None:
    render_sidebar()  # SSOT 사이드바. :contentReference[oaicite:1]{index=1}
    _apply_pending_prefill()

    # 0) 상태 박스(시크릿/입력키 감지)
    with st.container(border=True):
        st.subheader("🔍 상태 점검", divider="gray")

        repo_full = st.secrets.get("GITHUB_REPO", "")
        token     = st.secrets.get("GITHUB_TOKEN", "")
        ref       = st.secrets.get("GITHUB_BRANCH", "main")
        workflow  = st.secrets.get("GITHUB_WORKFLOW", "publish-prompts.yml")

        owner = repo = ""
        if repo_full and "/" in str(repo_full):
            owner, repo = str(repo_full).split("/", 1)

        if not (owner and repo):
            st.info("GITHUB_REPO 시크릿이 비어 있어 출판 기능이 비활성화됩니다. 편집과 저장은 계속 사용할 수 있습니다.")
        else:
            st.success(f"Repo OK — {owner}/{repo}, workflow={workflow}, ref={ref}")

        keys = _discover_inputs(owner, repo, workflow, ref, token) if (owner and repo) else []
        input_key_default = st.secrets.get("GITHUB_WORKFLOW_INPUT_KEY", "") or ""
        chosen_key: Optional[str] = None
        if keys:
            if input_key_default and input_key_default in keys:
                chosen_key = input_key_default
            elif "prompts_yaml" in keys:
                chosen_key = "prompts_yaml"
            else:
                chosen_key = keys[0]
            chosen_key = st.selectbox(
                "출판에 사용할 입력 키",
                options=keys, index=keys.index(chosen_key),
                key=S_PUB_INPUT_KEY,
                help="GitHub Workflow의 workflow_dispatch.inputs 중 하나를 선택하세요.",
            )
        else:
            st.caption("워크플로우 입력이 정의되어 있지 않습니다 → 입력 없이 디스패치합니다.")

    # 1) 편집 UI(세로 배열)
    st.markdown("### ① 페르소나(공통)")
    st.text_area("모든 모드에 공통 적용", key=K_PERSONA, height=160, placeholder="페르소나 텍스트…")

    st.markdown("### ② 모드별 프롬프트(지시/규칙)")
    st.text_area("문법(Grammar) 프롬프트",  key=K_GRAMMAR,  height=220, placeholder="문법 모드 지시/규칙…")
    st.text_area("문장(Sentence) 프롬프트", key=K_SENTENCE, height=220, placeholder="문장 모드 지시/규칙…")
    st.text_area("지문(Passage) 프롬프트",  key=K_PASSAGE,  height=220, placeholder="지문 모드 지시/규칙…")

    # 2) 액션
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

    # (d) 🚀 출판(Publish) + 상태 버튼(🟡/🟢/🔴)
    with b4:
        repo_full = st.secrets.get("GITHUB_REPO", "")
        token     = st.secrets.get("GITHUB_TOKEN", "")
        ref       = st.secrets.get("GITHUB_BRANCH", "main")
        workflow  = st.secrets.get("GITHUB_WORKFLOW", "publish-prompts.yml")
        disabled  = not (repo_full and "/" in str(repo_full) and token)

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
                    input_key = st.session_state.get(S_PUB_INPUT_KEY)
                    _ = _dispatch_workflow(owner=owner, repo=repo, workflow=workflow,
                                           ref=ref, token=token, yaml_text=y, input_key=input_key)
                    # 상태 전이
                    st.session_state[S_PUB_STATE] = "running"
                    st.session_state[S_PUB_DISPATCH_AT] = time.time()
                    st.session_state[S_PUB_RUN_ID] = None
                    st.session_state[S_PUB_RUN_URL] = None
                    st.toast("출판 요청을 전송했습니다. Actions에서 처리 중입니다.", icon="⌛")
                except Exception as exc:
                    st.session_state[S_PUB_STATE] = "error"
                    st.exception(exc)

        _render_status_button()

    # YAML 미리보기/편집
    st.markdown("### YAML 미리보기/편집")
    st.text_area("YAML", key="_merged_yaml", height=320, placeholder="여기에 병합된 YAML이 표시됩니다. 필요하면 직접 수정하세요.")
    if st.session_state.get("_last_prompts_source"):
        st.caption(f"최근 소스: {st.session_state['_last_prompts_source']}")

    # running이면 계속 폴링
    if st.session_state.get(S_PUB_STATE) == "running":
        repo_full = st.secrets.get("GITHUB_REPO", "")
        token     = st.secrets.get("GITHUB_TOKEN", "")
        ref       = st.secrets.get("GITHUB_BRANCH", "main")
        workflow  = st.secrets.get("GITHUB_WORKFLOW", "publish-prompts.yml")
        if repo_full and "/" in str(repo_full):
            owner, repo = str(repo_full).split("/", 1)
            _handle_publish_state(owner, repo, workflow, ref, token)

if __name__ == "__main__":
    main()
# [AP-STATUS-RUNID+SCHEMA] END
