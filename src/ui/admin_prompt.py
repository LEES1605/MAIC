# [AP-KANON-STATUS] START: src/ui/admin_prompt.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import base64
import json
import time
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

# ---- 내부 상태 키 (출판 상태 관리) ----------------------------------------------
S_PUB_STATE       = "_PUBLISH_STATE"         # "idle" | "running" | "done" | "error"
S_PUB_DISPATCH_AT = "_PUBLISH_DISPATCH_AT"   # float(ts)
S_PUB_LAST_STATE  = "_PUBLISH_LAST_STATE"    # 이전 상태(토스트 분기)
S_PUB_RUN_URL     = "_PUBLISH_RUN_URL"       # 마지막 런 URL
S_PUB_NEXT_POLL   = "_PUBLISH_NEXT_POLL"     # 다음 폴링 시각
S_PUB_INPUT_KEY   = "_publish_input_key"     # UI에서 선택된 입력키

# ======================================================================================
# 정규화/파서 유틸 (한국어/영문/약어 라벨 → grammar/sentence/passage)
# ======================================================================================
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
    if t in ("pt","mn","mina"):
        return "sentence" if t != "pt" else "grammar"
    return ""

# ======================================================================================
# 파일 탐색 / 파서 (release/assets/prompts.yaml → UI 키로 추출)
# ======================================================================================
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

def _strip_persona_prefix(text: str, persona: str) -> str:
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
    out = {K_PERSONA:"", K_GRAMMAR:"", K_SENTENCE:"", K_PASSAGE:""}

    # 0) 페르소나 선추출
    def _maybe_persona(k: Any, v: Any) -> bool:
        kk = str(k or "").strip().lower()
        if kk in {"persona","common","profile","system","페르소나","공통","프로필"}:
            out[K_PERSONA] = _coerce_yaml_to_text(v)
            return True
        return False
    for k, v in (doc or {}).items():
        if _maybe_persona(k, v): continue
    for nested in ("pt","mn","mina"):
        nv = doc.get(nested)
        if isinstance(nv, dict) and not out[K_PERSONA]:
            sys_txt = nv.get("system")
            if isinstance(sys_txt, str) and sys_txt.strip():
                out[K_PERSONA] = sys_txt
    persona = out[K_PERSONA]

    def _assign(canon: str, payload: Any) -> None:
        if not canon: return
        raw = payload
        txt = _coerce_yaml_to_text(raw)
        if isinstance(raw, dict):
            has_direct = any(isinstance(raw.get(k), str) and raw.get(k).strip() for k in ("prompt","text"))
            if not has_direct:
                txt = _strip_persona_prefix(txt, persona)
        if not txt: return
        if canon == "grammar":  out[K_GRAMMAR]  = txt
        if canon == "sentence": out[K_SENTENCE] = txt
        if canon == "passage":  out[K_PASSAGE]  = txt

    # 1) 얕은 스캔
    for k, v in (doc or {}).items():
        if _maybe_persona(k, v): continue
        _assign(_canon_mode_key(k), v)

    # 2) mn/pt 보정
    mn = doc.get("mn") or doc.get("mina")
    if isinstance(mn, dict):
        for nk, nv in mn.items(): _assign(_canon_mode_key(nk), nv)
    pt = doc.get("pt") if isinstance(doc.get("pt"), dict) else None
    if isinstance(pt, dict) and not out[K_GRAMMAR]:
        for k in ("grammar","prompt","text","full"):
            if k in pt: _assign("grammar", pt[k]); break

    # 3) modes 섹션
    for key in ("modes","모드","mode_prompts","modeprompts","prompts_by_mode"):
        sect = doc.get(key)
        if isinstance(sect, dict):
            for mk, mv in sect.items(): _assign(_canon_mode_key(mk), mv)
        elif isinstance(sect, list):
            for e in sect:
                if not isinstance(e, dict): continue
                label = e.get("key") or e.get("label") or e.get("name") or e.get("라벨")
                _assign(_canon_mode_key(label), e)

    # 4) 제한 재귀(≤3)
    def _walk(node: Any, d=0):
        if d >= 3: return
        if isinstance(node, dict):
            for k, v in node.items():
                if _maybe_persona(k, v): continue
                _assign(_canon_mode_key(k), v); _walk(v, d+1)
        elif isinstance(node, list):
            for it in node: _walk(it, d+1)
    _walk(doc)

    return out

