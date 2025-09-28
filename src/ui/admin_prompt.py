# [APUB‑V4] START: FILE src/ui/admin_prompt.py — publish fixes (dispatch+poll+local load)
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

# ✅ 진짜 사이드바(SSOT)
try:
    from .utils.sider import render_sidebar  # official
except Exception:
    from src.ui.utils.sider import render_sidebar  # fallback

# ---- UI Widget Keys ----------------------------------------------------------
K_PERSONA  = "persona_text"
K_GRAMMAR  = "grammar_prompt"
K_SENTENCE = "sentence_prompt"
K_PASSAGE  = "passage_prompt"

# ---- Publish State Keys ------------------------------------------------------
S_PUB_STATE       = "_PUBLISH_STATE"          # "idle" | "running" | "done" | "error"
S_PUB_LAST_STATE  = "_PUBLISH_LAST_STATE"
S_PUB_DISPATCH_AT = "_PUBLISH_DISPATCH_AT"
S_PUB_RUN_ID      = "_PUBLISH_RUN_ID"
S_PUB_RUN_URL     = "_PUBLISH_RUN_URL"
S_PUB_NEXT_POLL   = "_PUBLISH_NEXT_POLL"
S_PUB_INPUT_KEY   = "_publish_input_key"      # workflow_dispatch.inputs 키

# =============================================================================
# Loader — release/prompts.yaml → 세션키(페르소나/3모드)로 주입
# =============================================================================
def _norm_token(x: Any) -> str:
    s = str(x or "").strip().lower()
    return "".join(ch for ch in s if ch.isalnum())

_SYNONYMS = {
    "grammar": {
        "grammar","pt","문법","문법설명","문법해설","문법규칙","품사","문장성분","문법검사"
    },
    "sentence": {
        "sentence","sent","문장","문장분석","문장해석","문장구조","문장구조분석","문장완성","문장성분분석"
    },
    "passage": {
        "passage","para","지문","지문분석","독해","독해지문","독해분석","지문해석","장문독해"
    },
}
def _canon_mode_key(label_or_key: Any) -> str:
    t = _norm_token(label_or_key)
    for key, names in _SYNONYMS.items():
        if any(_norm_token(n) == t for n in names):
            return key
    return ""

def _coerce_yaml_to_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        for k in ("prompt","text","full","system","value","content"):
            s = v.get(k)
            if isinstance(s, str) and s.strip():
                return s
        return json.dumps(v, ensure_ascii=False, indent=2)
    if isinstance(v, (list, tuple)):
        return "\n".join(str(x) for x in v)
    return str(v)

def _resolve_release_prompts_file() -> Path | None:
    """
    릴리스/에셋 위치에서 prompts.yaml을 가장 먼저 발견되는 경로로 선택.
    우선순위: <_release_dir>/assets > <_release_dir> > ./assets > ./
    """
    base = Path(st.session_state.get("_release_dir", "release")).resolve()
    for p in (base/"assets/prompts.yaml", base/"prompts.yaml",
              Path("assets/prompts.yaml").resolve(), Path("prompts.yaml").resolve()):
        try:
            if p.exists() and p.is_file():
                return p
        except Exception:
            continue
    return None

