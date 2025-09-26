# [AP-KANON] START: FILE src/ui/admin_prompt.py — ko/en mode label canonicalization + prefill handshake
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import yaml
import streamlit as st

# ✅ 진짜 사이드바
try:
    from .utils.sider import render_sidebar
except Exception:
    from src.ui.utils.sider import render_sidebar  # fallback

# ---- SSOT: UI Widget Keys ----------------------------------------------------
K_PERSONA  = "persona_text"
K_GRAMMAR  = "grammar_prompt"
K_SENTENCE = "sentence_prompt"
K_PASSAGE  = "passage_prompt"

# ---- tiny utils --------------------------------------------------------------
def _norm_token(x: Any) -> str:
    """공백/대소문자/구두점 영향 줄인 토큰(한글 대응)."""
    s = str(x or "").strip().lower()
    # 숫자/영문/한글만 남기고 공백 제거
    return "".join(ch for ch in s if ch.isalnum())

def _coerce_yaml_to_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        for k in ("prompt", "text", "full", "system", "value", "content"):
            if isinstance(v.get(k), str) and v[k].strip():
                return v[k]
        return json.dumps(v, ensure_ascii=False, indent=2)
    if isinstance(v, (list, tuple)):
        return "\n".join(str(x) for x in v)
    return str(v)

def _canon_mode_key(label_or_key: Any) -> str:
    """
    입력(한국어 라벨/영문키/약어)을 표준 모드 키('grammar'|'sentence'|'passage')로 변환.
    1순위: src.core.modes가 제공하는 정규화/검색 유틸
    2순위: 내장 시소러스
    """
    s = str(label_or_key or "").strip()
    if not s:
        return ""

    # 1) core.modes가 있으면 우선 사용(견고하게 여러 이름 시도)
    try:
        import src.core.modes as _m
        # find_mode_by_label(라벨→spec)
        fn = getattr(_m, "find_mode_by_label", None)
        if callable(fn):
            spec = fn(s)
            key = getattr(spec, "key", None)
            if isinstance(key, str) and key in ("grammar", "sentence", "passage"):
                return key
        # 추가적인 정규화 함수가 있으면 시도
        for cand in ("canon_mode", "canon_key", "canon_label", "normalize_mode", "normalize_key", "normalize_label"):
            g = getattr(_m, cand, None)
            if callable(g):
                try:
                    res = g(s)
                    if isinstance(res, str) and res in ("grammar", "sentence", "passage"):
                        return res
                    key = getattr(res, "key", None)
                    if isinstance(key, str) and key in ("grammar", "sentence", "passage"):
                        return key
                except Exception:
                    pass
    except Exception:
        pass

    # 2) 내장 시소러스(한국어/영문/약어)
    t = _norm_token(s)
    synonyms = {
        "grammar": {
            "grammar", "pt", "문법", "문법설명", "문법해설", "문법규칙", "품사", "문장성분", "문법검사"
        },
        "sentence": {
            "sentence", "sent", "문장", "문장분석", "문장해석", "문장구조", "문장구조분석", "문장구조해석",
            "문장구조분해", "문장구조파악", "문장구조분", "문장 구조 분석"
        },
        "passage": {
            "passage", "para", "지문", "지문분석", "독해", "독해지문", "독해분석", "지문해석"
        },
    }
    # 빠른 매칭: normalize 후 비교
    for key, names in synonyms.items():
        for name in names:
            if _norm_token(name) == t:
                return key
    return ""  # 미매칭

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

