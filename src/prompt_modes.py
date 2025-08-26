# ===== [PM] FILE: src/prompt_modes.py ========================================
"""
Google Drive → Local 캐시 기반 프롬프트 로더/엔진
- Drive `prompts` 폴더 내 `prompts.yaml`(또는 최신 .yaml)을 찾아 로컬에 캐시
- YAML(persona/guidelines/modes/…)을 읽어 모드별 system/user 프롬프트 조립
- 후속질문(followup)/보충(supplement) 템플릿 지원
- 안전치환: {question},{context},{today},{mode},{lang},{primary_answer} '정확 토큰'만 교체
- OpenAI / Gemini 페이로드 변환 유틸 제공

주의:
- 교육 예시용 중괄호 { } 가 많으므로 str.format* 금지. 안전치환 사용.
- Drive 실패/로컬 부재 시 내장 기본 YAML로 폴백(서비스 다운 방지).
"""

# ===== [PM-00] Imports & Globals ============================================
from __future__ import annotations
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any, TypedDict, List, cast

_OVR_CACHE: Optional[dict] = None  # YAML 메모리 캐시
_REMOTE_PULL_ONCE_FLAG = {"done": False}  # [04C] 패널 호환용 플래그

# ----- Optional imports (지연) ------------------------------------------------
def _maybe_import_streamlit():
    try:
        import streamlit as st
        return st
    except Exception:
        return None

def _maybe_import_yaml():
    try:
        import yaml  # type: ignore
        return yaml
    except Exception:
        return None

# ===== [PM-01] Paths & Drive helpers ========================================
def get_overrides_path() -> Path:
    """
    로컬 캐시 경로(기존 규칙 유지):
      - ENV MAIC_PROMPTS_PATH 가 있으면 그 파일 경로 사용
      - 없으면 ~/.maic/prompts.yaml
    """
    env_path = os.getenv("MAIC_PROMPTS_PATH")
    if env_path:
        p = Path(env_path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    p = Path.home().joinpath(".maic", "prompts.yaml")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def _get_drive_folder_id() -> Optional[str]:
    """Drive 폴더 ID (ENV → st.secrets 순)"""
    fid = os.getenv("MAIC_PROMPTS_DRIVE_FOLDER_ID")
    if fid:
        return str(fid)
    st = _maybe_import_streamlit()
    try:
        if st and "MAIC_PROMPTS_DRIVE_FOLDER_ID" in st.secrets:
            return str(st.secrets["MAIC_PROMPTS_DRIVE_FOLDER_ID"])
    except Exception:
        pass
    return None

def _get_drive_service():
    """
    src.rag.index_build 에 정의된 _drive_service() 재사용.
    (없으면 None)
    """
    try:
        import importlib
        im = importlib.import_module("src.rag.index_build")
        if hasattr(im, "_drive_service") and callable(getattr(im, "_drive_service")):
            return im._drive_service()
    except Exception:
        return None
    return None

def _pull_remote_overrides_if_newer() -> Optional[str]:
    """
    Drive prompts 폴더에서 .yaml 파일을 찾아 로컬 캐시를 갱신.
    - 우선순위: 이름이 정확히 'prompts.yaml' → 없으면 가장 최근 수정된 .yaml
    - 로컬이 없거나, 원격 modifiedTime 이 더 최신이면 다운로드
    반환: "downloaded" | "nochange" | None(실패/연결없음)
    """
    folder_id = _get_drive_folder_id()
    if not folder_id:
        return None
    svc = _get_drive_service()
    if not svc:
        return None

    try:
        q = f"'{folder_id}' in parents and trashed=false"
        res = svc.files().list(q=q, fields="files(id,name,mimeType,modifiedTime)").execute()
        files = res.get("files", []) or []
        cands = [f for f in files if (f.get("name","").lower().endswith(".yaml"))]
        if not cands:
            return None

        target = None
        for f in cands:
            if f.get("name","").lower() == "prompts.yaml":
                target = f; break
        if not target:
            # modifiedTime 기준 최신
            target = sorted(cands, key=lambda x: x.get("modifiedTime",""))[-1]

        lp = get_overrides_path()
        remote_mtime = target.get("modifiedTime") or ""
        local_mtime = ""
        if lp.exists():
            try:
                local_mtime = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(lp.stat().st_mtime))
            except Exception:
                local_mtime = ""

        need = (not lp.exists()) or (remote_mtime and remote_mtime > local_mtime)
        if not need:
            return "nochange"

        # 다운로드
        dl = svc.files().get_media(fileId=target["id"]).execute()
        data = dl if isinstance(dl, (bytes, bytearray)) else (dl.read() if hasattr(dl, "read") else bytes(dl))
        lp.write_bytes(data)
        _REMOTE_PULL_ONCE_FLAG["done"] = True
        return "downloaded"
    except Exception:
        return None

