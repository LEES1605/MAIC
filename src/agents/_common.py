# src/agents/_common.py
# -----------------------------------------------------------------------------
# Agents common helpers: sentence split + streaming building blocks
# - 테스트 호환 보장: _split_sentences, _on_piece, _runner, StreamState
# - 향후 통합 대비: stream_llm (provider 브릿지)
# -----------------------------------------------------------------------------
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Iterator, List, Mapping, Optional
import inspect
import re
from queue import Queue, Empty
from threading import Thread


__all__ = [
    "_split_sentences",  # (str) -> List[str]
    "_on_piece",         # (state, piece, emit) -> None
    "_runner",           # (chunks, on_piece) -> None
    "StreamState",       # dataclass with .buffer
    "stream_llm",        # optional provider bridge
]

# -------------------------- sentence segmentation ---------------------------
# EN/KO 문장부호 + 줄바꿈 기준의 간단하고 견고한 분리기
_SENT_SEP = re.compile(
    r"(?<=[\.\?!。？！…])\s+|"      # 일반 문장부호 + 공백
    r"(?<=\n)\s*|"                  # 줄바꿈
    r"(?<=[;:])\s+"                 # 세미콜론/콜론
)


def _split_sentences(text: str) -> List[str]:
    """
    간단·견고한 문장 분리기.
    - 한국어/영어 혼합 입력에서도 작동
    - 공백 정리 및 빈 토큰 제거
    """
    if not isinstance(text, str) or not text.strip():
        return []
    raw = re.sub(r"\s+", " ", text.strip())         # 연속 공백 정규화
    parts = [p.strip() for p in _SENT_SEP.split(raw)]
    return [p for p in parts if p]                  # 빈 항목 제거


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


# -------------------------- provider streaming bridge -----------------------
def _build_io_kwargs(
    params: Mapping[str, inspect.Parameter],
    *,
    system_prompt: Optional[str] = None,
    user_prompt: Optional[str] = None,
    question: Optional[str] = None,
) -> Dict[str, Any]:
    """
    providers.* 함수 시그니처에 맞춰 안전하게 kwargs 구성.
    - messages / prompt / (system|system_prompt) / user_prompt 등을 폭넓게 지원
    """
    kwargs: Dict[str, Any] = {}
    # 우선순위: (messages) -> (prompt/user_prompt + system)
    if "messages" in params:
        up = (user_prompt if user_prompt is not None else question) or ""
        kwargs["messages"] = [
            {"role": "system", "content": system_prompt or ""},
            {"role": "user", "content": up},
        ]
    else:
        # user 텍스트
        up = (user_prompt if user_prompt is not None else question) or ""
        if "prompt" in params:
            kwargs["prompt"] = up
        elif "user_prompt" in params:
            kwargs["user_prompt"] = up
        # system 텍스트
        if "system_prompt" in params:
            kwargs["system_prompt"] = system_prompt or ""
        elif "system" in params:
            kwargs["system"] = system_prompt or ""
    return kwargs


def stream_llm(
    *,
    system_prompt: Optional[str] = None,
    user_prompt: Optional[str] = None,
    question: Optional[str] = None,
) -> Iterator[str]:
    """
    통합 스트리밍 브릿지:
    - providers.stream_text(...)가 있으면 직접 스트림
    - 아니면 providers.call_with_fallback(stream+callbacks) 시도
    - 전부 불가하면 providers.call_with_fallback(...) 반환 텍스트를 문장 단위로 분할
    """
    try:
        from src.llm import providers as prov  # 런타임 의존(테스트 환경에서도 안전)
    except Exception as e:  # pragma: no cover
        yield f"(오류) provider 로딩 실패: {type(e).__name__}: {e}"
        return

    # 1) stream_text 우선
    st_fn = getattr(prov, "stream_text", None)
    if callable(st_fn):
        params = inspect.signature(st_fn).parameters
        kwargs = _build_io_kwargs(
            params,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            question=question,
        )
        for piece in st_fn(**kwargs):
            yield str(piece or "")
        return

    # 2) call_with_fallback + 콜백(실스트리밍)
    call = getattr(prov, "call_with_fallback", None)
    if callable(call):
        params = inspect.signature(call).parameters
        kwargs = _build_io_kwargs(
            params,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            question=question,
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

        # 콜백 미지원 → 한 번에 받기
        try:
            res = call(**kwargs)
            txt = res.get("text") if isinstance(res, dict) else str(res)
        except Exception as e:  # pragma: no cover
            yield f"(오류) {type(e).__name__}: {e}"
            return

        for chunk in _split_sentences(txt or ""):
            yield chunk
        return

    yield "(오류) LLM 어댑터를 찾을 수 없어요."
