# =============== [LLM-01] IMPORTS & SECRET HELPER — START =================
from __future__ import annotations

import importlib  # ← 누락으로 F821 발생 → 추가
import json
import os
import traceback
from typing import Any, Dict, Optional

import requests

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
    """Streamlit secrets 우선 → 환경변수. 불가하면 default."""
    try:
        val: Optional[str] = None
        if st is not None and hasattr(st, "secrets"):
            v = st.secrets.get(name)  # 가드 후 접근 → ignore 불필요
            if v is not None:
                val = v if isinstance(v, str) else str(v)
        if val is None:
            val = os.getenv(name, default)
        return val
    except Exception:
        return os.getenv(name, default)
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

    # 정적 임포트 대신 동적 로드(타입 스텁 미비 회피)
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


# -------- Gemini -------------------------------------------------------------
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
    mdl_env = _secret("LLM_MODEL") or "gemini-1.5-pro"
    model = model or mdl_env

    if not api_key:
        return {"ok": False, "provider": "gemini", "error": "missing_api_key", "text": ""}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    # Gemini request body (text-only)
    contents = []
    if system:
        contents.append({"role": "user", "parts": [{"text": f"[SYSTEM]\n{system}"}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    try:
        r = requests.post(
            url,
            timeout=45,
            headers={"Content-Type": "application/json"},
            json={
                "contents": contents,
                "generationConfig": {"temperature": float(temperature)},
            },
        )
        if r.status_code != 200:
            return {
                "ok": False,
                "provider": "gemini",
                "error": f"http_{r.status_code}: {r.text[:400]}",
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


# -------- Fallback orchestrator ----------------------------------------------
def call_with_fallback(
    *,
    system: str,
    prompt: str,
    prefer: str = "gemini",  # "gemini" | "openai"
    temperature: float = 0.2,
) -> Dict[str, Any]:
    """
    우선순위 제공자 실패 시 다른 쪽으로 폴백. 텍스트만 반환.
    """
    order = ["gemini", "openai"] if prefer == "gemini" else ["openai", "gemini"]
    last: Dict[str, Any] | None = None
    for name in order:
        if name == "gemini":
            res = call_gemini_raw(system=system, prompt=prompt, temperature=temperature)
        else:
            res = call_openai_raw(system=system, prompt=prompt, temperature=temperature)
        if res.get("ok"):
            return res
        last = res
    return last or {"ok": False, "provider": "unknown", "error": "all_failed", "text": ""}
# ============================= providers.py — END ============================
