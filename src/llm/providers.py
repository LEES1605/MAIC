# ================================ llm/providers.py — START ======================
from __future__ import annotations

import os
from typing import Any, Dict, Optional


def _from_env_or_secrets(key: str) -> Optional[str]:
    val = os.getenv(key)
    if val:
        return val
    try:
        import streamlit as st

        v = st.secrets.get(key)
        return str(v) if v else None
    except Exception:
        return None


# -------- OpenAI ---------------------------------------------------------------
def call_openai(
    *,
    system: str,
    user: str,
    model: Optional[str] = None,
    temperature: float = 0.2,
    stream: bool = False,
    **kwargs: Any,
) -> str:
    """
    OpenAI Chat Completions(비스트리밍 기본). 라이브러리 미설치/키 없음은 예외.
    """
    key = _from_env_or_secrets("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY 가 없습니다.")

    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("openai 라이브러리가 설치되어 있지 않습니다.") from e

    client = OpenAI(api_key=key)  # type: ignore

    mdl = model or _from_env_or_secrets("OPENAI_MODEL") or "gpt-4o-mini"
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]

    if stream:
        # Streamlit 쪽에서 토큰 단위로 받도록 상위에서 처리(여기선 단순화).
        with client.chat.completions.stream.create(model=mdl, messages=msgs) as s:  # type: ignore[attr-defined]
            out = []
            for event in s:
                delta = getattr(event, "delta", None)
                if not delta:
                    continue
                c = getattr(delta, "content", None)
                if c:
                    out.append(str(c))
            return "".join(out)

    res = client.chat.completions.create(  # type: ignore[attr-defined]
        model=mdl,
        messages=msgs,
        temperature=float(temperature),
    )
    text = res.choices[0].message.content or ""  # type: ignore[assignment]
    return str(text)


# -------- Gemini ---------------------------------------------------------------
def call_gemini(
    *,
    system: str,
    user: str,
    model: Optional[str] = None,
    temperature: float = 0.2,
    **kwargs: Any,
) -> str:
    """
    Google Gemini 호출(간단 버전). 키/라이브러리 없으면 예외.
    """
    key = _from_env_or_secrets("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY 가 없습니다.")
    try:
        import google.generativeai as genai  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("google-generativeai 라이브러리가 설치되어 있지 않습니다.") from e

    genai.configure(api_key=key)  # type: ignore
    mdl = model or _from_env_or_secrets("LLM_MODEL") or "models/gemini-1.5-pro"
    prompt = f"[SYSTEM]\n{system}\n\n[USER]\n{user}"
    m = genai.GenerativeModel(mdl)  # type: ignore
    out = m.generate_content(prompt, generation_config={"temperature": float(temperature)})  # type: ignore
    return str(getattr(out, "text", "") or "")


# -------- Fallback -------------------------------------------------------------
def call_with_fallback(
    *,
    system: str,
    user: str,
    prefer: str = "gemini",  # "openai" | "gemini"
    **kwargs: Any,
) -> str:
    """
    우선 호출 실패 시 다른 프로바이더로 자동 폴백.
    """
    order = ["gemini", "openai"] if prefer == "gemini" else ["openai", "gemini"]
    last_err: Optional[str] = None
    for name in order:
        try:
            if name == "openai":
                return call_openai(system=system, user=user, **kwargs)
            if name == "gemini":
                return call_gemini(system=system, user=user, **kwargs)
        except Exception as e:  # pragma: no cover
            last_err = f"{name}: {e}"
            continue
    raise RuntimeError(f"모든 LLM 호출이 실패했습니다. last={last_err}")
# ================================= llm/providers.py — END =======================
