# [01] START: admin_prompt — Loader helpers (release/prompts.yaml)
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import json
import yaml
import streamlit as st

# ---- UI Widget Keys (stable) ----
K_GRAMMAR: str = "prompt_PT"               # 문법(Grammar)
K_SENTENCE: str = "prompt_MN_sentence"     # 문장(Sentence)
K_PASSAGE: str = "prompt_MN_passage"       # 지문(Passage)

def _resolve_release_prompts_file() -> Path | None:
    """
    릴리스/에셋 위치에서 prompts.yaml을 가장 먼저 발견되는 경로로 선택.
    우선순위: <_release_dir>/assets > <_release_dir> > ./assets > ./
    """
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
            # 경로 이슈(권한/부정확한 심볼릭 등)는 무시하고 다음 후보로 진행
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
    """
    다양한 YAML 스키마를 허용해 3개 텍스트(문법/문장/지문)로 매핑한다.
    지원 예:
      - {grammar, sentence, passage}
      - {pt: "...", mn: {sentence: "...", passage: "..."}}  등
    """
    data: Dict[str, Any] = {
        (k.lower() if isinstance(k, str) else k): v
        for k, v in (yaml_data or {}).items()
    }
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

    # 2) { mn: { sentence, passage } } 지원
    mn = data.get("mn") or data.get("mina")
    if isinstance(mn, dict):
        if "sentence" in mn:
            out[K_SENTENCE] = _coerce_yaml_to_text(mn["sentence"])
        if "passage" in mn:
            out[K_PASSAGE] = _coerce_yaml_to_text(mn["passage"])

    # 3) { pt: { grammar/prompt/text/... } } 보정(드문 케이스)
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
    """
    버튼 핸들러: 세션 키에 값 주입 후 즉시 rerun.
    UI에는 value= 초기값을 쓰지 않고 key 바인딩만 사용해야 한다.
    """
    try:
        texts, src = _load_prompts_from_release()
        st.session_state[K_GRAMMAR] = texts[K_GRAMMAR]
        st.session_state[K_SENTENCE] = texts[K_SENTENCE]
        st.session_state[K_PASSAGE]  = texts[K_PASSAGE]
        st.session_state["_last_prompts_source"] = str(src)
        st.session_state["_flash_success"] = f"릴리스에서 프롬프트를 불러왔습니다: {src}"
        st.rerun()  # 즉시 반영
    except FileNotFoundError as e:
        st.session_state["_flash_error"] = str(e)
        st.rerun()
    except Exception:
        # 상세 예외는 내부 로그로만(민감정보 노출 방지)
        st.session_state["_flash_error"] = "프롬프트 로딩 중 오류가 발생했습니다."
        st.rerun()
# [01] END
# [02] START: admin_prompt — UI widgets + Action button (Loader)
import streamlit as st
from ui.nav import render_sidebar  # 이전 브랜치에서 추가된 공통 사이드바

# 사이드바 일관 렌더
render_sidebar()

# 이전 단계에서 설정해둔 플래시 메시지 표출(1회성)
_success = st.session_state.pop("_flash_success", None)
_error = st.session_state.pop("_flash_error", None)
if _success:
    st.success(_success)
if _error:
    st.error(_error)

st.header("② 모드별 프롬프트(지시/규칙)")

# 중요: value 인자 미사용. 세션 상태(key) 단일 소스 유지.
st.text_area("문법(Grammar) 프롬프트", key=K_GRAMMAR, height=220, placeholder="문법 모든 지시/규칙…")
st.text_area("문장(Sentence) 프롬프트", key=K_SENTENCE, height=220, placeholder="문장 모든 지시/규칙…")
st.text_area("지문(Passage) 프롬프트", key=K_PASSAGE,  height=220, placeholder="지문 모든 지시/규칙…")

st.markdown("### ③ 액션")
st.button("🧲 최신 프롬프트 불러오기(릴리스 우선)", on_click=on_click_load_latest_prompts)

# 운영 가시성을 위해 최근 소스 경로를 표시(선택)
_last = st.session_state.get("_last_prompts_source")
if _last:
    st.caption(f"최근 소스: {_last}")
# [02] END



