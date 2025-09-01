# ============================ providers.py — FULL REPLACEMENT ===========================
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional

import requests

try:
    import streamlit as st  # type: ignore
except Exception:
    st = None  # pragma: no cover

from src.common.utils import get_secret, logger


def _first(*vals):
    for v in vals:
        if v:
            return v
    return None


def _emit_stream(text: str, on_token=None, on_delta=None, yield_text=None) -> None:
    """간단 스트리밍: 완성 텍스트를 작은 조각으로 쪼개 콜백 호출."""
    if not text:
        return
    chunk = []
    last_emit = time.time()
    for ch in text:
        chunk.append(ch)
        if ch in ".!?\n" or len(chunk) >= 24 or (time.time() - last_emit) > 0.06:
            piece = "".join(chunk)
            if callable(on_token):
                try:
                    on_token(piece)
                except Exception:
                    pass
            if callable(on_delta):
                try:
                    on_delta(piece)
                except Exception:
                    pass
            if callable(yield_text):
                try:
                    yield_text(piece)
                except Exception:
                    pass
            chunk = []
            last_emit = time.time()
    if chunk:
        piece = "".join(chunk)
        if callable(on_token):
            try:
                on_token(piece)
            except Exception:
                pass
        if callable(on_delta):
            try:
                on_delta(piece)
            except Exception:
                pass
        if callable(yield_text):
            try:
                yield_text(piece)
            except Exception:
                pass


def _openai_chat(
    messages: Optional[list[dict]] = None,
    prompt: Optional[str] = None,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = 0.2,
    timeout_s: Optional[int] = 30,
) -> Optional[str]:
    key = _first(os.getenv("OPENAI_API_KEY"), get_secret("OPENAI_API_KEY", ""))
    if not key:
        return None
    model = model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    url = os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if not messages:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if prompt:
            messages.append({"role": "user", "content": prompt})
    data = {"model": model, "messages": messages, "temperature": float(temperature or 0.2)}
    try:
        r = requests.post(url, headers=headers, json=data, timeout=timeout_s or 30)
        r.raise_for_status()
        j = r.json()
        return j["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger().warning(f"OpenAI call failed: {type(e).__name__}: {e}")
        return None


def _gemini_chat(
    messages: Optional[list[dict]] = None,
    prompt: Optional[str] = None,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = 0.2,
    timeout_s: Optional[int] = 30,
) -> Optional[str]:
    key = _first(os.getenv("GEMINI_API_KEY"), get_secret("GEMINI_API_KEY", ""))
    if not key:
        return None
    model = model or os.getenv("GEMINI_MODEL") or "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

    # 메시지/프롬프트 합성(간단)
    text = ""
    if messages:
        parts = []
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, list):
                content = " ".join([c.get("text", "") if isinstance(c, dict) else str(c) for c in content])
            parts.append(content)
        text = "\n\n".join([p for p in parts if p])
    else:
        text = ((system_prompt or "") + "\n\n" + (prompt or "")).strip()

    payload = {"contents": [{"parts": [{"text": text}]}], "generationConfig": {"temperature": float(temperature or 0.2)}}
    try:
        r = requests.post(url, json=payload, timeout=timeout_s or 30)
        r.raise_for_status()
        j = r.json()
        cands = (j.get("candidates") or [])
        if not cands:
            return None
        parts = (cands[0].get("content") or {}).get("parts") or []
        return "".join([p.get("text", "") for p in parts]).strip()
    except Exception as e:
        logger().warning(f"Gemini call failed: {type(e).__name__}: {e}")
        return None


def call_with_fallback(
    *,
    messages: Optional[list[dict]] = None,
    prompt: Optional[str] = None,
    user_prompt: Optional[str] = None,
    system_prompt: Optional[str] = None,
    system: Optional[str] = None,
    mode_token: Optional[str] = None,
    mode: Optional[str] = None,
    temperature: Optional[float] = 0.2,
    temp: Optional[float] = None,
    timeout_s: Optional[int] = 30,
    timeout: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
    stream: bool = False,
    on_token: Optional[callable] = None,
    on_delta: Optional[callable] = None,
    yield_text: Optional[callable] = None,
) -> Dict[str, Any]:
    """OpenAI → Gemini → 로컬 에코 순으로 시도. dict {'text': str} 반환."""
    system_prompt = _first(system_prompt, system)
    prompt = _first(prompt, user_prompt)
    t = float(_first(temperature, temp) or 0.2)
    to = int(_first(timeout_s, timeout) or 30)

    # 1) OpenAI
    text = _openai_chat(
        messages=messages,
        prompt=prompt,
        system_prompt=system_prompt,
        model=os.getenv("OPENAI_MODEL"),
        temperature=t,
        timeout_s=to,
    )
    if text:
        if stream and (on_token or on_delta or yield_text):
            _emit_stream(text, on_token=on_token, on_delta=on_delta, yield_text=yield_text)
        return {"text": text, "provider": "openai"}

    # 2) Gemini
    text = _gemini_chat(
        messages=messages,
        prompt=prompt,
        system_prompt=system_prompt,
        model=os.getenv("GEMINI_MODEL"),
        temperature=t,
        timeout_s=to,
    )
    if text:
        if stream and (on_token or on_delta or yield_text):
            _emit_stream(text, on_token=on_token, on_delta=on_delta, yield_text=yield_text)
        return {"text": text, "provider": "gemini"}

    # 3) Local fallback (항상 성공)
    base = (prompt or "") or ""
    if not base and messages:
        for m in reversed(messages):
            if m.get("role") == "user":
                base = m.get("content", "")
                break
    base = str(base or "").strip()
    if not base:
        text = "안내: 질문이 비어 있습니다. 한 줄로 질문을 입력해 주세요."
    else:
        text = (
            f"요청을 확인했습니다. 핵심 주제: {base[:64]}...\n"
            f"- 간단한 답변을 진행할게요. 필요하면 예시/추가설명도 붙일 수 있어요."
        )
    if stream and (on_token or on_delta or yield_text):
        _emit_stream(text, on_token=on_token, on_delta=on_delta, yield_text=yield_text)
    return {"text": text, "provider": "local"}
# ============================ providers.py — END =======================================
