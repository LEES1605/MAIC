# src/agents/_common.py
# -----------------------------------------------------------------------------
# Agents common helpers (SSOT)
# - 단일화 목적: responder.py / evaluator.py 의 모든 스트리밍/분절 보일러플레이트 제거
# - 공개 API:
#     _split_sentences(text) -> List[str]
#     StreamState(buffer)
#     _on_piece(state, piece, emit) -> None
#     _runner(chunks, on_piece) -> None
#     stream_llm(system_prompt=..., user_prompt=..., split_fallback=False) -> Iterator[str]
# -----------------------------------------------------------------------------
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Iterator, List, Optional, Dict, Any, Mapping
import inspect
import queue
import re
import threading

__all__ = [
    "_split_sentences",
    "StreamState",
    "_on_piece",
    "_runner",
    "stream_llm",
]

# -------------------------- sentence segmentation ---------------------------
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
    이터러블/제너레이터에서 조각을 꺼내 콜백(on_piece)에 전달.
    - pieces가 문자열이 아닐 수도 있어 str() 강제
    - StopIteration 이외 예외는 상위에서 처리
    """
    for c in chunks:
        on_piece(str(c))

# --------------------------- providers adapter (SSOT) ------------------------
def _build_kwargs_for_provider(
    params: Mapping[str, inspect.Parameter],
    *,
    system_prompt: str,
    user_prompt: str,
) -> Dict[str, Any]:
    """
    provider 함수 시그니처(messages|prompt|user_prompt, system|system_prompt) 적응
    """
    kwargs: Dict[str, Any] = {}
    if "messages" in params:
        kwargs["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return kwargs

    # messages 미지원 → 각 단일 파라미터 조합 대응
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
    user_prompt: str,
    split_fallback: bool = False,
) -> Iterator[str]:
    """
    통합 스트리밍 제너레이터(SSOT).
    우선순위:
      1) providers.stream_text(messages|prompt…) 실스트리밍
      2) providers.call_with_fallback(stream+callbacks) 콜백 스트리밍
      3) call_with_fallback 반환 텍스트: split_fallback=True면 문장 분할, 아니면 한 번에 방출
    """
    try:
        from src.llm import providers as prov  # 런타임 의존
    except Exception as e:  # pragma: no cover
        yield f"(오류) provider 로딩 실패: {type(e).__name__}: {e}"
        return

    # 1) stream_text
    st_fn = getattr(prov, "stream_text", None)
    if callable(st_fn):
        params = inspect.signature(st_fn).parameters
        kwargs = _build_kwargs_for_provider(
            params, system_prompt=system_prompt, user_prompt=user_prompt
        )
        for piece in st_fn(**kwargs):
            yield str(piece or "")
        return

    # 2) call_with_fallback + callbacks
    call = getattr(prov, "call_with_fallback", None)
    if callable(call):
        params = inspect.signature(call).parameters
        kwargs = _build_kwargs_for_provider(
            params, system_prompt=system_prompt, user_prompt=user_prompt
        )

        q: "queue.Queue[Optional[str]]" = queue.Queue()

        def _enqueue(t: Any) -> None:
            try:
                q.put(str(t or ""))
            except Exception:
                pass

        used_cb = False
        for name in ("on_delta", "on_token", "yield_text"):
            if name in params:
                kwargs[name] = _enqueue
                used_cb = True
        if "stream" in params:
            kwargs["stream"] = True

        if used_cb:
            def _runner_thread() -> None:
                try:
                    call(**kwargs)
                except Exception as e:  # pragma: no cover
                    q.put(f"(오류) {type(e).__name__}: {e}")
                finally:
                    q.put(None)

            th = threading.Thread(target=_runner_thread, daemon=True)
            th.start()

            while True:
                try:
                    item = q.get(timeout=0.1)
                except queue.Empty:
                    if not th.is_alive() and q.empty():
                        break
                    continue
                if item is None:
                    break
                yield str(item or "")
            return

        # 콜백 미지원 → 단발 텍스트
        try:
            res = call(**kwargs)
        except Exception as e:  # pragma: no cover
            yield f"(오류) {type(e).__name__}: {e}"
            return
        txt = res.get("text") if isinstance(res, dict) else str(res)
        txt = str(txt or "")
        if split_fallback:
            for chunk in _split_sentences(txt):
                yield chunk
        else:
            yield txt
        return

    # 3) 어떠한 provider도 사용 불가
    yield "(오류) LLM 어댑터를 찾을 수 없어요."