def pull_remote_overrides_once() -> Optional[str]:
    """
    외부에서 호출해 원격 갱신을 1회 시도하고 캐시 무효화.
    [04C]에서 사용.
    """
    global _OVR_CACHE
    result = _pull_remote_overrides_if_newer()
    _OVR_CACHE = None
    return result

# ===== [PM-02] Built-in fallback YAML =======================================
_DEFAULT_OVERRIDES_YAML = """\
version: 1
modes:
  문장구조분석:
    system: |
      당신은 영문법(통사론·의미론) 전문가 AI로서, 현대 영국·미국 영어 모두에 정통합니다.
      당신의 분석은 최신 코퍼스 언어학과 실제 사용 용례에 근거해야 하며, 추측은 금지합니다.
      EFL 학습자를 배려해 한국어로 간결·정확하게 설명하되, 예시는 자연스러운 영어를 사용합니다.
      모호함이 있을 땐 임의 판단하지 말고 먼저 사용자에게 필요한 추가 정보를 물어봅니다.
      대화 중 확정된 지침은 이후 답변에 일관되게 적용합니다.
      관용구/연어/굳어진 표현으로 판단되면 그 사실을 가장 먼저 밝히고 설명을 시작합니다.
      답변의 신뢰성에 스스로 엄격하세요. 확신이 부족하거나 잠재적 부정확 가능성이 있다고 판단되면 그 사실을 명시합니다.

    user: |
      [분석 목적]
      - 입력 문장을 엄격한 "괄호 규칙"에 따라 구조적으로 분석하고,
        핵심 골격과 어휘·표현, 자연스러운 번역, 근거를 단계별로 제시합니다.
      - 언어: {lang} / 모드: {mode} / 날짜: {today}

      [입력 문장]
      {question}

      [데이터·근거 사용 원칙]
      - 가능하면 업로드된 자료(최근 10개), 최근 10년간 TOEFL/IELTS 예문·지문 및 신뢰 가능한 문법 규칙을 근거로 사용합니다.
      - 출처는 항목 끝에 간단히 표기하세요. (예: [업로드/파일명], [TOEFL-2018/Reading], [규칙: 가주어-진주어])

      [문장 구조 분석 — 괄호 규칙(엄수)]
      - 명사적 용법(준동사/절): 대괄호 [ ]   예) [To study hard] is important. / She knows [what she said].
      - 형용사적 용법(구/절, 분사 수식 포함): 중괄호 { }   예) This is a chance {to succeed}. / Look at the {sleeping} baby.
      - 부사적 용법(구/절): 기예메 « »   예) He studies hard «to pass the exam». / Call me «when you are ready».
      - 전치사구: 소괄호 ( )   예) The book is (on the desk).
      - 일반 명사/명사구 자체에는 괄호를 쓰지 않습니다. (예: The beautiful house (on the hill) is expensive.)
      - It-cleft(강조) : 강조 대상이 명사(구)면 [[ ]] 사용, 부사/부사구/부사절이면 « » 사용. It 자체엔 괄호 없음.
        예) It was [[John]] {who broke the window}. / It was «yesterday» {that I met him}.
      - 가주어/진주어: 진주어가 명사절/명사적 준동사구이면 [It] is ... [진주어] 로 표기.
        예) [It] is important [to finish the work on time]. / [It] is true [that he is honest].
      - 생략 복원: 의미상 필요한 생략 요소(관계대명사, 주격관계대명사+be 등)는 (*생략형) 로 해당 위치에 복원 표시.
        예) This is the house {(*that/which) I built}. / The girl {(*who is) playing the piano} is my sister.
      - 비교급 상관구문: «The 비교급 S V», the 비교급 S V — 첫 절은 부사절로 « » 사용, 주절엔 별도 괄호 없음.
        예) «The harder you study», the better grades you will get.
      - 도치구문(동사가 주어 앞): 문두 이동된 부분을 규칙대로 괄호 처리하고, 문장 끝에 -INVS 표시.
        예) «Nor» does it happen.-INVS
      - 비교급에서 that/as는 원칙적으로 부사절로 취급.
      - afraid/sure/aware + to-V, 그리고 해당 형용사 + that S V 는 형용사 보충어로 간주(별도 괄호 적용하지 않음).

      [출력 형식(항상 아래 구조로)]
      0) 모호성 점검(필요시 질문 1~2개만)
      1) 괄호 규칙 적용 표기: 입력 문장을 위 규칙 그대로 표시 (한 줄)
      2) 핵심 골격: [S: … | V: … | O: … | C: … | M: …]
      3) 구조 요약: 구/절 계층과 의존관계를 2~4줄로 요약
      4) 어휘·표현: 핵심 어휘/관용구 설명(간결)
      5) 번역: 자연스러운 한국어 번역 1–2문장
      6) 근거/출처: 사용한 규칙·자료의 출처를 최소 1개 이상 표기

    followup_user: |
      [추가 질문]
      {question}

      [참고: 이전 대화 요지(재진술 금지)]
      {context}

      [응답 지시 — 후속 모드]
      - 새 정보/정정/예외만 3~5줄로.
      - 이전 답변 재진술 금지, 중복 금지.
      - 필요하면 예문 1–2개만(간결).

    supplement:
      user: |
        [1차 응답 요지]
        {primary_answer}

        [보충 지시 — 차별화]
        - 1차와 다른 관점/구조로 설명.
        - 비교 포인트 2~3개, 예문 1~2개.
        - 반복 금지.

    provider_kwargs:
      temperature: 0.1
      top_p: 1
      presence_penalty: 0.0
      frequency_penalty: 0.0
      max_tokens: 1400
"""

