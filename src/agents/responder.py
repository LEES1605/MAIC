# ================================ [01] Answer Stream — START ================================
from __future__ import annotations

from typing import Iterator, Dict, Any, Optional, List, Callable, Mapping
import inspect
import re
from queue import Queue, Empty
from threading import Thread

from src.agents._common import _split_sentences, _on_piece, _build_io_kwargs, _errlog, StreamState

def _system_prompt(mode: str) -> str:
    hint = {
        "문법설명": "핵심 규칙 → 간단 예시 → 흔한 오해 순서로 쉽게 설명하세요.",
        "문장구조분석": "품사/구문 역할을 표처럼 정리하고 핵심 포인트 3개를 요약하세요.",
        "지문분석": "주제/요지/세부정보를 구분하고 근거 문장을 제시하세요.",
    }.get(mode, "")
    return (
        "당신은 문법 선생님 '피티쌤'입니다. 친절하고 쉽게 설명하며, 질문과 대화 형식으로 진행하세요. " + hint
    )

def _iter_provider_stream(
    *, system_prompt: str, question: str
) -> Iterator[str]:
    """
    가능한 경우 실제 스트리밍으로 토막을 yield.
    - 우선순위: providers.stream_text → call_with_fallback(stream+callbacks)
    - 전부 불가하면 문장 단위로 분할하여 의사-스트리밍
    """
    try:
        from src.llm import providers as prov
    except Exception as e:
        prov = None
        _errlog(f"providers import failed: {e}", where="[responder.stream]", exc=e)
    call = None
    if prov:
        call = getattr(prov, "stream_text", None) or getattr(prov, "call_with_fallback", None)
    if callable(call):
        params = inspect.signature(call).parameters
        kwargs = _build_io_kwargs(params, system_prompt=system_prompt, user_prompt=question)
        used_cb = False

        # Prepare streaming callback and thread runner
        q: "Queue[Optional[str]]" = Queue()
        state = StreamState()
        def _piece_callback(t: Optional[str]) -> None:
            try:
                _on_piece(state, t, lambda s: q.put(s))
            except Exception:
                pass

        for name in ("on_delta", "on_token", "yield_text"):
            if name in params:
                kwargs[name] = _piece_callback
                used_cb = True
        if "stream" in params:
            kwargs["stream"] = True

        if used_cb:
            def runner() -> None:
                try:
                    call(**kwargs)
                except Exception as e:  # pragma: no cover
                    _errlog(f"provider call error: {e}", where="[responder.stream]", exc=e)
                    q.put(f"(오류) {type(e).__name__}: {e}")
                finally:
                    q.put(None)
            th = Thread(target=runner, daemon=True)
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

        # 콜백 미지원 → 최종 텍스트 분할 의사-스트리밍
        try:
            res = call(**kwargs)
            txt = res.get("text") if isinstance(res, dict) else str(res)
            for chunk in _split_sentences(str(txt or "")):
                yield chunk
            return
        except Exception as e:  # pragma: no cover
            _errlog(f"provider call failed: {e}", where="[responder.stream]", exc=e)
            yield f"(오류) {type(e).__name__}: {e}"
            return

    # 어떤 provider도 없으면 메시지 출력
    yield "(오류) LLM 어댑터를 찾을 수 없어요."

def answer_stream(
    *, question: str, mode: str, ctx: Optional[Dict[str, Any]] = None
) -> Iterator[str]:
    """
    주답변(피티쌤) 스트리밍 제너레이터.
    App 단에서 문장 버퍼링을 적용하므로, 여기서는 '토막'을 잘게 흘려보내면 됩니다.
    """
    system_prompt = _system_prompt(mode)
    # 필요 시 ctx 활용 여지(예: RAG 요약 삽입) — 현 단계에선 미사용
    yield from _iter_provider_stream(system_prompt=system_prompt, question=question)
# ================================= [01] Answer Stream — END =================================
