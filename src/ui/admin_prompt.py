# [A1] START: FILE src/ui/admin_prompt.py — clean version
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict
import json
import yaml
import streamlit as st

# ✅ 공통 사이드바(브랜치: fix/ui-sidebar-consistency-after-login) — 올바른 임포트 경로
from src.ui.nav import render_sidebar

# ---- UI Widget Keys (stable) ----
K_GRAMMAR: str = "prompt_PT"               # 문법(Grammar)
K_SENTENCE: str = "prompt_MN_sentence"     # 문장(Sentence)
K_PASSAGE: str = "prompt_MN_passage"       # 지문(Passage)

def _resolve_release_prompts_file() -> Path | None:
    """릴리스/에셋에서 prompts.yaml 탐색. 우선순위: <_release_dir>/assets > <_release_dir> > ./assets > ./"""
    base = Path(st.session_state.get("_release_dir", "release")).resolve()
    candidates = [
        base / "assets" / "prompts.yaml",
        base / "prompts.yaml",
        Path("assets/prompts.yaml").resolve(),
        Path("prompts.yaml").resolve(),
    ]
    for p in candidates:
        try:
            if p.exists() and p.is_file():
                return p
        except Exception:
            continue
    return None

def _coerce_yaml_to_text(value: Any) -> str:
    """문자열이 아니어도 보기 좋게 문자열화한다(dict/list 지원)."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("full", "system", "text", "prompt"):
            v = value.get(key)
            if isinstance(v, str):
                return v
        return json.dumps(value, ensure_ascii=False, indent=2)
    if isinstance(value, (list, tuple)):
        return "\n".join(str(x) for x in value)
    return str(value)

def _extract_prompts(yaml_data: Dict[str, Any]) -> Dict[str, str]:
    """여러 YAML 스키마를 허용해 3개 텍스트(문법/문장/지문)로 매핑한다."""
    data: Dict[str, Any] = {(k.lower() if isinstance(k, str) else k): v for k, v in (yaml_data or {}).items()}
    out: Dict[str, str] = {K_GRAMMAR: "", K_SENTENCE: "", K_PASSAGE: ""}

    # 1) 최상위 단일 키 매핑(여러 별칭 허용)
    mapping = {
        "grammar": K_GRAMMAR, "pt": K_GRAMMAR, "grammar_prompt": K_GRAMMAR,
        "sentence": K_SENTENCE, "mn_sentence": K_SENTENCE, "sentence_prompt": K_SENTENCE,
        "passage": K_PASSAGE, "mn_passage": K_PASSAGE, "passage_prompt": K_PASSAGE,
    }
    for yk, sk in mapping.items():
        if yk in data:
            out[sk] = _coerce_yaml_to_text(data[yk])

    # 2) { mn: { sentence, passage } }
    mn = data.get("mn") or data.get("mina")
    if isinstance(mn, dict):
        if "sentence" in mn:
            out[K_SENTENCE] = _coerce_yaml_to_text(mn["sentence"])
        if "passage" in mn:
            out[K_PASSAGE] = _coerce_yaml_to_text(mn["passage"])

    # 3) { pt: { grammar/prompt/text/... } }
    ptsec = data.get("pt") if isinstance(data.get("pt"), dict) else None
    if isinstance(ptsec, dict) and not out[K_GRAMMAR]:
        for k in ("grammar", "prompt", "text", "full", "system"):
            if k in ptsec:
                out[K_GRAMMAR] = _coerce_yaml_to_text(ptsec[k])
                break

    return out

def _load_prompts_from_release() -> tuple[Dict[str, str], Path]:
    """릴리스/에셋에서 YAML을 읽어 표준 3필드로 반환."""
    p = _resolve_release_prompts_file()
    if not p:
        raise FileNotFoundError("prompts.yaml을 release 또는 assets에서 찾지 못했습니다.")
    with p.open("r", encoding="utf-8") as f:
        y = yaml.safe_load(f) or {}
    texts = _extract_prompts(y)
    return texts, p

def on_click_load_latest_prompts() -> None:
    """버튼 핸들러: 세션 키에 값 주입 후 즉시 rerun."""
    try:
        texts, src = _load_prompts_from_release()
        st.session_state[K_GRAMMAR] = texts[K_GRAMMAR]
        st.session_state[K_SENTENCE] = texts[K_SENTENCE]
        st.session_state[K_PASSAGE]  = texts[K_PASSAGE]
        st.session_state["_last_prompts_source"] = str(src)
        st.session_state["_flash_success"] = f"릴리스에서 프롬프트를 불러왔습니다: {src}"
        st.rerun()
    except FileNotFoundError as e:
        st.session_state["_flash_error"] = str(e)
        st.rerun()
    except Exception:
        st.session_state["_flash_error"] = "프롬프트 로딩 중 오류가 발생했습니다."
        st.rerun()

def main() -> None:
    render_sidebar()

    # 플래시 메시지(1회성)
    _success = st.session_state.pop("_flash_success", None)
    _error = st.session_state.pop("_flash_error", None)
    if _success: st.success(_success)
    if _error:   st.error(_error)

    # 상태 점검(로컬/릴리스 경로 확인만 — 네트워크 의존 제거)
    with st.container(border=True):
        st.subheader("🔍 상태 점검", divider="gray")
        p = _resolve_release_prompts_file()
        if p:
            st.success(f"경로 OK — prompts.yaml 확인: {p}")
        else:
            st.warning("prompts.yaml을 release/assets 또는 프로젝트 루트에서 찾지 못했습니다.")

    st.markdown("### ① 페르소나(공통)")
    st.text_area("모든 모드에 공통 적용", key="persona_text", height=160, placeholder="페르소나 텍스트…")

    st.markdown("### ② 모드별 프롬프트(지시/규칙)")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.text_area("문법(Grammar) 프롬프트", key=K_GRAMMAR, height=220, placeholder="문법 모든 지시/규칙…")
    with c2:
        st.text_area("문장(Sentence) 프롬프트", key=K_SENTENCE, height=220, placeholder="문장 모든 지시/규칙…")
    with c3:
        st.text_area("지문(Passage) 프롬프트", key=K_PASSAGE,  height=220, placeholder="지문 모든 지시/규칙…")

    st.markdown("### ③ 액션")
    st.button("🧲 최신 프롬프트 불러오기(릴리스 우선)", on_click=on_click_load_latest_prompts)

    _last = st.session_state.get("_last_prompts_source")
    if _last:
        st.caption(f"최근 소스: {_last}")

if __name__ == "__main__":
    main()
# [A1] END: FILE src/ui/admin_prompt.py — clean version
