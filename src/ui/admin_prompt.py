# [AP-KANON-FINAL] START: src/ui/admin_prompt.py — ko/en canonicalization + robust extract + prefill handshake
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import yaml
import streamlit as st

# ✅ 진짜 사이드바(Single Source of Truth)
try:
    from .utils.sider import render_sidebar
except Exception:
    from src.ui.utils.sider import render_sidebar  # fallback

# ---- SSOT: UI Widget Keys ----------------------------------------------------
K_PERSONA  = "persona_text"
K_GRAMMAR  = "grammar_prompt"
K_SENTENCE = "sentence_prompt"
K_PASSAGE  = "passage_prompt"

# ---- canon helpers -----------------------------------------------------------
def _norm_token(x: Any) -> str:
    """공백/대소문자/구두점 영향 최소화. (한글 포함)"""
    s = str(x or "").strip().lower()
    return "".join(ch for ch in s if ch.isalnum())

def _coerce_yaml_to_text(v: Any) -> str:
    """문자열이 아니어도 보기 좋게 문자열화(dict/list 지원)."""
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

# —— 1순위: core.modes 유틸이 있으면 적극 사용(있을 수도, 없을 수도)
def _canon_via_core_modes(label: str) -> Optional[str]:
    try:
        import src.core.modes as _m
    except Exception:
        return None
    # 가능한 여러 이름을 시도 (존재하지 않으면 무시)
    for cand in ("canon_mode", "canon_key", "normalize_mode", "normalize_key", "find_mode_by_label"):
        fn = getattr(_m, cand, None)
        if not callable(fn):
            continue
        try:
            res = fn(label)
        except Exception:
            continue
        # 문자열 또는 .key 보유 객체 모두 수용
        if isinstance(res, str):
            s = res.strip().lower()
            if s in ("grammar", "sentence", "passage"):
                return s
            # 한국어 레이블을 돌려주는 구현일 수도 있음
            if s in ("문법", "문장", "지문"):
                return {"문법": "grammar", "문장": "sentence", "지문": "passage"}[s]
        key = getattr(res, "key", None)
        if isinstance(key, str) and key in ("grammar", "sentence", "passage"):
            return key
    return None

