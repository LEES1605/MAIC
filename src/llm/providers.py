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
        import importlib
        from typing import Any as _Any
        requests_mod: _Any = importlib.import_module("requests")
    except Exception as e:
        return {
            "ok": False,
            "provider": "gemini",
            "error": f"requests_import_error: {e}",
            "text": "",
        }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

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
        import traceback
        return {
            "ok": False,
            "provider": "gemini",
            "error": f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
            "text": "",
        }
# ============================= [03] Gemini raw call — END =============================
