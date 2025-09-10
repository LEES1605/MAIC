# =============================== [01] Agents Common — START ===============================
from __future__ import annotations

from typing import Iterator, Mapping, Dict, Any, Optional
import inspect
import re
from queue import Queue, Empty
from threading import Thread


__all__ = ["_split_sentences", "stream_llm"]


def _split_sentences(text: str) -> list[str]:
    """
    간단한 문장 분리기(영/한 마침부호 기준).
    - 목적: 토막 응답을 '문장' 단위로 자연스럽게 쪼개기
    """
    if not text:
        return []
    parts = re.split(r"(?<=[\.!\?。！？])\s+", text.strip())
    return [p for p in parts if p]


def _build_io_kwargs(
    params: Mapping[str, inspect.Parameter],
    *,
    system_prompt: str,
    user_input: str,
) -> Dict[str, Any]:
    """
    providers API 시그니처(messages/prompt/user_prompt/system|system_prompt)를
    런타임에 탐지하여 kwargs를 구성한다.
    """
    kwargs: Dict[str, Any] = {}
    if "messages" in params:
        kwargs["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]
    else:
        # 프롬프트/시스템 분리 시그니처 대응
        if "prompt" in params:
            kwargs["prompt"] = user_input
        elif "user_prompt" in params:
            kwargs["user_prompt"] = user_input
        if "system_prompt" in params:
            kwargs["system_prompt"] = system_prompt
        elif "system" in params:
            kwargs["system"] = system_prompt
    return kwargs


def stream_llm(
    *,
    system_prompt: str,
    user_input: str,
    split_fallback: bool = True,
) -> Iterator[str]:
    """
    공통 스트리밍 래퍼:
    1) providers.stream_text(**kwargs) 존재 → 그대로 스트림
    2) call_with_fallback(stream+callbacks) → 콜백으로 청크 수신
    3) 미지원 시 call_with_fallback(non-stream) 결과를 문장 분할/직출력

    split_fallback=True  → 폴백 시 문장 단위로 여러 번 방출
                    False → 폴백 시 한 번에 방출(필요 시 상위에서 후처리)
    """
    try:
        from src.llm import providers as prov
    except Exception as e:  # pragma: no cover
        yield f"(오류) provider 로딩 실패: {type(e).__name__}: {e}"
        return

    # 1) stream_text 우선
    st_fn = getattr(prov, "stream_text", None)
    if callable(st_fn):
        params = inspect.signature(st_fn).parameters
        kwargs = _build_io_kwargs(params, system_prompt=system_prompt, user_input=user_input)
        for piece in st_fn(**kwargs):
            yield str(piece or "")
        return

    # 2) call_with_fallback + callbacks
    call = getattr(prov, "call_with_fallback", None)
    if callable(call):
        params = inspect.signature(call).parameters
        kwargs = _build_io_kwargs(params, system_prompt=system_prompt, user_input=user_input)

        q: "Queue[Optional[str]]" = Queue()

        # 금지 네이밍(_on_piece/_runner) 피해서 정의
        def _cb_piece(t: Any) -> None:
            try:
                q.put(str(t or ""))
            except Exception:
                pass

        used_cb = False
        for name in ("on_delta", "on_token", "yield_text"):
            if name in params:
                kwargs[name] = _cb_piece
                used_cb = True
        if "stream" in params:
            kwargs["stream"] = True

        if used_cb:
            def _run() -> None:
                try:
                    call(**kwargs)
                except Exception as e:  # pragma: no cover
                    q.put(f"(오류) {type(e).__name__}: {e}")
                finally:
                    q.put(None)

            th = Thread(target=_run, daemon=True)
            th.start()

            while True:
                try:
                    item = q.get(timeout=0.1)
                except Empty:
                    if not th.is_alive() and q.empty():
                        break
                    continue
                if item is None:
                    break
                yield str(item or "")
            return

        # 콜백 미지원 → non-stream 폴백
        try:
            res = call(**kwargs)
            txt = res.get("text") if isinstance(res, dict) else str(res)
            if split_fallback:
                for chunk in _split_sentences(str(txt or "")):
                    yield chunk
            else:
                yield str(txt or "")
            return
        except Exception as e:  # pragma: no cover
            yield f"(오류) {type(e).__name__}: {e}"
            return

    # 3) provider 부재
    yield "(오류) LLM 어댑터를 찾을 수 없어요."
# ================================ [01] Agents Common — END ================================
