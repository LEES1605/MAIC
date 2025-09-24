# =============================== [01] future import — START ===========================
from __future__ import annotations
# ================================ [01] future import — END ============================

# =============================== [02] imports — START =================================
from pathlib import Path
from typing import Optional, Tuple
import json
import os

import yaml

try:
    import streamlit as st
except Exception:
    st = None

# 내부 노멀라이저
from src.ui.assist.prompt_normalizer import normalize_to_yaml
# ================================ [02] imports — END ==================================

# =============================== [03] helpers — START =================================
def _get_openai_key() -> Optional[str]:
    try:
        if st is not None and hasattr(st, "secrets"):
            k = st.secrets.get("OPENAI_API_KEY")
            if k:
                return str(k)
    except Exception:
        pass
    return os.getenv("OPENAI_API_KEY")

def _candidate_schema_paths() -> list[Path]:
    here = Path(__file__).resolve()
    root = here.parents[2]  # <repo>/src/ui/assist/../../..
    return [
        root / "src" / "schemas" / "prompts.schema.json",
        root / "schemas" / "prompts.schema.json",
        Path.cwd() / "src" / "schemas" / "prompts.schema.json",
    ]

def _load_json_schema() -> Tuple[Optional[dict], Optional[Path]]:
    for p in _candidate_schema_paths():
        try:
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8")), p
        except Exception:
            continue
    return None, None

def _validate_yaml_with_schema(yaml_text: str) -> Tuple[bool, str]:
    """
    jsonschema가 설치되어 있으면 검증, 없으면 '스킵' 메시지 반환.
    스키마 파일이 없으면 '권고' 메시지와 함께 항상 True.
    """
    try:
        obj = yaml.safe_load(yaml_text)
    except Exception as e:
        return False, f"YAML 파싱 오류: {e}"

    schema, path = _load_json_schema()
    if schema is None:
        return True, "스키마 파일을 찾지 못했습니다. (검증 생략)"
    try:
        import jsonschema  # type: ignore
        jsonschema.validate(obj, schema)
        return True, f"스키마 검증 통과 ✓  (schema={path})"
    except ModuleNotFoundError:
        return True, "jsonschema 미설치 — 스키마 검증 생략(권고)"
    except Exception as e:
        return False, f"스키마 위배: {e}"
# ================================ [03] helpers — END ==================================

# =============================== [04] page header — START =============================
def _render_header() -> None:
    st.markdown("## 🧭 프롬프트 Admin (자연어 → YAML 노멀라이저)")
    st.caption("스키마 파일이 없거나 jsonschema 미설치여도 동작합니다(권고 경고만 표시).")
# ================================ [04] page header — END ==============================

# =============================== [05] input areas — START =============================
def _render_inputs() -> tuple[str, str, str]:
    st.markdown("#### 입력(자연어 한 덩어리씩)")
    c1, c2, c3 = st.columns(3)
    with c1:
        grammar = st.text_area("문법(Grammar)", height=260, key="pn_grammar")
    with c2:
        sentence = st.text_area("문장(Sentence)", height=260, key="pn_sentence")
    with c3:
        passage = st.text_area("지문(Passage)", height=260, key="pn_passage")
    return grammar, sentence, passage
# ================================ [05] input areas — END ==============================

# =============================== [06] actions — START =================================
def _render_actions(grammar: str, sentence: str, passage: str) -> str:
    st.markdown("#### 변환/검증")
    col_a, col_b, col_c = st.columns([1, 1, 1])

    yaml_text = st.session_state.get("_pn_yaml", "") or ""

    if col_a.button("🔧 자연어 → YAML 변환", type="primary", use_container_width=True):
        key = _get_openai_key()
        yaml_text = normalize_to_yaml(
            grammar_text=grammar,
            sentence_text=sentence,
            passage_text=passage,
            openai_key=key,
            openai_model=os.getenv("OPENAI_MODEL") or "gpt-4o-mini",
        )
        st.session_state["_pn_yaml"] = yaml_text

    if col_b.button("🧪 스키마 검증", use_container_width=True):
        ok, msg = _validate_yaml_with_schema(yaml_text)
        (st.success if ok else st.error)(msg)

    if col_c.button("📤 출판(Publish)", use_container_width=True):
        if not yaml_text.strip():
            st.warning("먼저 YAML을 생성하세요.")
        else:
            # 저장 위치/방식은 프로젝트 정책에 맞게 여기서만 통합
            st.session_state["PROMPT_PROFILE_YAML"] = yaml_text
            st.success("출판 완료(세션에 저장). 실제 배포 경로와 동기화는 저장 훅에 연결하세요.")

    return yaml_text
# ================================= [06] actions — END =================================

# =============================== [07] preview — START =================================
def _render_preview(yaml_text: str) -> None:
    st.markdown("#### 결과 미리보기")
    if not yaml_text.strip():
        st.info("아직 생성된 YAML이 없습니다.")
        return
    st.code(yaml_text, language="yaml")
# ================================= [07] preview — END =================================

# =============================== [08] main — START ====================================
def main() -> None:
    if st is None:
        print("Streamlit 환경이 아닙니다.")
        return
    _render_header()
    g, s, p = _render_inputs()
    y = _render_actions(g, s, p)
    _render_preview(y)

if __name__ == "__main__":
    main()
# ================================= [08] main — END ====================================