def _load_prompts_from_release() -> tuple[Dict[str,str], Path]:
    p = _resolve_release_prompts_file()
    if not p:
        raise FileNotFoundError("prompts.yaml을 release/assets 또는 프로젝트 루트에서 찾지 못했습니다.")
    with p.open("r", encoding="utf-8") as f:
        y = yaml.safe_load(f) or {}
    return _extract_prompts(y), p

# ======================================================================================
# 프리필 핸드셰이크 (콜백 경고 없이 값 주입)
# ======================================================================================
def _apply_pending_prefill() -> None:
    ss = st.session_state
    data = ss.pop("_PREFILL_PROMPTS", None)
    if isinstance(data, dict):
        ss[K_PERSONA]  = data.get(K_PERSONA,  "")
        ss[K_GRAMMAR]  = data.get(K_GRAMMAR,  "")
        ss[K_SENTENCE] = data.get(K_SENTENCE, "")
        ss[K_PASSAGE]  = data.get(K_PASSAGE,  "")

# ======================================================================================
# 저장/출판 유틸
# ======================================================================================
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
    d = json.loads(json.dumps(y))
    ok_modes = isinstance(d.get("modes"), list) and len(d["modes"]) > 0
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

# ======================================================================================
# GitHub Workflow — inputs 자동탐지 + 디스패치 + 상태 폴링
# ======================================================================================
def _gh_headers(token: Optional[str]) -> Dict[str, str]:
    h = {"Accept": "application/vnd.github+json"}
    if token: h["Authorization"] = f"Bearer {token}"
    return h

def _fetch_workflow_yaml(owner: str, repo: str, workflow: str, ref: str, token: Optional[str]) -> Optional[str]:
    headers = _gh_headers(token)
    # 1) actions/workflows로 path 알아보기
    try:
        r = req.get(f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}",
                    headers=headers, timeout=10)
        if r.ok:
            path = r.json().get("path")
            if isinstance(path, str) and path:
                r2 = req.get(f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={ref}",
                             headers=headers, timeout=10)
                if r2.ok:
                    js = r2.json()
                    if js.get("encoding") == "base64":
                        return base64.b64decode(js["content"].encode("utf-8")).decode("utf-8", "ignore")
    except Exception:
        pass
    # 2) 직접 경로 추정 시도
    try:
        r3 = req.get(f"https://api.github.com/repos/{owner}/{repo}/contents/.github/workflows/{workflow}?ref={ref}",
                     headers=headers, timeout=10)
        if r3.ok:
            js = r3.json()
            if js.get("encoding") == "base64":
                return base64.b64decode(js["content"].encode("utf-8")).decode("utf-8", "ignore")
    except Exception:
        pass
    return None

def _discover_inputs(owner: str, repo: str, workflow: str, ref: str, token: Optional[str]) -> List[str]:
    try:
        yml = _fetch_workflow_yaml(owner, repo, workflow, ref, token) or ""
        y = yaml.safe_load(yml) or {}
        on = y.get("on")
        if isinstance(on, dict):
            wd = on.get("workflow_dispatch")
            if isinstance(wd, dict):
                ins = wd.get("inputs") or {}
                if isinstance(ins, dict):
                    return [k for k in ins.keys() if isinstance(k, str)]
        elif isinstance(on, list):
            # ['workflow_dispatch', ...] → 입력 없음
            return []
    except Exception:
        pass
    return []

def _dispatch_workflow(owner: str, repo: str, workflow: str, ref: str,
                       token: str, yaml_text: str, input_key: Optional[str]) -> Dict[str, Any]:
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
    headers = _gh_headers(token)

    # 1차 시도: 선택된 입력키 사용(있다면)
    payload: Dict[str, Any] = {"ref": ref}
    if input_key:
        payload["inputs"] = {input_key: yaml_text}
    r = req.post(url, headers=headers, json=payload, timeout=15)
    if 200 <= r.status_code < 300:
        return {"status": r.status_code, "detail": "ok"}

    # 폴백: 422 Unexpected inputs → 입력 없이 재시도
    try:
        js = r.json() if r.content else {}
    except Exception:
        js = {}
    if r.status_code == 422 and "unexpected" in (js.get("message","").lower()):
        r2 = req.post(url, headers=headers, json={"ref": ref}, timeout=15)
        if 200 <= r2.status_code < 300:
            return {"status": r2.status_code, "detail": "ok (fallback: no inputs)"}
        raise RuntimeError(f"workflow dispatch 실패(status={r2.status_code}): {r2.text}")
    raise RuntimeError(f"workflow dispatch 실패(status={r.status_code}): {js or r.text}")

