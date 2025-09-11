# =============== [LLM-01] IMPORTS & SECRET HELPER — START =================
from __future__ import annotations

import importlib
import json
import os
import traceback
from typing import Any, Dict, Optional, Callable, Iterator, List

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
    """
    Streamlit secrets 우선 → 환경변수. 실패 시 default.
    - 반환은 문자열(딕셔너리/리스트면 JSON 문자열)로 통일
    """
    try:
        if st is not None and hasattr(st, "secrets"):
            v = st.secrets.get(name)
            if v is not None:
                return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        return os.getenv(name, default)
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
        # v1 client (python-openai>=1.0) 기준
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
        # 구버전 등 다양한 케이스를 안전하게 포착
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
    contents: list[dict] = []
    if system:
        contents.append({"role": "user", "parts": [{"text": f"[SYSTEM]\n{system}"}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    try:
        r = requests_mod.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "contents": contents,
                "generationConfig": {"temperature": float(temperature)},
            },
            timeout=30,
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
    # 기본 인자 (소비자 시그니처와 하위호환)
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
                        for ch in text:
                            try:
                                cb(ch)  # 한 토큰(여기선 글자)씩 전달
                            except Exception:
                                # 콜백 오류는 UX를 깨지 않도록 무시
                                pass
                except Exception:
                    pass

            return {"ok": True, "provider": name, "text": text, "error": None}
        last = res

    return last or {"ok": False, "provider": "unknown", "error": "all_failed", "text": ""}
# ================ [LLM-04] call_with_fallback — END =================


# =========================== [LLM-05] stream_text — START ===========================
def stream_text(
    *,
    # 메신저 스타일
    messages: Optional[List[Dict[str, str]]] = None,
    # 단문 스타일
    prompt: str = "",
    user_prompt: str = "",
    # 시스템 입력
    system_prompt: str = "",
    system: str = "",
    # 선택: 라우팅/온도
    prefer: str = "gemini",
    temperature: float = 0.2,
    # 알 수 없는 추가 인자는 무시
    **kwargs: Any,
) -> Iterator[str]:
    """
    소비자 우선 경로. 입력을 정규화하여 call_with_fallback(stream+콜백)로 연결.
    - messages가 있으면 마지막 user.content를 우선
    - 없으면 prompt → user_prompt 순으로 사용자 입력을 결정
    - 시스템 프롬프트는 system_prompt → system 순
    """
    sys_txt = (system_prompt or system or "").strip()

    user_txt = ""
    if messages:
        try:
            # 마지막 user role content 사용(없으면 전체 messages를 이어붙임)
            users = [m.get("content", "") for m in messages if (m.get("role") == "user")]
            user_txt = users[-1] if users else ""
            if not user_txt:
                user_txt = " ".join(m.get("content", "") for m in messages)
        except Exception:
            user_txt = ""
    if not user_txt:
        user_txt = (prompt or user_prompt or "").strip()

    # 콜백 기반 실스트리밍 → 안전한 큐-스레드 패턴
    from queue import Queue, Empty
    from threading import Thread

    q: "Queue[Optional[str]]" = Queue()

    def _cb(piece: str) -> None:
        try:
            q.put(str(piece or ""))
        except Exception:
            pass

    def _runner() -> None:
        try:
            # stream=True + 콜백 등록
            _ = call_with_fallback(
                system=sys_txt,
                prompt=user_txt,
                prefer=prefer,
                temperature=temperature,
                stream=True,
                on_token=_cb,  # 소비자 쪽 호환: on_delta/yield_text 도 수용하므로 on_token 사용
            )
        except Exception:
            # 콜백 기반 스트림 실패 시에도 종료 신호는 보장
            pass
        finally:
            q.put(None)

    th = Thread(target=_runner, daemon=True)
    th.start()

    while True:
        try:
            item = q.get(timeout=0.2)
        except Empty:
            if not th.is_alive() and q.empty():
                break
            continue
        if item is None:
            break
        yield str(item or "")
# =========================== [LLM-05] stream_text — END ===========================
