# ============================================================
# ============ [PM-01] PROMPT MODES MODULE (UPDATED) =========
# ============================================================
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime, timezone
import os, json, io

# ---- YAML 지원(없으면 JSON 폴백) --------------------------------------------
try:
    import yaml  # type: ignore
except Exception:  # PyYAML이 없으면 내부 json으로 폴백
    yaml = None  # noqa: N816

# ============================================================
# 경로/환경설정
# ============================================================
def _expand_user_path(p: str) -> Path:
    return Path(os.path.expanduser(p)).resolve()

def get_overrides_path() -> Path:
    """
    로컬 prompts.yaml 경로를 반환.
    - 우선순위: 환경변수 MAIC_PROMPTS_PATH > ~/.maic/prompts.yaml
    """
    env_path = os.getenv("MAIC_PROMPTS_PATH")
    if env_path:
        p = _expand_user_path(env_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    base = _expand_user_path("~/.maic")
    base.mkdir(parents=True, exist_ok=True)
    return base / "prompts.yaml"

# ============================================================
# 안전한 format_map
# ============================================================
class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"

def _fmt(template: str, values: Dict[str, Any]) -> str:
    try:
        return str(template).format_map(_SafeDict(values))
    except Exception:
        return str(template)

# ============================================================
# 데이터 구조
# ============================================================
@dataclass
class PromptParts:
    system: str
    user: str
    tools: Optional[list] = None
    provider_kwargs: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ModeSpec:
    name: str
    version: str
    system_template: str
    user_template: str
    provider_kwargs: Dict[str, Any]

# ============================================================
# 기본 템플릿
# ============================================================
GLOBAL_DEFAULT = ModeSpec(
    name="GLOBAL",
    version="1.0.0",
    system_template=(
        "너는 학생을 돕는 영어 코치야. 답변은 {lang}로 친절하고 간결하게.\n"
        "사실 확인이 필요한 내용은 조심스럽게 다루고, 모르면 솔직히 모른다고 말해.\n"
        "불필요한 장황함은 피하고, 예시는 짧고 명확하게."
    ),
    user_template="",
    provider_kwargs={"temperature": 0.2, "max_tokens": 1024},
)

MODE_DEFAULTS: Dict[str, ModeSpec] = {
    "문법설명": ModeSpec(
        name="문법설명", version="1.0.0",
        system_template=(
            "역할: 영문법 튜터. 규칙→예외 순서로 설명하고, 마지막에 간단 체크리스트 제공.\n"
            "설명은 국문, 예문은 영어 {examples}."
        ),
        user_template=(
            "질문(문장/규칙): {question}\n"
            "요구사항:\n"
            "1) 핵심 규칙 3줄 요약\n"
            "2) 자주 틀리는 예외 2가지\n"
            "3) 예문 3개(영어/해석)\n"
            "4) 한 줄 마무리 팁\n"
        ),
        provider_kwargs={"temperature": 0.1},
    ),
    "문장구조분석": ModeSpec(
        name="문장구조분석", version="1.0.0",
        system_template=(
            "역할: 문장 구조 분석가.\n"
            "품사 태깅, 구/절 분해, 의존관계 핵심만. 과잉 용어 사용 금지."
        ),
        user_template=(
            "분석 대상 문장: {question}\n"
            "출력 형식:\n"
            "- 품사 태깅(핵심 단어 위주)\n"
            "- 구/절 구조 요약(2~4줄)\n"
            "- 핵심 골격: [S: … | V: … | O: … | C: … | M: …]\n"
            "- 오해하기 쉬운 포인트 1개"
        ),
        provider_kwargs={"temperature": 0.1},
    ),
    "지문분석": ModeSpec(
        name="지문분석", version="1.0.0",
        system_template=(
            "역할: 리딩 코치. 요지와 근거 중심으로 설명하되, 불필요한 요약은 지양."
        ),
        user_template=(
            "지문(또는 질문): {question}\n"
            "원하는 출력:\n"
            "1) 한 줄 요지\n"
            "2) 핵심 논지/전개(3포인트)\n"
            "3) 근거 문장 번호 또는 단서(가능하면)\n"
            "4) 오답유형 주의 1가지"
        ),
        provider_kwargs={"temperature": 0.2},
    ),
}
MODE_ALIASES = {
    "Grammar": "문법설명",
    "Sentence": "문장구조분석",
    "Passage": "지문분석",
    "문장분석": "문장구조분석",
}

def _normalize_mode(mode: str) -> str:
    m = str(mode or "").strip()
    return MODE_ALIASES.get(m, m) if m else "문법설명"

# ============================================================
# 로컬 오버라이드 I/O
# ============================================================
def _deep_merge(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out

def _spec_to_dict(spec: ModeSpec) -> Dict[str, Any]:
    return {
        "name": spec.name,
        "version": spec.version,
        "system": spec.system_template,
        "user": spec.user_template,
        "provider_kwargs": dict(spec.provider_kwargs or {}),
    }

def _build_defaults_dict() -> Dict[str, Any]:
    return {
        "version": 1,
        "global": {
            "system": GLOBAL_DEFAULT.system_template,
            "user": GLOBAL_DEFAULT.user_template,
            "provider_kwargs": dict(GLOBAL_DEFAULT.provider_kwargs),
        },
        "modes": {k: _spec_to_dict(v) for k, v in MODE_DEFAULTS.items()},
    }

def save_overrides(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    try:
        p = get_overrides_path()
        if yaml:
            with p.open("w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        else:
            with p.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        return True, None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

def reset_overrides() -> Tuple[bool, Optional[str]]:
    try:
        p = get_overrides_path()
        if p.exists():
            p.unlink()
        return True, None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

# ============================================================
# Google Drive 연동(옵션) — 최신 prompts.yaml 자동 pull
# ============================================================
_REMOTE_PULL_ONCE_FLAG = {"done": False}

def _drive_service_or_none():
    """
    src.rag.index_build._drive_service() 가 있으면 재사용.
    없거나 라이브러리 미설치면 None.
    """
    try:
        import importlib
        m = importlib.import_module("src.rag.index_build")
        return getattr(m, "_drive_service", None)() if hasattr(m, "_drive_service") else None
    except Exception:
        return None

def _find_drive_prompts_file(svc, folder_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    드라이브에서 prompts.yaml을 최신 수정순으로 찾는다.
    folder_id가 있으면 그 폴더 내부에서만 검색.
    """
    try:
        files = svc.files()
        params = {
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
            "fields": "files(id, name, modifiedTime, parents, mimeType)",
            "pageSize": 10,
            "orderBy": "modifiedTime desc",
        }
        if folder_id:
            q = f"'{folder_id}' in parents and name = 'prompts.yaml' and trashed = false"
        else:
            q = "name = 'prompts.yaml' and trashed = false"
        params["q"] = q
        resp = files.list(**params).execute() or {}
        arr = resp.get("files") or []
        return arr[0] if arr else None
    except Exception:
        return None

def _download_file_bytes(svc, file_id: str) -> Optional[bytes]:
    try:
        # 간단한 방식: get_media().execute() 로 바이트 획득
        req = svc.files().get_media(fileId=file_id, supportsAllDrives=True)
        return req.execute()
    except Exception:
        return None

def _utc_from_rfc3339(s: str) -> datetime:
    # '2025-08-25T09:10:11.000Z' → datetime UTC
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt.astimezone(timezone.utc)

def _pull_remote_overrides_if_newer() -> Optional[str]:
    """
    드라이브의 prompts.yaml 이 로컬보다 최신이면 다운로드하여 저장.
    성공 시 'pulled', 조건 불충족/실패 시 None.
    """
    svc = _drive_service_or_none()
    if not svc:
        return None

    folder_id = os.getenv("MAIC_PROMPTS_DRIVE_FOLDER_ID") or None
    meta = _find_drive_prompts_file(svc, folder_id)
    if not meta:
        return None  # 드라이브에 파일 없음

    # Drive modifiedTime
    drive_mtime = _utc_from_rfc3339(meta.get("modifiedTime"))

    # 로컬 mtime
    local_path = get_overrides_path()
    local_exists = local_path.exists()
    local_mtime = datetime.fromtimestamp(0, tz=timezone.utc)
    if local_exists:
        try:
            local_mtime = datetime.fromtimestamp(local_path.stat().st_mtime, tz=timezone.utc)
        except Exception:
            pass

    if (not local_exists) or (drive_mtime > local_mtime):
        data = _download_file_bytes(svc, meta["id"])
        if not data:
            return None
        # 저장
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(data)
        try:
            # 파일 mtime을 드라이브 시간과 맞춤(선택)
            ts = drive_mtime.timestamp()
            os.utime(local_path, (ts, ts))
        except Exception:
            pass
        return "pulled"

    return None

def _lazy_remote_pull_once():
    # 프로세스 당 최초 1회만 시도(불필요한 API 호출 방지)
    if _REMOTE_PULL_ONCE_FLAG["done"]:
        return
    try:
        _pull_remote_overrides_if_newer()
    finally:
        _REMOTE_PULL_ONCE_FLAG["done"] = True

# ============================================================
# 오버라이드 로딩
# ============================================================
def load_overrides() -> Dict[str, Any]:
    """
    ~/.maic/prompts.yaml (+ 환경변수 경로) 를 로드.
    - 최초 호출 시 1회, 구글드라이브에서 최신본 자동 pull(가능한 환경이면)
    """
    _lazy_remote_pull_once()
    p = get_overrides_path()
    if not p.exists():
        return {}
    try:
        if yaml:
            with p.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        else:
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

# ============================================================
# 스펙 조회/프롬프트 빌드
# ============================================================
def list_modes() -> Dict[str, str]:
    return {k: k for k in MODE_DEFAULTS.keys()}

def get_prompt_spec(mode: str) -> Dict[str, Any]:
    defaults = _build_defaults_dict()
    overrides = load_overrides()
    merged = _deep_merge(defaults, overrides)

    mname = _normalize_mode(mode)
    global_spec = merged.get("global", {}) or {}
    mode_spec = merged.get("modes", {}).get(mname, {}) or {}

    alias = MODE_ALIASES.get(mode)
    if alias and alias in (merged.get("modes") or {}):
        mode_spec = _deep_merge(mode_spec, merged["modes"][alias])

    return {"global": global_spec, "mode": mode_spec}

def build_prompt(mode: str, question: str, *, lang: str = "ko", extras: Optional[Dict[str, Any]] = None) -> PromptParts:
    extras = extras or {}
    values = {
        "question": question or "",
        "mode": _normalize_mode(mode),
        "lang": lang or "ko",
        "today": datetime.now().strftime("%Y-%m-%d"),
        **extras,
    }

    spec = get_prompt_spec(mode)
    g = spec.get("global", {}) or {}
    m = spec.get("mode", {}) or {}

    sys_global = str(g.get("system") or GLOBAL_DEFAULT.system_template)
    usr_global = str(g.get("user") or GLOBAL_DEFAULT.user_template)
    sys_mode   = str(m.get("system") or MODE_DEFAULTS[_normalize_mode(mode)].system_template)
    usr_mode   = str(m.get("user")   or MODE_DEFAULTS[_normalize_mode(mode)].user_template)

    system_text = _fmt(sys_global, values).strip()
    if sys_mode.strip():
        system_text = (system_text + "\n\n" + _fmt(sys_mode, values)).strip()

    user_text = _fmt(usr_global, values).strip()
    if usr_mode.strip():
        user_text = ((user_text + "\n\n") if user_text else "") + _fmt(usr_mode, values)

    pk_global = dict(g.get("provider_kwargs") or {})
    pk_mode   = dict(m.get("provider_kwargs") or {})
    pk_extra  = dict((extras.get("provider_kwargs") or {}))
    provider_kwargs = _deep_merge(_deep_merge(pk_global, pk_mode), pk_extra) or None

    return PromptParts(
        system=system_text,
        user=user_text,
        tools=None,
        provider_kwargs=provider_kwargs,
        meta={"mode": _normalize_mode(mode), "lang": lang},
    )

# ============================================================
# 프로바이더 페이로드 변환 예시
# ============================================================
def to_openai(parts: PromptParts) -> Dict[str, Any]:
    messages = []
    if parts.system.strip():
        messages.append({"role": "system", "content": parts.system})
    if parts.user.strip():
        messages.append({"role": "user", "content": parts.user})
    payload = {"messages": messages}
    if parts.provider_kwargs:
        payload.update(parts.provider_kwargs)
    return payload

def to_gemini(parts: PromptParts) -> Dict[str, Any]:
    full = parts.system.strip()
    if parts.user.strip():
        full = (full + "\n\n" + parts.user.strip()).strip()
    payload = {"contents": [{"role": "user", "parts": [{"text": full}]}]}
    if parts.provider_kwargs:
        payload.update(parts.provider_kwargs)
    return payload

# ============================================================
# 편의: 기본 오버라이드 파일 생성
# ============================================================
def write_default_overrides_if_missing() -> bool:
    p = get_overrides_path()
    if p.exists():
        return False
    data = _build_defaults_dict()
    ok, _ = save_overrides(data)
    return bool(ok)

# ========================== [PM-01] END ============================
