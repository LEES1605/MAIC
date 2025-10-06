# =============== [LLM-01] IMPORTS & SECRET HELPER — START =================
from __future__ import annotations

import importlib
import json
import os
import traceback
from typing import Any, Dict, Optional, Callable

# streamlit은 있을 수도/없을 수도 있다.
# - mypy 충돌 방지: st를 먼저 Any로 선언한 뒤, 런타임에 모듈 또는 None을 대입
from typing import Any as _AnyForSt

st: _AnyForSt | None
try:
    import streamlit as _st_mod
    st = _st_mod
except Exception:
    st = None  # Optional[Any] 취급 → mypy OK


def _secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """ConfigManager를 사용한 설정값 조회"""
    from src.core.config_manager import get_config_manager
    return get_config_manager().get_optional_string(name, default)
# ================ [LLM-01] IMPORTS & SECRET HELPER — END ==================


# =============== [LLM-02] OpenAI raw call — START =================
def call_openai_raw(
    *,
    system: str,
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.2,
) -> Dict[str, Any]:
    """
    OpenAI Chat Completions (비스트리밍 단순 버전)
    응답: {"ok": bool, "provider":"openai", "text": str, "error": str|None}
    """
    api_key = _secret("OPENAI_API_KEY")
    mdl = model or _secret("OPENAI_MODEL") or "gpt-4o-mini"
    if not api_key:
        return {"ok": False, "provider": "openai", "error": "missing_api_key", "text": ""}

    # 동적 import로 타입 스텁/설치 유무에 둔감
    try:
        mod = importlib.import_module("openai")
        OpenAI: Any = getattr(mod, "OpenAI", None)
        if OpenAI is None:
            return {
                "ok": False,
                "provider": "openai",
                "error": "openai.OpenAI not found",
                "text": "",
            }
    except Exception as e:
        return {
            "ok": False,
            "provider": "openai",
            "error": f"openai_import_error: {e}",
            "text": "",
        }

    try:
        client: Any = OpenAI(api_key=api_key)
        res: Any = client.chat.completions.create(
            model=mdl,
            temperature=float(temperature),
            messages=[
                {"role": "system", "content": system or ""},
                {"role": "user", "content": prompt or ""},
            ],
        )
        txt = res.choices[0].message.content or ""
        return {"ok": True, "provider": "openai", "text": str(txt), "error": None}
    except Exception as e:
        return {
            "ok": False,
            "provider": "openai",
            "error": f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
            "text": "",
        }
# ================ [LLM-02] OpenAI raw call — END ==================


# ============================ [03] Gemini raw call — START ============================
def call_gemini_raw(
    *,
    system: str,
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.2,
) -> Dict[str, Any]:
    """
    Google Generative Language API(REST) 단순 호출
    응답: {"ok": bool, "provider":"gemini", "text": str, "error": str|None}
    """
    api_key = _secret("GEMINI_API_KEY")
    mdl_env = _secret("LLM_MODEL") or _secret("GEMINI_MODEL") or "gemini-1.5-pro"
    model = model or mdl_env

    if not api_key:
        return {"ok": False, "provider": "gemini", "error": "missing_api_key", "text": ""}

    # requests를 동적 import → Any로 취급하여 mypy 속성 경고 방지
    try:
        requests_mod: Any = importlib.import_module("requests")
    except Exception as e:
        return {
            "ok": False,
            "provider": "gemini",
            "error": f"requests_import_error: {e}",
            "text": "",
        }

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )

    # Gemini request body (text-only)
    contents = []
    if system:
        contents.append({"role": "user", "parts": [{"text": f"[SYSTEM]\n{system}"}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    try:
        r = requests_mod.post(
            url,
            timeout=45,
            headers={"Content-Type": "application/json"},
            json={
                "contents": contents,
                "generationConfig": {"temperature": float(temperature)},
            },
        )
        status = getattr(r, "status_code", 500)
        if status != 200:
            txt = getattr(r, "text", "") or ""
            return {
                "ok": False,
                "provider": "gemini",
                "error": f"http_{status}: {txt[:400]}",
                "text": "",
            }
        data = r.json()
        text = ""
        if isinstance(data, dict):
            cands = data.get("candidates") or []
            if cands and isinstance(cands, list):
                parts = (cands[0].get("content") or {}).get("parts") or []
                if parts and isinstance(parts, list):
                    text = str(parts[0].get("text") or "")
        return {"ok": True, "provider": "gemini", "text": text, "error": None}
    except Exception as e:
        return {
            "ok": False,
            "provider": "gemini",
            "error": f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
            "text": "",
        }
# ============================= [03] Gemini raw call — END =============================


# =============== [LLM-04] call_with_fallback — START =================
def call_with_fallback(
    *,
    # 기본 인자 (app.py가 검사하는 시그니처와 하위호환)
    system: str = "",
    prompt: str = "",
    # 우선순위
    prefer: str = "gemini",  # "gemini" | "openai"
    # 옵션/별칭(예상치 못한 키워드가 와도 안전)
    temperature: float = 0.2,
    temp: Optional[float] = None,
    timeout_s: Optional[int] = None,
    timeout: Optional[int] = None,
    mode_token: Optional[str] = None,
    mode: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    # 스트리밍
    stream: Optional[bool] = None,
    on_token: Optional[Callable[[str], None]] = None,
    on_delta: Optional[Callable[[str], None]] = None,
    yield_text: Optional[Callable[[str], None]] = None,
    # 알 수 없는 추가 인자는 조용히 무시(호환성)
    **_: Any,
) -> Dict[str, Any]:
    """
    우선순위 제공자 실패 시 다른 쪽으로 폴백.
    - 스트리밍 콜백(on_token/on_delta/yield_text)이 있으면 '토큰 단위'로 흘립니다.
    - 콜백이 없으면 완성된 텍스트만 반환합니다.
    반환: {"ok": bool, "provider": str, "text": str, "error": str|None}
    """
    # 별칭 정규화
    temperature = float(temp if isinstance(temp, (int, float)) else temperature)

    order = ["gemini", "openai"] if prefer == "gemini" else ["openai", "gemini"]
    last: Dict[str, Any] | None = None

    for name in order:
        if name == "gemini":
            res = call_gemini_raw(system=system, prompt=prompt, temperature=temperature)
        else:
            res = call_openai_raw(system=system, prompt=prompt, temperature=temperature)

        if res.get("ok"):
            text = str(res.get("text") or "")

            # 스트리밍 요청/콜백 처리 — None 가드로 mypy/misc 오류 제거
            streamer = on_token or on_delta or yield_text
            cb = streamer if callable(streamer) else None
            if (stream or cb) and text:
                try:
                    if cb is not None:
                        # 성능 최적화: PerformanceManager를 사용한 적응형 청킹
                        from src.core.performance_manager import optimize_streaming
                        optimize_streaming(text, cb)
                except (RuntimeError, OSError) as e:
                    from src.common.utils import errlog
                    errlog(f"스트리밍 처리 오류: {e}", "stream_llm", e)
                    pass

            return {"ok": True, "provider": name, "text": text, "error": None}
        last = res

    return last or {"ok": False, "provider": "unknown", "error": "all_failed", "text": ""}
# ================ [LLM-04] call_with_fallback — END =================