def _query_runs(owner: str, repo: str, workflow: str, ref: str, token: Optional[str]) -> List[Dict[str, Any]]:
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

def _pick_recent_run(runs: List[Dict[str, Any]], since_ts: float) -> Optional[Dict[str, Any]]:
    # since_ts 이후(약간의 지연 허용)로 생성된 가장 최근 run을 선택
    for run in runs:
        try:
            created = run.get("created_at")  # '2025-09-21T00:00:00Z'
            if not created:  # 방어
                continue
            # 느슨히: 최근 N개 중 첫 번째를 채택(실무에선 ISO 파싱 추천)
            return run
        except Exception:
            continue
    return runs[0] if runs else None

def _poll_workflow(owner: str, repo: str, workflow: str, ref: str,
                   token: Optional[str], since_ts: float) -> Tuple[str, Optional[str]]:
    """
    반환: ("running" | "done" | "error", run_html_url | None)
    """
    runs = _query_runs(owner, repo, workflow, ref, token)
    if not runs:
        return "running", None  # 디스패치 직후엔 빈 목록이 흔함

    run = _pick_recent_run(runs, since_ts) or {}
    status = (run.get("status") or "").lower()            # queued | in_progress | completed
    conclusion = (run.get("conclusion") or "").lower()    # success | failure | cancelled | neutral...
    url = run.get("html_url")

    if status != "completed":
        return "running", url
    if conclusion == "success":
        return "done", url
    return "error", url

# ======================================================================================
# UI: 상태 버튼(🟡/🟢) + 자동 폴링
# ======================================================================================
def _inject_status_css_once() -> None:
    if st.session_state.get("_status_css_v1"):
        return
    st.session_state["_status_css_v1"] = True
    st.markdown("""
<style>
  .status-wrap { display:flex; align-items:center; gap:8px; margin-top:6px; }
  .status-btn {
    cursor: default; border:0; padding:8px 12px; border-radius:10px; font-weight:800;
    color:#111; box-shadow:0 1px 2px rgba(0,0,0,.08);
  }
  .status-btn.running { background:#FFE083; }   /* 노란색 */
  .status-btn.done    { background:#34D399; color:#fff; } /* 초록색 */
  .status-btn.error   { background:#EF4444; color:#fff; } /* 빨강(실패) */
  .status-hint { font-size:12px; color:#555; }
</style>
    """, unsafe_allow_html=True)

def _render_status_button() -> None:
    _inject_status_css_once()
    st.session_state.setdefault(S_PUB_STATE, "idle")
    state = st.session_state[S_PUB_STATE]
    url = st.session_state.get(S_PUB_RUN_URL)

    label = "대기"
    klass = ""
    if state == "running":
        label = "🟡 처리중..."
        klass = "running"
    elif state == "done":
        label = "🟢 처리완료"
        klass = "done"
    elif state == "error":
        label = "🔴 실패"
        klass = "error"

    with st.container():
        st.markdown(
            f'<div class="status-wrap"><button class="status-btn {klass}">{label}</button>'
            + (f'<a href="{url}" target="_blank" class="status-hint">Actions 열기</a>' if url else "")
            + '</div>',
            unsafe_allow_html=True,
        )

def _tick_auto_poll(interval: float = 5.0) -> None:
    """running 상태에서만 interval 초마다 부드럽게 rerun."""
    now = time.time()
    nxt = float(st.session_state.get(S_PUB_NEXT_POLL, 0.0) or 0.0)
    if now < nxt:
        return
    st.session_state[S_PUB_NEXT_POLL] = now + max(2.0, float(interval))
    # 아주 짧은 sleep으로 깜빡임 완화
    time.sleep(0.4)
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()  # 구버전 호환
        except Exception:
            pass