def _extract_prompts(doc: Dict[str, Any]) -> Dict[str, str]:
    """
    다양한 YAML 스키마를 허용해 4개 텍스트(페르소나/문법/문장/지문)로 매핑.
    지원:
      • Top-level: {grammar/sentence/passage} + 한국어 라벨/약어
      • Nested: {mn:{sentence,passage}}, {pt:{grammar|prompt|text|...}}
      • Modes:  dict → {modes:{grammar|sentence|passage}}
                list → {modes:[{key|label|name, prompt|text|full|...}, ...]}
    """
    out: Dict[str, str] = {K_PERSONA:"", K_GRAMMAR:"", K_SENTENCE:"", K_PASSAGE:""}
    d = {(k.lower() if isinstance(k, str) else k): v for k, v in (doc or {}).items()}

    # 0) Persona/Common
    for yk in ("persona","common","profile","system","페르소나","공통","프로필"):
        if yk in d:
            out[K_PERSONA] = _coerce_yaml_to_text(d[yk])
            break

    # 1) Top-level ko/en key들
    for raw_key, val in list(d.items()):
        canon = _canon_mode_key(raw_key)
        if not canon:
            continue
        txt = _coerce_yaml_to_text(val)
        if canon == "grammar":  out[K_GRAMMAR]  = txt
        if canon == "sentence": out[K_SENTENCE] = txt
        if canon == "passage":  out[K_PASSAGE]  = txt

    # 2) Nested mn/pt
    mn = d.get("mn") or d.get("mina")
    if isinstance(mn, dict):
        if "sentence" in mn: out[K_SENTENCE] = _coerce_yaml_to_text(mn["sentence"])
        if "passage"  in mn: out[K_PASSAGE]  = _coerce_yaml_to_text(mn["passage"])
    pt = d.get("pt") if isinstance(d.get("pt"), dict) else None
    if isinstance(pt, dict) and not out[K_GRAMMAR]:
        for k in ("grammar","prompt","text","full","system","설명"):
            if k in pt:
                out[K_GRAMMAR] = _coerce_yaml_to_text(pt[k]); break

    # 3) Modes(dict/list)
    modes = d.get("modes") if isinstance(d.get("modes"), (dict, list)) else None
    if modes is None and isinstance(d.get("모드"), (dict, list)):
        modes = d.get("모드")

    def _apply_canon(canon_key: str, payload: Any) -> None:
        txt = _coerce_yaml_to_text(payload)
        if canon_key == "grammar":  out[K_GRAMMAR]  = txt
        if canon_key == "sentence": out[K_SENTENCE] = txt
        if canon_key == "passage":  out[K_PASSAGE]  = txt

    if isinstance(modes, dict):
        for mk, mv in modes.items():
            ck = _canon_mode_key(mk) or str(mk).strip().lower()
            if ck in ("grammar","sentence","passage"):
                _apply_canon(ck, mv)
    elif isinstance(modes, list):
        for entry in modes:
            if not isinstance(entry, dict):
                continue
            label = entry.get("key") or entry.get("label") or entry.get("name") or entry.get("라벨")
            payload = None
            for tk in ("prompt","text","full","system","value","content","지시","규칙"):
                if isinstance(entry.get(tk), str) and entry.get(tk).strip():
                    payload = entry.get(tk); break
            if payload is None:
                payload = entry
            ck = _canon_mode_key(label)
            if ck: _apply_canon(ck, payload)

    return out

def _load_prompts_from_release() -> tuple[Dict[str, str], Path]:
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

# =============================================================================
# Local Save/Load — per-mode(4개 파일: persona + 3모드)
# =============================================================================
def _effective_persist_dir() -> Path:
    try:
        from src.core.persist import effective_persist_dir  # app.py와 정합
        return Path(effective_persist_dir()).expanduser()
    except Exception:
        return Path.home() / ".maic" / "persist"

def _save_local_per_mode(persona: str, g: str, s: str, psg: str) -> Dict[str, Path]:
    root = _effective_persist_dir()
    root.mkdir(parents=True, exist_ok=True)
    out = {
        "persona.txt": root/"persona.txt",
        "grammar.txt": root/"grammar.txt",
        "sentence.txt": root/"sentence.txt",
        "passage.txt":  root/"passage.txt",
    }
    out["persona.txt"].write_text(persona or "", encoding="utf-8")
    out["grammar.txt"].write_text(g or "", encoding="utf-8")
    out["sentence.txt"].write_text(s or "", encoding="utf-8")
    out["passage.txt"].write_text(psg or "", encoding="utf-8")
    return out

def _load_local_per_mode() -> Dict[str, str]:
    root = _effective_persist_dir()
    def _read(p: Path) -> str:
        try:
            return p.read_text(encoding="utf-8")
        except Exception:
            return ""
    return {
        K_PERSONA: _read(root/"persona.txt"),
        K_GRAMMAR: _read(root/"grammar.txt"),
        K_SENTENCE: _read(root/"sentence.txt"),
        K_PASSAGE:  _read(root/"passage.txt"),
    }

# =============================================================================
# YAML(출판용 내부 자동 병합) + 사전검증
# =============================================================================
def _build_yaml_for_publish() -> str:
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

# =============================================================================
# GitHub Actions — 입력 자동탐지 + 디스패치 + 폴백/폴링
# =============================================================================
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

