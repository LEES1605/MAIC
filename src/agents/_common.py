# src/agents/_common.py
# -----------------------------------------------------------------------------
# Agents common helpers (unified)
# - 표준 스트리밍 API(stream_llm)와 공용 유틸만 제공
# - responder/evaluator는 이 모듈만 의존
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
    """스트리밍 누적 버퍼 상태(단순 문자열 누적)."""
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

# ---------------------------- provider plumbing -----------------------------
def _build_io_kwargs(
    params: Mapping[str, inspect.Parameter],
    *,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    """providers API 시그니처에 맞게 안전하게 kwargs 구성."""
    kw: dict[str, Any] = {}
    if "messages" in params:
        kw["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    else:
        # 단일 프롬프트 계열
        if "prompt" in params:
            kw["prompt"] = user_prompt
        elif "user_prompt" in params:
            kw["user_prompt"] = user_prompt
        # 시스템 프롬프트
        if "system_prompt" in params:
            kw["system_prompt"] = system_prompt
        elif "system" in params:
            kw["system"] = system_prompt
    return kw

# ------------------------------ public facade -------------------------------
def stream_llm(
    *,
    system_prompt: str,
    user_prompt: str,
    split_fallback: bool = True,
) -> Iterator[str]:
    """
    표준 스트리밍 파사드.
    1) providers.stream_text(...)  → 실제 스트리밍
    2) providers.call_with_fallback(..., stream=True, callbacks...) → 콜백 스트리밍
    3) 콜백 미지원 → 최종 텍스트 1개(옵션에 따라 문장 분할)
    """
    try:
        from src.llm import providers as prov  # type: ignore
    except Exception as e:  # pragma: no cover
        yield f"(오류) provider 로딩 실패: {type(e).__name__}: {e}"
        return

    # 1) stream_text 우선
    st_fn = getattr(prov, "stream_text", None)
    if callable(st_fn):
        params = inspect.signature(st_fn).parameters
        kwargs = _build_io_kwargs(params, system_prompt=system_prompt, user_prompt=user_prompt)
        for piece in st_fn(**kwargs):
            yield str(piece or "")
        return

    # 2) call_with_fallback + callbacks
    call = getattr(prov, "call_with_fallback", None)
    if callable(call):
        params = inspect.signature(call).parameters
        kwargs = _build_io_kwargs(params, system_prompt=system_prompt, user_prompt=user_prompt)

        q: "Queue[Optional[str]]" = Queue()

        # 지역 콜백(이름을 _on_piece로 하지 않음: 에이전트 파일 테스트와 혼동 방지)
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
            def _worker() -> None:
                try:
                    call(**kwargs)
                except Exception as e:  # pragma: no cover
                    q.put(f"(오류) {type(e).__name__}: {e}")
                finally:
                    q.put(None)

            th = Thread(target=_worker, daemon=True)
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
            txt = res.get("text") if isinstance(res, dict) else str(res)
        except Exception as e:  # pragma: no cover
            yield f"(오류) {type(e).__name__}: {e}"
            return

        if not txt:
            return
        if split_fallback:
            for seg in _split_sentences(txt):
                yield seg
        else:
            yield txt
        return

    # 3) 어떤 provider도 없으면 메시지
    yield "(오류) LLM 어댑터를 찾을 수 없어요."
