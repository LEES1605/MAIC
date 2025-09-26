# [F2] START: FILE src/ui/admin_prompt.py — sider-based admin prompt
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict
import json, yaml, streamlit as st

# ✅ 진짜 사이드바: utils/sider 사용
from src.ui.utils.sider import render_sidebar

# ---- 기본 Pages 네비 완전 숨김(보조) --------------------------------------------
def _hide_default_pages_nav() -> None:
    st.markdown(
        """
        <style>
          [data-testid="stSidebarNav"],
          section[data-testid="stSidebarNav"],
          nav[data-testid="stSidebarNav"],
          div[data-testid="stSidebarNav"] { display:none !important; height:0 !important; overflow:hidden !important; }
        </style>
        """, unsafe_allow_html=True
    )

# ---- UI Widget Keys (stable) --------------------------------------------------
K_GRAMMAR: str = "prompt_PT"
K_SENTENCE: str = "prompt_MN_sentence"
K_PASSAGE: str = "prompt_MN_passage"

# ---- Loader helpers -----------------------------------------------------------
def _resolve_release_prompts_file() -> Path | None:
    base = Path(st.session_state.get("_release_dir", "release")).resolve()
    for p in [base/"assets/prompts.yaml", base/"prompts.yaml",
              Path("assets/prompts.yaml").resolve(), Path("prompts.yaml").resolve()]:
        try:
            if p.exists() and p.is_file(): return p
        except Exception: continue
    return None

def _coerce_yaml_to_text(v: Any) -> str:
    if v is None: return ""
    if isinstance(v, str): return v
    if isinstance(v, dict):
        for k in ("full","system","text","prompt"):
            if isinstance(v.get(k), str): return v[k]
        return json.dumps(v, ensure_ascii=False, indent=2)
    if isinstance(v, (list, tuple)): return "\n".join(str(x) for x in v)
    return str(v)

def _extract_prompts(doc: Dict[str, Any]) -> Dict[str, str]:
    d = {(k.lower() if isinstance(k,str) else k): v for k,v in (doc or {}).items()}
    out = {K_GRAMMAR:"", K_SENTENCE:"", K_PASSAGE:""}
    alias = {
        "grammar":K_GRAMMAR, "pt":K_GRAMMAR, "grammar_prompt":K_GRAMMAR,
        "sentence":K_SENTENCE, "mn_sentence":K_SENTENCE, "sentence_prompt":K_SENTENCE,
        "passage":K_PASSAGE, "mn_passage":K_PASSAGE, "passage_prompt":K_PASSAGE,
    }
    for yk, sk in alias.items():
        if yk in d: out[sk] = _coerce_yaml_to_text(d[yk])
    mn = d.get("mn") or d.get("mina")
    if isinstance(mn, dict):
        if "sentence" in mn: out[K_SENTENCE] = _coerce_yaml_to_text(mn["sentence"])
        if "passage"  in mn: out[K_PASSAGE]  = _coerce_yaml_to_text(mn["passage"])
    pt = d.get("pt") if isinstance(d.get("pt"), dict) else None
    if isinstance(pt, dict) and not out[K_GRAMMAR]:
        for k in ("grammar","prompt","text","full","system"):
            if k in pt: out[K_GRAMMAR] = _coerce_yaml_to_text(pt[k]); break
    return out

def _load_prompts_from_release() -> tuple[Dict[str,str], Path]:
    p = _resolve_release_prompts_file()
    if not p: raise FileNotFoundError("prompts.yaml을 release/assets에서 찾지 못했습니다.")
    with p.open("r", encoding="utf-8") as f: y = yaml.safe_load(f) or {}
    return _extract_prompts(y), p

def on_click_load_latest_prompts() -> None:
    try:
        texts, src = _load_prompts_from_release()
        st.session_state[K_GRAMMAR] = texts[K_GRAMMAR]
        st.session_state[K_SENTENCE] = texts[K_SENTENCE]
        st.session_state[K_PASSAGE]  = texts[K_PASSAGE]
        st.session_state["_last_prompts_source"] = str(src)
        st.session_state["_flash_success"] = f"릴리스에서 프롬프트를 불러왔습니다: {src}"
        st.rerun()
    except FileNotFoundError as e:
        st.session_state["_flash_error"] = str(e); st.rerun()
    except Exception:
        st.session_state["_flash_error"] = "프롬프트 로딩 중 오류가 발생했습니다."; st.rerun()

# ---- Main --------------------------------------------------------------------
def main() -> None:
    _hide_default_pages_nav()
    render_sidebar()

    # 플래시
    ok = st.session_state.pop("_flash_success", None)
    er = st.session_state.pop("_flash_error", None)
    if ok: st.success(ok)
    if er: st.error(er)

    with st.container(border=True):
        st.subheader("🔍 상태 점검", divider="gray")
        p = _resolve_release_prompts_file()
        if p: st.success(f"경로 OK — prompts.yaml 확인: {p}")
        else: st.warning("prompts.yaml을 release/assets 또는 루트에서 찾지 못했습니다.")

    st.markdown("### ① 페르소나(공통)")
    st.text_area("모든 모드에 공통 적용", key="persona_text", height=160, placeholder="페르소나 텍스트…")

    st.markdown("### ② 모드별 프롬프트(지시/규칙)")
    c1, c2, c3 = st.columns(3)
    with c1: st.text_area("문법(Grammar) 프롬프트", key=K_GRAMMAR, height=220, placeholder="문법 모든 지시/규칙…")
    with c2: st.text_area("문장(Sentence) 프롬프트", key=K_SENTENCE, height=220, placeholder="문장 모든 지시/규칙…")
    with c3: st.text_area("지문(Passage) 프롬프트",  key=K_PASSAGE,  height=220, placeholder="지문 모든 지시/규칙…")

    st.markdown("### ③ 액션")
    st.button("🧲 최신 프롬프트 불러오기(릴리스 우선)", on_click=on_click_load_latest_prompts)
    if st.session_state.get("_last_prompts_source"):
        st.caption(f"최근 소스: {st.session_state['_last_prompts_source']}")

if __name__ == "__main__":
    main()
# [F2] END: FILE src/ui/admin_prompt.py