# ===== [03] publish helpers — START =====
def _gh_dispatch_workflow(
    *,
    owner: str,
    repo: str,
    workflow: str,
    ref: str,
    token: str | None,
    yaml_text: str,
    prerelease: bool = False,
    promote_latest: bool = True,
) -> None:
    s, n = _sanitize_ellipsis(yaml_text)
    if n:
        st.info(f"U+2026 {n}개를 '...'로 치환했습니다.")
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
    payload = {"ref": ref, "inputs": {
        "yaml_b64": base64.b64encode(s.encode("utf-8")).decode("ascii"),
        "prerelease": "true" if prerelease else "false",
        "promote_latest": "true" if promote_latest else "false",
    }}
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = req.post(url, headers=headers, json=payload, timeout=20)
    if r.status_code not in (201, 204):
        raise RuntimeError(f"workflow_dispatch failed: {r.status_code} — {r.text}")
# ===== [03] publish helpers — END =====


# ===== [04] page init — START =====
def _init_admin_page() -> None:
    st.set_page_config(page_title="Prompts Admin", page_icon="🛠️", layout="wide")
    ensure_admin_sidebar()
    try:
        show_sidebar()  # 이 페이지에선 사이드바 강제 노출
    except Exception:
        pass
    render_minimal_admin_sidebar(back_page="app.py")
# ===== [04] page init — END =====


# ===== [05] prefill handshake — START =====
def _apply_pending_prefill() -> None:
    """
    버튼 클릭 → _PREFILL_PROMPTS에 담아 rerun → 이 함수가 '위젯 생성 전에'
    세션 키(persona_text/grammar_prompt/...)에 안전 주입.
    """
    if not callable(apply_prompts_to_session):
        return
    ss = st.session_state
    pending = None
    for k in ("_PREFILL_PROMPTS", "_prefill_prompts"):
        if k in ss and isinstance(ss[k], dict):
            pending = ss.pop(k)
            break
    if pending:
        # 아직 위젯이 만들어지기 '전'이므로 안전하게 세션키에 주입 가능
        apply_prompts_to_session(pending)  # 관용 키 매핑 사용 (loader 구현 참조)
# ===== [05] prefill handshake — END =====


