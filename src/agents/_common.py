# src/agents/_common.py
# -----------------------------------------------------------------------------
# Agents common helpers
# - 목적: responder.py / evaluator.py가 공통 스트리밍 API를 사용하도록 단일화
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
    "_on_piece",
    "_runner",
    "StreamState",
    "stream_llm",
]

# -------------------------- sentence segmentation ---------------------------
_SENT_SEP = re.compile(
    r"(?<=[\.\?!。？！…])\s+|"  # 일반 문장부호 + 공백
    r"(?<=\n)\s*|"              # 줄바꿈
    r"(?<=[;:])\s+"            # 세미콜론/콜론
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
    p = str(piece)
    state.buffer += p
    emit(p)

def _runner(chunks: Iterable[str], on_piece: Callable[[str], None]) -> None:
    """
    제너레이터/이터러블에서 조각을 꺼내 콜백(on_piece)에 전달.
    - pieces가 문자열이 아닐 수도 있어 str() 강제
    - StopIteration 이외 예외는 상위에서 처리
    """
    for c in chunks:
        on_piece(str(c))

# ----------------------------- public stream API -----------------------------
def _build_io_kwargs(
    params: Mapping[str, inspect.Parameter],
    *,
    system_prompt: str,
    user_prompt: str,
) -> Dict[str, Any]:
    """providers API 시그니처에 맞게 kwargs 구성."""
    kwargs: Dict[str, Any] = {}
    if "messages" in params:
        kwargs["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    else:
        if "prompt" in params:
            kwargs["prompt"] = user_prompt
        elif "user_prompt" in params:
            kwargs["user_prompt"] = user_prompt
        if "system_prompt" in params:
            kwargs["system_prompt"] = system_prompt
        elif "system" in params:
            kwargs["system"] = system_prompt
    return kwargs

def stream_llm(
    *,
    system_prompt: str,
    user_input: str,
    split_fallback: bool = False,
) -> Iterator[str]:
    """
    통합 LLM 스트리밍:
    1) providers.stream_text(...) → 실시간 토막 yield
    2) providers.call_with_fallback(..., callbacks) → 콜백 기반 스트리밍
    3) 콜백 미지원 → 동기 호출
       - split_fallback=True면 문장 분할 후 여러 번 yield
       - 아니면 최종 텍스트 1회 yield
    """
    try:
        from src.llm import providers as prov
    except Exception as e:  # pragma: no cover
        yield f"(오류) provider 로딩 실패: {type(e).__name__}: {e}"
        return

    # 1) stream_text 우선 사용
    st_fn = getattr(prov, "stream_text", None)
    if callable(st_fn):
        params = inspect.signature(st_fn).parameters
        kwargs = _build_io_kwargs(
            params, system_prompt=system_prompt, user_prompt=user_input
        )
        for piece in st_fn(**kwargs):
            yield str(piece or "")
        return

    # 2) call_with_fallback + callbacks(on_delta/on_token/yield_text)
    call = getattr(prov, "call_with_fallback", None)
    if callable(call):
        params = inspect.signature(call).parameters
        kwargs = _build_io_kwargs(
            params, system_prompt=system_prompt, user_prompt=user_input
        )

        q: "Queue[Optional[str]]" = Queue()

        def _cb(t: Any) -> None:
            try:
                q.put(str(t or ""))
            except Exception:
                pass

        used_cb = False
        for name in ("on_delta", "on_token", "yield_text"):
            if name in params:
                kwargs[name] = _cb
                used_cb = True
        if "stream" in params:
            kwargs["stream"] = True

        if used_cb:
            def _bg() -> None:
                try:
                    call(**kwargs)
                except Exception as e:  # pragma: no cover
                    q.put(f"(오류) {type(e).__name__}: {e}")
                finally:
                    q.put(None)

            th = Thread(target=_bg, daemon=True)
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

        # 콜백 미지원 → 동기 호출
        try:
            res = call(**kwargs)
        except Exception as e:  # pragma: no cover
            yield f"(오류) {type(e).__name__}: {e}"
            return

        txt = res.get("text") if isinstance(res, dict) else str(res)
        if not split_fallback:
            yield str(txt or "")
            return

        for sent in _split_sentences(str(txt or "")):
            yield sent
        return

    # 3) 어떤 provider도 없으면 메시지
    yield "(오류) LLM 어댑터를 찾을 수 없어요."
