# ============================ providers.py — START ===========================
from __future__ import annotations
import os, json, requests, traceback
from typing import Any, Dict, Optional

def _secret(name: str, default: Optional[str] = None) -> Optional[str]:
    # Streamlit secrets 우선 → 환경변수
    try:
        import streamlit as st  # type: ignore
        val = st.secrets.get(name)  # type: ignore[attr-defined]
        if val is None:
            return os.getenv(name, default)
        if isinstance(val, str):
            return val
        return json.dumps(val, ensure_ascii=False)
    except Exception:
        return os.getenv(name, default)

def _strip(s: Optional[str]) -> str:
    return (s or "").strip()

# ── Gemini ───────────────────────────────────────────────────────────────────
def call_gemini(prompt: str, *, system: Optional[str] = None,
                temperature: float = 0.3, max_tokens: int = 1024) -> Dict[str, Any]:
    api_key = _secret("GEMINI_API_KEY")
    model   = _secret("GEMINI_MODEL", "gemini-1.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    if not api_key:
        return {"ok": False, "provider": "gemini", "error": "missing_api_key"}

    # Gemini request body (text-only)
    contents = []
    if system:
        contents.append({"role": "user", "parts": [{"text": f"[SYSTEM]\n{system}"}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    try:
        r = requests.post(
            url, timeout=45,
            headers={"Content-Type": "application/json"},
            json={
                "contents": contents,
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens
                }
            }
        )
        r.raise_for_status()
        data = r.json()
        text = ""
        for cand in (data.get("candidates") or []):
            parts = (((cand or {}).get("content") or {}).get("parts") or [])
            for p in parts:
                if "text" in p:
                    text += p["text"]
        text = _strip(text)
        if not text:
            return {"ok": False, "provider": "gemini", "error": "empty_response"}
        return {"ok": True, "provider": "gemini", "text": text}
    except Exception as e:
        return {"ok": False, "provider": "gemini",
                "error": f"{type(e).__name__}: {e}\n{traceback.format_exc()}"}

# ── OpenAI ───────────────────────────────────────────────────────────────────
def call_openai(prompt: str, *, system: Optional[str] = None,
                temperature: float = 0.3, max_tokens: int = 1024) -> Dict[str, Any]:
    api_key = _secret("OPENAI_API_KEY")
    model   = _secret("OPENAI_MODEL", "gpt-4o-mini")
    url = "https://api.openai.com/v1/chat/completions"

    if not api_key:
        return {"ok": False, "provider": "openai", "error": "missing_api_key"}

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        r = requests.post(
            url, timeout=45,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False
            }
        )
        r.raise_for_status()
        data = r.json()
        text = _strip(((data.get("choices") or [{}])[0].get("message") or {}).get("content"))
        if not text:
            return {"ok": False, "provider": "openai", "error": "empty_response"}
        return {"ok": True, "provider": "openai", "text": text}
    except Exception as e:
        return {"ok": False, "provider": "openai",
                "error": f"{type(e).__name__}: {e}\n{traceback.format_exc()}"}

# ── Fallback orchestrator ────────────────────────────────────────────────────
def call_with_fallback(prompt: str, *, system: Optional[str] = None,
                       primary: str = "gemini", secondary: str = "openai",
                       temperature: float = 0.3, max_tokens: int = 1024) -> Dict[str, Any]:
    order = [primary, secondary] if secondary else [primary]
    last_err = None
    for prov in order:
        if prov == "gemini":
            r = call_gemini(prompt, system=system, temperature=temperature, max_tokens=max_tokens)
        elif prov == "openai":
            r = call_openai(prompt, system=system, temperature=temperature, max_tokens=max_tokens)
        else:
            r = {"ok": False, "error": f"unknown_provider:{prov}"}
        if r.get("ok"):
            return r
        last_err = r.get("error")
    return {"ok": False, "provider": "/".join(order), "error": last_err or "all_failed"}
# ============================= providers.py — END ============================