# —— 2순위: 내장 시소러스 + 부분일치(“문장구조분석” 등) ---------------------------
_SYNONYMS = {
    "grammar": {
        "grammar", "pt", "문법", "문법설명", "문법해설", "문법규칙", "품사", "품사판별",
        "문장성분", "문법검사", "문법풀이", "문법 문제", "문법해석",
    },
    "sentence": {
        "sentence", "sent", "문장", "문장분석", "문장해석", "문장구조", "문장구조분석",
        "문장성분분석", "문장완성", "문장구조해석", "문장구조파악",
    },
    "passage": {
        "passage", "para", "지문", "지문분석", "독해", "독해지문", "독해분석", "지문해석",
        "독해 문제", "장문", "장문독해",
    },
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
    # 1) core.modes 우선
    via_core = _canon_via_core_modes(s)
    if via_core:
        return via_core
    # 2) 동의어 정규화(정확일치)
    t = _norm_token(s)
    for key, names in _SYNONYMS.items():
        for name in names:
            if _norm_token(name) == t:
                return key
    # 3) 부분일치 힌트(‘문장구조분석’, ‘독해 문제’ 등)
    low = s.lower()
    for key, hints in _SUBSTR_HINTS:
        if any(h in low for h in hints):
            return key
    # 4) 영문 축약
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

# ---- robust extractor --------------------------------------------------------
def _extract_prompts(doc: Dict[str, Any]) -> Dict[str, str]:
    """
    다양한 YAML 스키마를 **견고하게** 수용해 UI 키로 매핑한다.
    - Top-level 한글/영문 라벨(문장구조분석/문법설명/지문분석 등) → 정규화
    - Nested: { mn:{sentence,passage} }, { pt:{grammar/prompt/...} } 등
    - List/Dict: { modes:[...]} 또는 { modes:{...} } / { 모드: ... } / 기타 유사 키도 재귀 스캔
    - 마지막 수단: 부분일치/시소러스로 추정 매핑
    """
    out = {K_PERSONA: "", K_GRAMMAR: "", K_SENTENCE: "", K_PASSAGE: ""}

    def _assign(canon: str, payload: Any) -> None:
        if not canon:
            return
        text = _coerce_yaml_to_text(payload)
        if not text:
            return
        if canon == "grammar":
            out[K_GRAMMAR] = text
        elif canon == "sentence":
            out[K_SENTENCE] = text
        elif canon == "passage":
            out[K_PASSAGE] = text

    def _maybe_persona(k: Any, v: Any) -> bool:
        kk = str(k or "").strip().lower()
        if kk in {"persona", "common", "profile", "system", "페르소나", "공통", "프로필"}:
            out[K_PERSONA] = _coerce_yaml_to_text(v)
            return True
        return False

    # 1) 1차: 얕은 레벨 스캔
    for k, v in (doc or {}).items():
        if _maybe_persona(k, v):
            continue
        canon = _canon_mode_key(k)
        if canon:
            _assign(canon, v)

    # 2) mn/pt 보정
    mn = doc.get("mn") or doc.get("mina")
    if isinstance(mn, dict):
        for nk, nv in mn.items():
            _assign(_canon_mode_key(nk), nv)
    pt = doc.get("pt") if isinstance(doc.get("pt"), dict) else None
    if isinstance(pt, dict) and not out[K_GRAMMAR]:
        # pt 내부에서 문법 텍스트 찾기
        for k in ("grammar", "prompt", "text", "full", "system", "설명"):
            if k in pt:
                _assign("grammar", pt[k])
                break

    # 3) modes 섹션: dict/list/한글키 모두 수용
    for key in ("modes", "모드", "mode_prompts", "modeprompts", "prompts_by_mode"):
        sect = doc.get(key)
        if isinstance(sect, dict):
            for mk, mv in sect.items():
                canon = _canon_mode_key(mk)
                if canon:
                    _assign(canon, mv)
        elif isinstance(sect, list):
            for entry in sect:
                if not isinstance(entry, dict):
                    continue
                label = entry.get("key") or entry.get("label") or entry.get("name") or entry.get("라벨")
                canon = _canon_mode_key(label)
                # payload 후보 우선순위
                text = None
                for tk in ("prompt", "text", "full", "system", "value", "content", "지시", "규칙"):
                    if isinstance(entry.get(tk), str) and entry.get(tk).strip():
                        text = entry.get(tk)
                        break
                if text is None:
                    text = entry
                if canon:
                    _assign(canon, text)

    # 4) 2차: 재귀 스캔(안전한 제한, 깊이≤3)
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

# ---- prefill handshake (콜백 rerun 경고 없이 즉시 반영) ----------------------
def _apply_pending_prefill() -> None:
    ss = st.session_state
    data = ss.pop("_PREFILL_PROMPTS", None)
    if isinstance(data, dict):
        ss[K_PERSONA]  = data.get(K_PERSONA,  "")
        ss[K_GRAMMAR]  = data.get(K_GRAMMAR,  "")
        ss[K_SENTENCE] = data.get(K_SENTENCE, "")
        ss[K_PASSAGE]  = data.get(K_PASSAGE,  "")

# ---- Page Main ---------------------------------------------------------------
def main() -> None:
    render_sidebar()

    # (1) 프리필 예약분 적용(위젯 생성 전에)
    _apply_pending_prefill()

    # (2) 플래시
    ok = st.session_state.pop("_flash_success", None)
    er = st.session_state.pop("_flash_error",   None)
    if ok: st.success(ok)
    if er: st.error(er)

    # (3) 상태 점검
    with st.container(border=True):
        st.subheader("🔍 상태 점검", divider="gray")
        p = _resolve_release_prompts_file()
        if p: st.success(f"경로 OK — prompts.yaml 확인: {p}")
        else: st.warning("prompts.yaml을 release/assets 또는 루트에서 찾지 못했습니다.")

    # (4) 편집 UI — SSOT 키
    st.markdown("### ① 페르소나(공통)")
    st.text_area("모든 모드에 공통 적용", key=K_PERSONA, height=160, placeholder="페르소나 텍스트...")

    st.markdown("### ② 모드별 프롬프트(지시/규칙)")
    c1, c2, c3 = st.columns(3)
    with c1: st.text_area("문법(Grammar) 프롬프트", key=K_GRAMMAR,  height=220, placeholder="문법 모든 지시/규칙...")
    with c2: st.text_area("문장(Sentence) 프롬프트", key=K_SENTENCE, height=220, placeholder="문장 모든 지시/규칙...")
    with c3: st.text_area("지문(Passage) 프롬프트",  key=K_PASSAGE,  height=220, placeholder="지문 모든 지시/규칙...")

    # (5) 액션
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
# [AP-KANON-FINAL] END