# ===== [06] main — START =====
def main() -> None:
    _init_admin_page()

    # ✅ 프리필 예약분이 있으면, 위젯 생성 전에 먼저 주입
    _apply_pending_prefill()

    # --- 상태점검 박스 -------------------------------------------------------------
    with st.container(border=True):
        st.subheader("🔍 상태 점검", divider="gray")
        repo_full = st.secrets.get("GITHUB_REPO", "")
        token = st.secrets.get("GITHUB_TOKEN")
        ref = st.secrets.get("GITHUB_BRANCH", "main")
        workflow = st.secrets.get("GITHUB_WORKFLOW", "publish-prompts.yml")

        owner = repo = ""
        repo_config_error = False
        if repo_full and "/" in repo_full:
            owner, repo = repo_full.split("/", 1)
            if not owner or not repo:
                repo_config_error = True
                st.error("GITHUB_REPO 형식이 잘못되었습니다. 예: OWNER/REPO")
        elif repo_full:
            repo_config_error = True
            st.error("GITHUB_REPO 형식이 잘못되었습니다. 예: OWNER/REPO")
        else:
            repo_config_error = True
            st.info("GITHUB_REPO 시크릿이 비어 있어 출판 기능이 비활성화됩니다. 편집과 저장은 계속 사용할 수 있습니다.")

        # 릴리스 체크(최신 + prompts.yaml 존재)
        try:
            headers = {"Accept": "application/vnd.github+json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/prompts-latest"
            r = req.get(url, headers=headers, timeout=10)
            if r.status_code == 404:  # fallback
                r = req.get(f"https://api.github.com/repos/{owner}/{repo}/releases/latest", headers=headers, timeout=10)
            rel = r.json() if r.ok else {}
            assets = rel.get("assets") or []
            has_prompts = any((a.get("name") or "").lower() in ("prompts.yaml","prompts.yml") for a in assets)
            if has_prompts:
                st.success(f"릴리스 OK — prompts.yaml 자산 확인 (assets={len(assets)})")
            else:
                st.warning(f"릴리스에 prompts.yaml 자산이 보이지 않습니다. (assets={len(assets)})")
        except Exception as e:
            st.warning(f"릴리스 확인 실패: {e}")

    # --- 편집 UI ------------------------------------------------------------------
    st.markdown("### ① 페르소나(공통)")
    persona = st.text_area("모든 모드에 공통 적용", key="persona_text", height=160, placeholder="페르소나 텍스트...", help="모든 모드 공통 지침")

    st.markdown("### ② 모드별 프롬프트(지시/규칙)")
    c1, c2, c3 = st.columns(3)
    with c1:
        grammar_prompt = st.text_area("문법(Grammar) 프롬프트", key="grammar_prompt", height=200, placeholder="문법 모드 지시/규칙...")
    with c2:
        sentence_prompt = st.text_area("문장(Sentence) 프롬프트", key="sentence_prompt", height=200, placeholder="문장 모드 지시/규칙...")
    with c3:
        passage_prompt = st.text_area("지문(Passage) 프롬프트", key="passage_prompt", height=200, placeholder="지문 모드 지시/규칙...")

    # 액션 버튼
    st.markdown("### ③ 액션")
    b1, b2, b3, b4 = st.columns(4, vertical_alignment="center")

    # (a) 최신 프롬프트 불러오기(릴리스)
    with b1:
        if st.button("📥 최신 프롬프트 불러오기(릴리스 우선)", use_container_width=True, key="btn_fetch_prompts"):
            try:
                if callable(load_prompts_from_release):
                    data = load_prompts_from_release()  # 릴리스 → SSOT 폴백, persona+3모드 추출
                    # ❗️직접 세션키를 덮지 말고 예약키에 저장 → 즉시 rerun → 위젯 생성 이전에 주입
                    st.session_state["_PREFILL_PROMPTS"] = data
                    st.rerun()
                else:
                    st.error("prompts_loader 모듈을 불러오지 못했습니다.")
            except Exception as e:
                st.exception(e)

    # (b) YAML 병합(LLM) — 선택 사항
    with b2:
        if st.button("🧠 전체 정리(LLM)", use_container_width=True, key="llm_all"):
            if callable(normalize_to_yaml):
                y = normalize_to_yaml(
                    grammar_text=st.session_state.get("grammar_prompt", "") or "",
                    sentence_text=st.session_state.get("sentence_prompt", "") or "",
                    passage_text=st.session_state.get("passage_prompt", "") or "",
                    openai_key=st.secrets.get("OPENAI_API_KEY"),
                    openai_model=st.secrets.get("OPENAI_MODEL", "gpt-4o-mini"),
                )
                st.session_state["_merged_yaml"] = y
            else:
                st.warning("LLM 정리기(normalize_to_yaml)를 찾지 못했습니다. 수동 YAML 미리보기로 진행하세요.")

    # (c) 수동 병합/미리보기 — LLM 없어도 동작
    with b3:
        if st.button("🧾 YAML 병합(로컬 필드→YAML)", use_container_width=True, key="merge_local"):
            # 관용 YAML 스냅샷(간결 포맷)
            doc = {
                "version": "auto",
                "persona": st.session_state.get("persona_text", "") or "",
                "modes": [
                    {"key": "grammar", "prompt": st.session_state.get("grammar_prompt", "") or ""},
                    {"key": "sentence", "prompt": st.session_state.get("sentence_prompt", "") or ""},
                    {"key": "passage", "prompt": st.session_state.get("passage_prompt", "") or ""},
                ],
            }
            st.session_state["_merged_yaml"] = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)

    # (d) 출판(Publish)
    with b4:
        publish_disabled = repo_config_error or not owner or not repo
        publish_clicked = st.button(
            "🚀 출판(Publish)",
            type="primary",
            use_container_width=True,
            key="publish_all",
            disabled=publish_disabled,
            help="GITHUB_REPO 시크릿이 설정되어 있어야 출판할 수 있습니다." if publish_disabled else None,
        )
        if publish_clicked:
            y = st.session_state.get("_merged_yaml", "")
            ok, msgs = _validate_yaml_text(y)
            if not ok:
                st.error("스키마 검증 실패 — 먼저 오류를 해결하세요.")
                if msgs:
                    st.write("\n".join(f"- {m}" for m in msgs))
            else:
                try:
                    _gh_dispatch_workflow(
                        owner=owner,
                        repo=repo,
                        workflow=workflow,
                        ref=ref,
                        token=token,
                        yaml_text=y,
                    )
                    st.success("출판 요청 전송 완료 — Actions에서 처리 중입니다.")
                    st.markdown(
                        f"[열기: Actions › {workflow}]"
                        f"(https://github.com/{owner}/{repo}/actions/workflows/{workflow})"
                    )
                except Exception as exc:  # noqa: BLE001
                    st.exception(exc)

    # YAML 미리보기
    if st.session_state.get("_merged_yaml"):
        st.markdown("### YAML 미리보기")
        st.code(st.session_state["_merged_yaml"], language="yaml")


if __name__ == "__main__":
    main()
# ===== [06] main — END =====
# ===== [01] FILE: src/ui/admin_prompt.py — END =====
