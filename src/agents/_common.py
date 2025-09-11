# src/agents/_common.py
# -----------------------------------------------------------------------------
# Wave‑2.x: Agents common helpers (unify streaming + remove duplication)
# - 목적: responder.py / evaluator.py가 공통으로 사용하는 스트리밍 헬퍼의 단일 소스화
# - API 보장:
#   * _split_sentences(text) -> List[str]
#   * class StreamState(buffer: str)
#   * _on_piece(state, piece, emit)  # state.buffer 누적 + emit 호출
#   * _runner(chunks, on_piece)      # iterable에서 on_piece로 전달
#   * stream_llm(system_prompt=..., user_input=...|user_prompt=..., split_fallback=True)
#       - 에이전트들이 user_input, split_fallback을 인자로 넘겨도 mypy 통과
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
# 문장 경계: 영/한 문장부호 + 줄바꿈/공백 기준
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

# --------------------------- provider integration ---------------------------
def _build_io_kwargs(
    params: Mapping[str, inspect.Parameter],
    *,
    system_prompt: str,
    user_text: str,
) -> Dict[str, Any]:
    """
    providers API 시그니처에 맞춰 kwargs 구성.
    - messages 또는 prompt/user_prompt + system/system_prompt 모두 대응
    """
    kwargs: Dict[str, Any] = {}
    # 우선순위: (messages) -> (prompt/user_prompt + system)
    if "messages" in params:
        up = (user_prompt if user_prompt is not None else question) or ""
        kwargs["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]
    else:
        if "prompt" in params:
            # 일부 구현은 prompt 하나만 받기도 함
            kwargs["prompt"] = user_text
        elif "user_prompt" in params:
            kwargs["user_prompt"] = user_text
        if "system_prompt" in params:
            kwargs["system_prompt"] = system_prompt or ""
        elif "system" in params:
            kwargs["system"] = system_prompt or ""
    return kwargs


def stream_llm(
    *,
    system_prompt: str,
    user_prompt: Optional[str] = None,
    user_input: Optional[str] = None,
    split_fallback: bool = True,
) -> Iterator[str]:
    """
    LLM 스트림 통합 제너레이터.
    - 우선순위: providers.stream_text → providers.call_with_fallback(stream+callbacks)
    - 콜백 미지원이면: call_with_fallback() 결과를
        * split_fallback=True  → 문장 단위로 나눠 여러 번 yield
        * split_fallback=False → 한 번에 yield
    - 파라미터 호환: responder/evaluator가 넘기는 user_input/split_fallback을 그대로 수용
    """
    user_text = (user_prompt if user_prompt is not None else user_input) or ""

    try:
        from src.llm import providers as prov  # 런타임 의존 (테스트 환경 포함)
    except Exception as e:  # pragma: no cover
        yield f"(오류) provider 로딩 실패: {type(e).__name__}: {e}"
        return

    # 1) 진짜 스트리밍 API
    stream_fn = getattr(prov, "stream_text", None)
    if callable(stream_fn):
        params = inspect.signature(stream_fn).parameters
        kwargs = _build_io_kwargs(params, system_prompt=system_prompt, user_text=user_text)
        for piece in stream_fn(**kwargs):
            yield str(piece or "")
        return

    # 2) call_with_fallback + 콜백/stream 지원 시 의사-스트리밍
    call = getattr(prov, "call_with_fallback", None)
    if callable(call):
        params = inspect.signature(call).parameters
        kwargs = _build_io_kwargs(params, system_prompt=system_prompt, user_text=user_text)

        # 콜백 지원 여부 확인
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
            # 별도 스레드에서 provider 호출 → 큐를 통해 조각 수신
            def _runner_thread() -> None:
                try:
                    call(**kwargs)
                except Exception as e:  # pragma: no cover
                    q.put(f"(오류) {type(e).__name__}: {e}")
                finally:
                    q.put(None)

            th = Thread(target=_runner_thread, daemon=True)
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

        # 콜백 미지원 → 결과텍스트를 분리 또는 통으로 반환

        try:
            res = call(**kwargs)
            txt = res.get("text") if isinstance(res, dict) else str(res)
        except Exception as e:  # pragma: no cover
            yield f"(오류) {type(e).__name__}: {e}"
            return
        txt = str(txt or "")
        if not split_fallback:
            # 통으로 한 번만
            if txt:
                yield txt
            return

        # 문장 단위로 분할하여 여러 번
        for chunk in _split_sentences(txt):
            yield chunk
        return

    # 3) 어떤 provider도 없으면 메시지
    yield "(오류) LLM 어댑터를 찾을 수 없어요."
