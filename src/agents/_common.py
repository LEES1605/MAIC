# src/agents/_common.py
# -----------------------------------------------------------------------------
# Agents common helpers (single source of truth for streaming + helpers)
# - 목적: responder.py / evaluator.py 가 공통 스트리밍 헬퍼를 사용하도록 통합
# - 시그니처: stream_llm(system_prompt=..., user_input=..., split_fallback=True)
#   * 호출자(responder/evaluator)의 키워드 인자와 정확히 일치
# -----------------------------------------------------------------------------
from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Thread
from typing import Any, Callable, Dict, Iterable, Iterator, List, Mapping, Optional

__all__ = [
    "_split_sentences",
    "StreamState",
    "_on_piece",
    "_runner",
    "stream_llm",
]

# -------------------------- sentence segmentation ---------------------------
_SENT_SEP = re.compile(
    r"(?<=[\.\?!。？！…])\s+|"  # 일반 문장부호 + 공백
    r"(?<=\n)\s*|"              # 줄바꿈
    r"(?<=[;:])\s+"             # 세미콜론/콜론
)


def _split_sentences(text: str) -> List[str]:
    """
    간단·견고한 문장 분리기.
    - 한국어/영어 혼합 입력에서도 작동
    - 공백 정리 및 빈 토큰 제거
    """
    if not isinstance(text, str) or not text.strip():
        return []
    raw = re.sub(r"\s+", " ", text.strip())
    parts = [p.strip() for p in _SENT_SEP.split(raw)]
    return [p for p in parts if p]


# ---------------------------- streaming helpers -----------------------------
@dataclass
class StreamState:
    """스트리밍 누적 버퍼 상태."""
    buffer: str = ""


def _on_piece(state: StreamState, piece: Optional[str], emit: Callable[[str], None]) -> None:
    """
    조각(piece)을 누적하고 emitter로 전달.
    - piece가 None/공백이면 무시
    - emit 예외는 상위에서 처리(여기서는 전파)
    """
    if not piece:
        return
    s = str(piece)
    state.buffer += s
    emit(s)


def _runner(chunks: Iterable[str], on_piece: Callable[[str], None]) -> None:
    """
    제너레이터/이터러블에서 조각을 꺼내 콜백(on_piece)에 전달.
    - pieces가 문자열이 아닐 수도 있어 str() 강제
    - StopIteration 이외 예외는 상위에서 처리
    """
    for c in chunks:
        on_piece(str(c))


# ---------------------------- providers adapter -----------------------------
def _build_io_kwargs(
    params: Mapping[str, inspect.Parameter],
    *,
    system_prompt: str,
    user_input: str,
) -> Dict[str, Any]:
    """
    providers API 시그니처에 맞춰 안전하게 kwargs 구성.
    - messages/(prompt|user_prompt) + (system_prompt|system) 모두 대응
    """
    kwargs: Dict[str, Any] = {}
    if "messages" in params:
        kwargs["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]
    else:
        # user 입력
        if "prompt" in params:
            kwargs["prompt"] = user_input
        elif "user_prompt" in params:
            kwargs["user_prompt"] = user_input
        # system 입력
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
    공통 LLM 스트리밍 제너레이터.
    우선순위:
      1) providers.stream_text()가 있으면 그대로 사용
      2) providers.call_with_fallback() + callbacks(on_delta/on_token/yield_text)
         - 콜백 지원 시: Thread + Queue 로 실제 스트리밍
         - 콜백 미지원 시: 최종 텍스트 반환 → 필요 시 문장 단위 분할
      3) 전부 실패하면 에러 메시지
    """
    try:
        from src.llm import providers as prov  # lazy import
    except Exception as e:  # pragma: no cover
        yield f"(오류) provider 로딩 실패: {type(e).__name__}: {e}"
        return

    # 1) stream_text(...)
    stream_fn = getattr(prov, "stream_text", None)
    if callable(stream_fn):
        params = inspect.signature(stream_fn).parameters
        kwargs = _build_io_kwargs(
            params, system_prompt=system_prompt, user_input=user_input
        )
        for piece in stream_fn(**kwargs):
            yield str(piece or "")
        return

    # 2) call_with_fallback(..., stream=True, callbacks=...)
    call = getattr(prov, "call_with_fallback", None)
    if callable(call):
        params = inspect.signature(call).parameters
        kwargs = _build_io_kwargs(
            params, system_prompt=system_prompt, user_input=user_input
        )

        q: "Queue[Optional[str]]" = Queue()

        def _cb_on_piece(t: Any) -> None:
            try:
                q.put(str(t or ""))
            except Exception:
                # 콜백 예외는 무시(안전)
                pass

        used_cb = False
        for name in ("on_delta", "on_token", "yield_text"):
            if name in params:
                kwargs[name] = _cb_on_piece
                used_cb = True
        if "stream" in params:
            kwargs["stream"] = True

        if used_cb:
            def _runner_call() -> None:
                try:
                    call(**kwargs)
                except Exception as e:  # pragma: no cover
                    q.put(f"(오류) {type(e).__name__}: {e}")
                finally:
                    q.put(None)

            th = Thread(target=_runner_call, daemon=True)
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

        # 콜백 미지원 → 단발 호출
        try:
            res = call(**kwargs)
        except Exception as e:  # pragma: no cover
            yield f"(오류) {type(e).__name__}: {e}"
            return

        txt = res.get("text") if isinstance(res, dict) else str(res)
        if not split_fallback:
            yield str(txt or "")
            return
        # 문장 단위 분할
        for chunk in _split_sentences(str(txt or "")):
            yield chunk
        return

    # 3) provider 부재
    yield "(오류) LLM 어댑터를 찾을 수 없어요."