def _extract_prompts(doc: Dict[str, Any]) -> Dict[str, str]:
    """
    다양한 YAML 스키마를 허용해 'UI 키'로 매핑한다.
    - Top-level: {grammar/sentence/passage} + 한국어 라벨도 허용
    - Nested: {mn:{sentence/passage}}, {pt:{grammar/prompt/...}} 등
    - List: {modes:[{key|label|name, prompt|text|...}, ...]}
    """
    d = {(k.lower() if isinstance(k, str) else k): v for k, v in (doc or {}).items()}
    out = {K_PERSONA: "", K_GRAMMAR: "", K_SENTENCE: "", K_PASSAGE: ""}

    # 0) Persona / Common
    for yk in ("persona", "common", "profile", "system", "페르소나", "공통", "프로필"):
        if yk in d:
            out[K_PERSONA] = _coerce_yaml_to_text(d[yk])
            break

    # 1) Top-level keys: 한국어 라벨 포함 → 정규화
    for raw_key, val in list(d.items()):
        canon = _canon_mode_key(raw_key)
        if not canon:
            continue
        text = _coerce_yaml_to_text(val)
        if canon == "grammar":
            out[K_GRAMMAR] = text
        elif canon == "sentence":
            out[K_SENTENCE] = text
        elif canon == "passage":
            out[K_PASSAGE] = text

    # 2) Nested: mn / pt 계열 보정
    mn = d.get("mn") or d.get("mina")
    if isinstance(mn, dict):
        for nk, nv in mn.items():
            canon = _canon_mode_key(nk)
            if not canon:
                continue
            text = _coerce_yaml_to_text(nv)
            if canon == "sentence":
                out[K_SENTENCE] = text
            elif canon == "passage":
                out[K_PASSAGE] = text

    pt = d.get("pt") if isinstance(d.get("pt"), dict) else None
    if isinstance(pt, dict) and not out[K_GRAMMAR]:
        # pt 내부에서 문법 텍스트 찾기
        for k in ("grammar", "prompt", "text", "full", "system", "설명"):
            if k in pt:
                out[K_GRAMMAR] = _coerce_yaml_to_text(pt[k])
                break

    # 3) List: modes
    modes: Optional[List[dict]] = None
    if isinstance(d.get("modes"), list):
        modes = d.get("modes")
    elif isinstance(d.get("모드"), list):
        modes = d.get("모드")
    if isinstance(modes, list):
        for m in modes:
            if not isinstance(m, dict):
                continue
            label = m.get("key") or m.get("label") or m.get("name") or m.get("라벨")
            canon = _canon_mode_key(label)
            if not canon:
                continue
            text = None
            for tk in ("prompt", "text", "full", "system", "value", "content", "지시", "규칙"):
                if isinstance(m.get(tk), str) and m.get(tk).strip():
                    text = m.get(tk)
                    break
            if text is None:
                text = _coerce_yaml_to_text(m)
            if canon == "grammar":
                out[K_GRAMMAR] = text
            elif canon == "sentence":
                out[K_SENTENCE] = text
            elif canon == "passage":
                out[K_PASSAGE] = text

    return out

def _load_prompts_from_release() -> tuple[Dict[str, str], Path]:
    p = _resolve_release_prompts_file()
    if not p:
        raise FileNotFoundError("prompts.yaml을 release/assets 또는 프로젝트 루트에서 찾지 못했습니다.")
    with p.open("r", encoding="utf-8") as f:
        y = yaml.safe_load(f) or {}
    return _extract_prompts(y), p

# ---- Prefill handshake (콜백 rerun 경고 없이 즉시 반영) -----------------------------
def _apply_pending_prefill() -> None:
    ss = st.session_state
    data = ss.pop("_PREFILL_PROMPTS", None)
    if isinstance(data, dict):
        ss[K_PERSONA]  = data.get(K_PERSONA,  "")
        ss[K_GRAMMAR]  = data.get(K_GRAMMAR,  "")
        ss[K_SENTENCE] = data.get(K_SENTENCE, "")
        ss[K_PASSAGE]  = data.get(K_PASSAGE,  "")

# ---- Page Main -----------------------------------------------------------------------
def main() -> None:
    render_sidebar()

    # 1) 프리필 예약분 우선 반영(위젯 생성 전에)
    _apply_pending_prefill()

    # 2) 플래시
    ok = st.session_state.pop("_flash_success", None)
    er = st.session_state.pop("_flash_error",   None)
    if ok: st.success(ok)
    if er: st.error(er)

    # 3) 상태 점검
    with st.container(border=True):
        st.subheader("🔍 상태 점검", divider="gray")
        p = _resolve_release_prompts_file()
        if p: st.success(f"경로 OK — prompts.yaml 확인: {p}")
        else: st.warning("prompts.yaml을 release/assets 또는 루트에서 찾지 못했습니다.")

    # 4) 편집 UI (SSOT 키)
    st.markdown("### ① 페르소나(공통)")
    st.text_area("모든 모드에 공통 적용", key=K_PERSONA, height=160, placeholder="페르소나 텍스트...")

    st.markdown("### ② 모드별 프롬프트(지시/규칙)")
    c1, c2, c3 = st.columns(3)
    with c1: st.text_area("문법(Grammar) 프롬프트", key=K_GRAMMAR,  height=220, placeholder="문법 모든 지시/규칙...")
    with c2: st.text_area("문장(Sentence) 프롬프트", key=K_SENTENCE, height=220, placeholder="문장 모든 지시/규칙...")
    with c3: st.text_area("지문(Passage) 프롬프트",  key=K_PASSAGE,  height=220, placeholder="지문 모든 지시/규칙...")

    # 5) 액션
    st.markdown("### ③ 액션")
    if st.button("📥 최신 프롬프트 불러오기(릴리스 우선)", use_container_width=True, key="btn_fetch_prompts"):
        try:
            texts, src = _load_prompts_from_release()
            # 예약키에 저장 → rerun → 다음 런의 '위젯 생성 전'에 주입
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

    if st.session_state.get("_last_prompts_source"):
        st.caption(f"최근 소스: {st.session_state['_last_prompts_source']}")

if __name__ == "__main__":
    main()
# [AP-KANON] END: FILE src/ui/admin_prompt.py