def _repository_dispatch(owner: str, repo: str, token: str, yaml_text: str,
                         event_type: str = "publish-prompts") -> Dict[str, Any]:
    url = f"https://api.github.com/repos/{owner}/{repo}/dispatches"
    headers = _gh_headers(token)
    payload = {"event_type": event_type, "client_payload": {"prompts_yaml": yaml_text, "via": "admin-ui"}}
    r = req.post(url, headers=headers, json=payload, timeout=15)
    if 200 <= r.status_code < 300:
        return {"status": r.status_code, "detail": "ok(repository_dispatch)"}
    raise RuntimeError(f"repository_dispatch 실패(status={r.status_code}): {r.text}")

def _dispatch_workflow(owner: str, repo: str, workflow: str, ref: str,
                       token: str, yaml_text: str, input_key: Optional[str]) -> Dict[str, Any]:
    """
    우선순위:
      1) input_key가 있으면 workflow_dispatch(inputs 포함)
      2) 그 외(입력키 없음/422 등)에는 repository_dispatch로 폴백
    """
    # 입력키가 없으면 곧장 repository_dispatch 사용
    if not input_key:
        return _repository_dispatch(owner, repo, token, yaml_text, event_type="publish-prompts")

    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
    headers = _gh_headers(token)

    def _post(payload): 
        return req.post(url, headers=headers, json=payload, timeout=15)

    payload: Dict[str, Any] = {"ref": ref, "inputs": {input_key: yaml_text}}
    r = _post(payload)

    if 200 <= r.status_code < 300:
        return {"status": r.status_code, "detail": "ok"}

    # 422 처리 → 모두 repository_dispatch로 전환
    try:
        js = r.json() if r.content else {}
        msg = (js.get("message") or "").lower()
    except Exception:
        js = {}
        msg = ""

    # ‘does not have workflow_dispatch’ 또는 ‘Unexpected inputs’ 모두 폴백
    if r.status_code == 422 and ("does not have 'workflow_dispatch'" in (js.get("message") or "") or "unexpected" in msg):
        return _repository_dispatch(owner, repo, token, yaml_text, event_type="publish-prompts")

    raise RuntimeError(f"workflow dispatch 실패(status={r.status_code}): {js or r.text}")

def _iso_to_epoch(s: str) -> float:
    try:
        return dt.datetime.fromisoformat(s.replace("Z","+00:00")).timestamp()
    except Exception:
        return 0.0

def _list_runs(owner: str, repo: str, workflow: str, ref: str, token: Optional[str]) -> List[Dict[str, Any]]:
    """
    ❗️이벤트 필터(event=...)를 제거해 workflow_dispatch/repository_dispatch 모두 추적.
    """
    headers = _gh_headers(token)
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/runs"
    params = {"branch": ref, "per_page": 10}  # event 필터 제거
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

# ---- 상태 버튼 UI ------------------------------------------------------------
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
    if state == "running": label, klass = "🟡 처리중...", "running"
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