# ===== [PM-03] YAML load with fallback ======================================
def load_overrides(force_refresh: bool = False) -> dict:
    """
    로컬/Drive에서 prompts YAML을 읽어 dict 반환.
    - 경로: ENV MAIC_PROMPTS_PATH 우선, 없으면 ~/.maic/prompts.yaml
    - 파일이 없거나 파싱 실패 시:
        1) (가능하면) 원격 당겨오기 시도
        2) 그래도 실패하면 _DEFAULT_OVERRIDES_YAML 로 폴백
    - force_refresh=True 이면 원격 갱신 훅 먼저 시도
    """
    global _OVR_CACHE
    if (not force_refresh) and (_OVR_CACHE is not None):
        return _OVR_CACHE

    lp = get_overrides_path()

    # 강제 새로고침 시 원격 시도
    if force_refresh:
        try:
            _pull_remote_overrides_if_newer()
        except Exception:
            pass

    # 로컬 없으면 원격 한 번 시도
    if not lp.exists():
        try:
            _pull_remote_overrides_if_newer()
        except Exception:
            pass

    data: dict = {}
    yaml = _maybe_import_yaml()
    try:
        if lp.exists() and yaml:
            data = yaml.safe_load(lp.read_text(encoding="utf-8")) or {}
        else:
            # 폴백
            if yaml:
                data = yaml.safe_load(_DEFAULT_OVERRIDES_YAML) or {}
            else:
                data = {"version": 1, "modes": {}}
    except Exception:
        try:
            if yaml:
                data = yaml.safe_load(_DEFAULT_OVERRIDES_YAML) or {}
            else:
                data = {"version": 1, "modes": {}}
        except Exception:
            data = {"version": 1, "modes": {}}

    if not isinstance(data, dict):
        data = {"version": 1, "modes": {}}
    data.setdefault("version", 1)
    data.setdefault("modes", {})

    _OVR_CACHE = data
    return data

# ===== [PM-04] Safe replace (정확 토큰만 치환) ===============================
def _safe_replace(text: str, mapping: dict) -> str:
    """
    {question}, {context}, {today}, {mode}, {lang}, {primary_answer}
    정확히 일치하는 토큰만 교체. 일반 { } 예시에는 영향 없음.
    """
    if not isinstance(text, str) or not mapping:
        return text
    out = text
    for key, val in mapping.items():
        token = "{" + key + "}"
        out = out.replace(token, "" if val is None else str(val))
    return out

def _fmt(tmpl: str, mapping: dict) -> str:
    """안전치환 래퍼(과거 format_map 대체)."""
    return _safe_replace(tmpl or "", mapping or {})

# ===== [PM-05] Mode selection & prompt build ================================
class PromptParts(TypedDict, total=False):
    system: str
    user: str
    provider_kwargs: dict

def _select_mode_block(modes: dict, mode_label: str) -> Optional[dict]:
    """모드명 정확→별칭→소문자 근사 매칭"""
    if not isinstance(modes, dict):
        return None
    if mode_label in modes:
        return modes[mode_label]
    alias_map = {
        "Grammar": "문법설명",
        "Sentence": "문장구조분석",
        "Passage": "지문분석",
        "문장 분석": "문장구조분석",
    }
    alt = alias_map.get(mode_label)
    if alt and alt in modes:
        return modes[alt]
    norm = str(mode_label).strip().lower()
    for k in modes.keys():
        if str(k).strip().lower() == norm:
            return modes[k]
    return None

