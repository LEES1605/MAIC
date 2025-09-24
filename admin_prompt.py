# ============================== Prompts Admin — START ===============================
from __future__ import annotations

import io
from typing import Optional
from pathlib import Path

try:
    import streamlit as st
except Exception:
    st = None

import yaml

# 정규화 로직(자연어 → 완화 스키마 YAML)
from src.ui.assist.prompt_normalizer import normalize_to_yaml  # noqa: E402

TITLE = "Prompts Admin (Persona + Prompt 분리)"

def _is_admin() -> bool:
    try:
        return bool(st.session_state.get("admin_mode"))
    except Exception:
        return False

def _persist_dir() -> Path:
    try:
        from src.core.persist import effective_persist_dir
        return Path(str(effective_persist_dir())).expanduser()
    except Exception:
        return Path.home() / ".maic" / "persist"


def main() -> None:
    if st is None:
        return

    st.set_page_config(page_title=TITLE, layout="wide")

    # 관리자 전용 게이트
    if not _is_admin():
        st.error("이 페이지는 **관리자 전용**입니다.")
        st.page_link("app.py", label="← 홈으로 돌아가기", icon="🏠")
        st.stop()

    st.markdown(f"## {TITLE}")

    # UI: 상/하 2칸 — (1) 페르소나 (2) 프롬프트 (둘 다 크게)
    st.caption("입력 칸은 스크롤 없이 충분한 높이로 제공합니다.")
    persona = st.text_area("① 페르소나(Persona)", height=340, key="ap_persona")
    prompt  = st.text_area("② 프롬프트(지시/규칙)", height=420, key="ap_prompt")

    col_a, col_b = st.columns([1, 1])

    with col_a:
        st.markdown("#### 변환")
        do = st.button("정규화(Normalize → YAML)", type="primary", use_container_width=True)
        if do:
            openai_key = None
            try:
                # 있으면 사용, 없으면 폴백 템플릿으로 생성
                openai_key = st.secrets.get("OPENAI_API_KEY")
            except Exception:
                openai_key = None

            # 자연어 한 덩어리 → 각 모드 입력으로 그대로 넣어 완화 스키마 생성
            # (간편화: 세 모드 모두 동일 입력 사용)
            bundle_text = (persona or "").strip() + "\n\n" + (prompt or "").strip()
            yaml_text = normalize_to_yaml(
                grammar_text=bundle_text,
                sentence_text=bundle_text,
                passage_text=bundle_text,
                openai_key=openai_key,
            )
            st.session_state["_PROMPTS_YAML"] = yaml_text

        st.markdown("#### 저장")
        current = st.session_state.get("_PROMPTS_YAML", "")
        if current:
            buf = io.BytesIO(current.encode("utf-8"))
            st.download_button(
                "YAML 다운로드",
                data=buf,
                file_name="prompts.yaml",
                mime="text/yaml",
                use_container_width=True,
            )

            # 선택: Persist 디렉터리에도 저장(권한/권고에 맞게 사용)
            if st.button("Persist 디렉터리에 저장(선택)", use_container_width=True):
                try:
                    pdir = _persist_dir()
                    pdir.mkdir(parents=True, exist_ok=True)
                    (pdir / "prompts.yaml").write_text(current, encoding="utf-8")
                    st.success(f"저장 완료: {pdir / 'prompts.yaml'}")
                except Exception as e:
                    st.error(f"저장 실패: {e}")

    with col_b:
        st.markdown("#### 출력 미리보기 (YAML)")
        st.code(st.session_state.get("_PROMPTS_YAML", ""), language="yaml")


if __name__ == "__main__":
    main()
# =============================== Prompts Admin — END ================================