# =============================================================================
# Page
# =============================================================================
def main() -> None:
    # 사이드바(SSOT)
    render_sidebar()
    _apply_pending_prefill()

    # 상태 점검/시크릿
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
            st.info("GITHUB_REPO 시크릿이 비어 있어 출판 기능이 비활성화됩니다.")
        else:
            st.success(f"Repo OK — {owner}/{repo}, workflow={workflow}, ref={ref}")

        # 워크플로 입력키 자동탐지
        keys = _discover_inputs(owner, repo, workflow, ref, token) if (owner and repo) else []
        default_key = st.secrets.get("GITHUB_WORKFLOW_INPUT_KEY", "") or ""
        chosen: Optional[str] = None
        if keys:
            if default_key and default_key in keys: chosen = default_key
            elif "prompts_yaml" in keys:           chosen = "prompts_yaml"
            else:                                   chosen = keys[0]
            st.selectbox("출판 입력키", options=keys, index=keys.index(chosen), key=S_PUB_INPUT_KEY,
                         help="workflow_dispatch.inputs 중 하나를 선택합니다.")
        else:
            st.caption("이 워크플로는 입력 없이 디스패치되며, UI가 자동으로 repository_dispatch를 사용합니다.")

    # 편집 UI(세로 배열)
    st.markdown("### ① 페르소나(공통)")
    st.text_area("모든 모드에 공통 적용", key=K_PERSONA, height=160, placeholder="페르소나 텍스트...")

    st.markdown("### ② 모드별 프롬프트(지시/규칙)")
    st.text_area("문법(Grammar) 프롬프트",  key=K_GRAMMAR,  height=220, placeholder="문법 모드 지시/규칙...")
    st.text_area("문장(Sentence) 프롬프트", key=K_SENTENCE, height=220, placeholder="문장 모드 지시/규칙...")
    st.text_area("지문(Passage) 프롬프트",  key=K_PASSAGE,  height=220, placeholder="지문 모드 지시/규칙...")

    # 액션
    st.markdown("### ③ 액션")
    c1, c2, c3 = st.columns(3)

    # (a) 최신 프롬프트 불러오기(릴리스 → 세션)
    with c1:
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

    # (b) 📂 모드별 불러오기(로컬 persist)
    with c2:
        if st.button("📂 모드별 불러오기(로컬)", use_container_width=True, key="load_per_mode"):
            data = _load_local_per_mode()
            st.session_state["_PREFILL_PROMPTS"] = data
            st.session_state["_flash_success"] = "로컬 저장본을 불러왔습니다."
            st.rerun()

    # (c) 💾 모드별 저장(로컬 persist에 4파일)
    with c3:
        if st.button("💾 모드별 저장(로컬)", use_container_width=True, key="save_per_mode"):
            files = _save_local_per_mode(
                st.session_state.get(K_PERSONA,  ""),
                st.session_state.get(K_GRAMMAR,  ""),
                st.session_state.get(K_SENTENCE, ""),
                st.session_state.get(K_PASSAGE,  ""),
            )
            root = _effective_persist_dir()
            st.success("로컬 저장 완료")
            st.code("\n".join(f"{k}: {v}" for k, v in files.items()) + f"\nroot={root}", language="text")

    # (d) 🚀 출판(Publish) — 내부 자동 병합 → 디스패치 → 상태 버튼
    st.divider()
    repo_full = st.secrets.get("GITHUB_REPO", "")
    token     = st.secrets.get("GITHUB_TOKEN", "")
    ref       = st.secrets.get("GITHUB_BRANCH", "main")
    workflow  = st.secrets.get("GITHUB_WORKFLOW", "publish-prompts.yml")
    disabled  = not (repo_full and "/" in str(repo_full) and token)

    clicked = st.button("🚀 출판(Publish)", type="primary",
                        disabled=disabled, use_container_width=True,
                        help=None if not disabled else "GITHUB_REPO와 GITHUB_TOKEN 시크릿이 필요합니다.")
    if clicked:
        y = _build_yaml_for_publish()  # ✅ 항상 내부 병합
        okv, msgs = _validate_yaml_text(y)
        if not okv:
            st.error("스키마 검증 실패 — 필드 내용을 확인하세요.")
            if msgs: st.write("\n".join(f"- {m}" for m in msgs))
        else:
            try:
                owner, repo = str(repo_full).split("/", 1)
                input_key = st.session_state.get(S_PUB_INPUT_KEY)
                _ = _dispatch_workflow(owner=owner, repo=repo, workflow=workflow,
                                       ref=ref, token=token, yaml_text=y, input_key=input_key)
                st.session_state[S_PUB_STATE] = "running"
                st.session_state[S_PUB_DISPATCH_AT] = time.time()
                st.session_state[S_PUB_RUN_ID] = None
                st.session_state[S_PUB_RUN_URL] = None
                st.toast("출판 요청 전송 — Actions에서 처리 중입니다.", icon="⌛")
            except Exception as exc:
                st.session_state[S_PUB_STATE] = "error"
                st.exception(exc)

    _render_status_button()

    # (선택) YAML 미리보기(읽기 전용)
    with st.expander("고급: 출판용 YAML 미리보기(읽기 전용)", expanded=False):
        st.code(_build_yaml_for_publish(), language="yaml")

    # 폴링 유지
    if st.session_state.get(S_PUB_STATE) == "running":
        if repo_full and "/" in str(repo_full):
            owner, repo = str(repo_full).split("/", 1)
            _handle_publish_state(owner, repo, workflow, ref, token)

    # 플래시 메시지(1회성)
    ok = st.session_state.pop("_flash_success", None)
    er = st.session_state.pop("_flash_error",   None)
    if ok: st.success(ok)
    if er: st.error(er)


if __name__ == "__main__":
    main()
# [APUB‑V4] END: FILE src/ui/admin_prompt.py