def build_prompt(
    mode_label: str,
    question: str,
    lang: str = "ko",
    extras: Optional[Dict[str, Any]] = None,
) -> PromptParts:
    """
    YAML(overrides)을 읽어 해당 모드의 system/user 프롬프트 조립.
    - 후속: extras['is_followup'] True & YAML.followup_user 있으면 우선 사용
            (없으면 기존 user에 후속 지시를 자동 덧붙임)
    - 보충: extras['primary_answer'] 존재 & YAML.supplement.user 있으면 우선 사용
            (없으면 기존 user에 차별화 지시 자동 덧붙임)
    - 안전치환: {question},{context},{today},{mode},{lang},{primary_answer}
    """
    data = load_overrides()
    modes = data.get("modes") or {}
    blk = _select_mode_block(modes, mode_label) or {}

    is_follow = bool((extras or {}).get("is_followup"))
    has_primary = bool((extras or {}).get("primary_answer"))

    tpl_system = blk.get("system") or ""
    tpl_user = blk.get("user") or ""

    # 후속/보충 템플릿 우선
    if has_primary and isinstance(blk.get("supplement"), dict) and blk["supplement"].get("user"):
        tpl_user = blk["supplement"]["user"] or tpl_user
    elif is_follow and blk.get("followup_user"):
        tpl_user = blk["followup_user"] or tpl_user

    from datetime import datetime as _dt
    today = (extras or {}).get("today") or _dt.now().strftime("%Y-%m-%d")
    context = (extras or {}).get("context") or ""
    primary_answer = (extras or {}).get("primary_answer") or ""
    mode_display = (extras or {}).get("mode_display") or mode_label

    mapping = {
        "question": question or "",
        "context": context or "",
        "primary_answer": primary_answer or "",
        "today": today,
        "mode": mode_display,
        "lang": lang or "ko",
    }

    system_final = _fmt(tpl_system, mapping)
    user_final = _fmt(tpl_user, mapping)

    provider_kwargs = dict(blk.get("provider_kwargs") or {})

    # 템플릿 없을 때의 보조 지시(짧게)
    if has_primary and "primary_answer" not in tpl_user:
        user_final += (
            "\n\n[보충 지시 — 차별화]\n"
            "- 1차와 다른 관점/구조로 설명.\n"
            "- 비교 포인트 2~3개, 예문 1~2개.\n"
            "- 반복/재진술 금지.\n"
        )
    elif is_follow and "추가 질문" not in tpl_user:
        user_final += (
            "\n\n[후속 지시]\n"
            "- 새 정보/정정/예외만 간결히(3~5줄).\n"
            "- 이전 답변 재진술/중복 금지.\n"
            "- 필요 시 예문 1~2개.\n"
        )

    return cast(PromptParts, {
        "system": system_final,
        "user": user_final,
        "provider_kwargs": provider_kwargs,
    })

# ===== [PM-06] Payload converters ===========================================
def to_openai(parts: PromptParts) -> dict:
    """
    OpenAI Chat Completions 형식으로 변환.
    (temperature/max_tokens/top_p 등은 호출부에서 병합/덮어쓰기 권장)
    """
    sys = (parts.get("system") or "").strip()
    usr = (parts.get("user") or "").strip()
    messages = []
    if sys:
        messages.append({"role": "system", "content": sys})
    messages.append({"role": "user", "content": usr})

    out = {"messages": messages}
    if parts.get("provider_kwargs"):
        # 참고용으로 동봉(호출부에서 사용/무시 선택)
        out.update(parts["provider_kwargs"])
    return out

def to_gemini(parts: PromptParts) -> dict:
    """
    Gemini generateContent 형식으로 변환.
    시스템 프롬프트는 단순 결합하여 user 텍스트로 전달.
    """
    sys = (parts.get("system") or "").strip()
    usr = (parts.get("user") or "").strip()
    full = (sys + "\n\n" + usr) if sys else usr
    contents = [{"role": "user", "parts": [{"text": full}]}]
    out = {"contents": contents}
    if parts.get("provider_kwargs"):
        out.update(parts["provider_kwargs"])
    return out

# ===== [PM-07] Diagnostics helpers ==========================================
def list_modes() -> List[str]:
    """YAML에 포함된 모드명 나열(진단 패널 [04C]에서 사용)."""
    try:
        data = load_overrides()
        modes = data.get("modes") or {}
        return list(modes.keys())
    except Exception:
        return []

def get_enabled_modes_unified() -> dict:
    """
    기존 UI 호환용: Grammar/Sentence/Passage 키로 단순 맵 반환.
    """
    names = set(list_modes())
    return {
        "Grammar": ("문법설명" in names) or ("Grammar" in names),
        "Sentence": ("문장구조분석" in names) or ("Sentence" in names),
        "Passage": ("지문분석" in names) or ("Passage" in names),
    }

# ===== [PM] END ==============================================================
