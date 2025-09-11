# src/agents/_common.py
# -----------------------------------------------------------------------------
# Agents common helpers (SSOT)
# - 목적: responder.py / evaluator.py 가 공통 스트리밍/분할 로직을 공유
# - 공개 API: _split_sentences, _on_piece, _runner, StreamState, stream_llm
# -----------------------------------------------------------------------------
from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Thread
from typing import Any, Callable, Iterable, Iterator, List, Mapping, Optional


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


def _on_piece(
    state: StreamState,
    piece: Optional[str],
    emit: Callable[[str], None],
) -> None:
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


# ---------------------------- provider adapter ------------------------------
def _build_io_kwargs(
    params: Mapping[str, inspect.Parameter],
    *,
    system_prompt: str,
    user_text: str,
) -> dict:
    """
    providers API 각 시그니처(messages/prompt/user_prompt/system/...)에 맞춰
    안전하게 kwargs를 생성한다.
    """
    kwargs: dict = {}
    if "messages" in params:
        kwargs["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]
        return kwargs

    # 메시지 미지원 → 단일 프롬프트 조합
    if "prompt" in params:
        # 일부 공급자는 system/user를 합친 prompt를 기대
        kwargs["prompt"] = f"{system_prompt}\n\n{user_text}"
    elif "user_prompt" in params:
        kwargs["user_prompt"] = user_text

    # 시스템 프롬프트 채널
    if "system_prompt" in params:
        kwargs["system_prompt"] = system_prompt
    elif "system" in params:
        kwargs["system"] = system_prompt

    return kwargs


# ------------------------------- public API ---------------------------------
def stream_llm(
    *,
    system_prompt: str,
    user_input: str,
    split_fallback: bool = False,
) -> Iterator[str]:
    """
    LLM 스트리밍 통합 제너레이터.
    우선순위
      1) providers.stream_text(...)     → 직접 스트리밍
      2) providers.call_with_fallback(...) + 콜백 → 의사 스트리밍
      3) (2) 콜백 미지원 → 단발 호출 결과를 스트림처럼 분할/방출
    """
    # 1) provider 모듈 안전 로드
    try:
        from src.llm import providers as prov  # type: ignore
    except Exception as e:  # pragma: no cover
        yield f"(오류) provider 로딩 실패: {type(e).__name__}: {e}"
        return

    # 2) stream_text 우선
    stream_fn = getattr(prov, "stream_text", None)
    if callable(stream_fn):
        params = inspect.signature(stream_fn).parameters
        kwargs = _build_io_kwargs(
            params,
            system_prompt=system_prompt,
            user_text=user_input,
        )
        try:
            for piece in stream_fn(**kwargs):
                yield str(piece or "")
            return
        except Exception as e:  # pragma: no cover
            yield f"(오류) {type(e).__name__}: {e}"
            return

    # 3) call_with_fallback 시도(콜백 기반 스트리밍)
    call = getattr(prov, "call_with_fallback", None)
    if callable(call):
        params = inspect.signature(call).parameters
        kwargs = _build_io_kwargs(
            params,
            system_prompt=system_prompt,
            user_text=user_input,
        )

        q: "Queue[Optional[str]]" = Queue()

        def _enqueue(t: Any) -> None:
            try:
                q.put(str(t or ""))
            except Exception:
                # 큐가 닫혔거나 기타 오류는 조용히 무시
                pass

        used_cb = False
        for name in ("on_delta", "on_token", "yield_text"):
            if name in params:
                kwargs[name] = _enqueue
                used_cb = True
        if "stream" in params:
            kwargs["stream"] = True

        if used_cb:
            def _target() -> None:
                try:
                    call(**kwargs)
                except Exception as e:  # pragma: no cover
                    q.put(f"(오류) {type(e).__name__}: {e}")
                finally:
                    q.put(None)

            th = Thread(target=_target, daemon=True)
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

        text = res.get("text") if isinstance(res, dict) else str(res)
        if not text:
            return

        if split_fallback:
            for seg in _split_sentences(text):
                yield seg
        else:
            yield text
        return

    # 4) 어떤 provider도 없으면 메시지
    yield "(오류) LLM 어댑터를 찾을 수 없어요."