def _handle_publish_state(owner: str, repo: str, workflow: str, ref: str, token: Optional[str]) -> None:
    """페이지 렌더 시점마다 상태를 평가/전이 + UI/토스트."""
    ss = st.session_state
    ss.setdefault(S_PUB_STATE, "idle")
    cur = ss[S_PUB_STATE]
    prev = ss.get(S_PUB_LAST_STATE)

    # 전이 감지 → 토스트
    if prev and prev != cur:
        if cur == "done":
            st.toast("출판 완료!", icon="✅")
        elif cur == "error":
            st.toast("출판 실패. Actions 로그를 확인하세요.", icon="❌")
    ss[S_PUB_LAST_STATE] = cur

    if cur != "running":
        return

    # running → GitHub Actions 폴링
    try:
        state, url = _poll_workflow(owner, repo, workflow, ref, token, since_ts=float(ss.get(S_PUB_DISPATCH_AT, 0.0) or 0.0))
        if url:
            ss[S_PUB_RUN_URL] = url
        if state == "running":
            _tick_auto_poll(6.0)   # 6초 간격 자동 새로고침
        else:
            ss[S_PUB_STATE] = state  # done | error
            # 다음 턴에서 토스트가 뜨도록 유지
    except Exception:
        ss[S_PUB_STATE] = "error"

# ======================================================================================
# 페이지 본문
# ======================================================================================
def main() -> None:
    render_sidebar()
    _apply_pending_prefill()

    # ---- 상태 메시지(1회성)
    ok = st.session_state.pop("_flash_success", None)
    er = st.session_state.pop("_flash_error",   None)
    if ok: st.success(ok)
    if er: st.error(er)

    # ---- 상태 박스(시크릿/워크플로 검사 + 입력키 자동탐지)
    with st.container(border=True):
        st.subheader("🔍 상태 점검", divider="gray")

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

        # 워크플로우 inputs 자동 탐지
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
                options=keys,
                index=keys.index(chosen_key),
                key=S_PUB_INPUT_KEY,
                help="GitHub Workflow의 workflow_dispatch.inputs 중 하나를 선택하세요.",
            )
        else:
            st.caption("워크플로우 입력이 정의되어 있지 않습니다 → 입력 없이 디스패치합니다.")

    # ---- 편집 UI (세로 배열)
    st.markdown("### ① 페르소나(공통)")
    st.text_area("모든 모드에 공통 적용", key=K_PERSONA, height=160, placeholder="페르소나 텍스트...")

    st.markdown("### ② 모드별 프롬프트(지시/규칙)")
    st.text_area("문법(Grammar) 프롬프트",  key=K_GRAMMAR,  height=220, placeholder="문법 모드 지시/규칙...")
    st.text_area("문장(Sentence) 프롬프트", key=K_SENTENCE, height=220, placeholder="문장 모드 지시/규칙...")
    st.text_area("지문(Passage) 프롬프트",  key=K_PASSAGE,  height=220, placeholder="지문 모드 지시/규칙...")

    # ---- 액션
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

    # (d) 🚀 출판(Publish) + 상태 버튼(🟡/🟢)
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
                    # 상태 전이: running
                    st.session_state[S_PUB_STATE] = "running"
                    st.session_state[S_PUB_DISPATCH_AT] = time.time()
                    st.session_state[S_PUB_RUN_URL] = None
                    st.toast("출판 요청을 전송했습니다. Actions에서 처리 중입니다.", icon="⌛")
                    # 즉시 한 번 폴링하고, 필요 시 자동 새로고침
                    _handle_publish_state(owner, repo, workflow, ref, token)
                except Exception as exc:
                    st.session_state[S_PUB_STATE] = "error"
                    st.exception(exc)

        # 현재 상태 표시(버튼 한 개처럼 보이게 바로 옆에 렌더)
        _render_status_button()

    # YAML 미리보기/편집
    st.markdown("### YAML 미리보기/편집")
    st.text_area("YAML", key="_merged_yaml", height=320, placeholder="여기에 병합된 YAML이 표시됩니다. 필요하면 직접 수정하세요.")
    if st.session_state.get("_last_prompts_source"):
        st.caption(f"최근 소스: {st.session_state['_last_prompts_source']}")

    # 페이지 하단에서도 러닝이면 주기 폴링
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
# [AP-KANON-STATUS] END
