# -----------------------------------------------------------------------------
# Wave‑2.1: Agents common helpers (finalized)
# 목적:
# - responder.py / evaluator.py가 공통으로 쓰는 헬퍼의 단일화
# - 테스트 가정(_split_sentences/_on_piece/_runner/StreamState) 충족
# - ruff F821/F841 및 mypy 파생 이슈 방지
# -----------------------------------------------------------------------------
from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from queue import Queue, Empty
from threading import Thread
from typing import Any, Callable, Iterable, Iterator, List, Mapping, Optional

__all__ = [
    "_split_sentences",
    "_on_piece",
    "_runner",
    "StreamState",
    "stream_llm",
]

# -------------------------- [01] sentence segmentation -----------------------
_SENT_SEP = re.compile(
    r"(?<=[\.\?!。？！…])\s+|"  # 일반 문장부호 + 공백
    r"(?<=\n)\s*|"             # 줄바꿈
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
    # 연속 공백 정규화
    raw = re.sub(r"\s+", " ", text.strip())
    # 구분자 기준 스플릿
    parts = [p.strip() for p in _SENT_SEP.split(raw)]
    # 빈 항목 제거 후 최소 보호
    return [p for p in parts if p]


# ---------------------------- [02] streaming helpers -------------------------
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


# ----------------------------- [03] stream_llm --------------------------------
def _build_io_kwargs(
    params: Mapping[str, inspect.Parameter],
    *,
    system_prompt: str,
    user_text: str,
) -> dict:
    """providers API 각 시그니처(messages/prompt/user_prompt/system/...)에 맞춰 안전하게 kwargs 생성."""
    kwargs: dict = {}
    if "messages" in params:
        kwargs["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]
    else:
        # user 영역
        if "prompt" in params:
            kwargs["prompt"] = user_text
        elif "user_prompt" in params:
            kwargs["user_prompt"] = user_text
        # system 영역
        if "system_prompt" in params:
            kwargs["system_prompt"] = system_prompt
        elif "system" in params:
            kwargs["system"] = system_prompt
    return kwargs


def stream_llm(
    *,
    system_prompt: str,
    # 구버전·신버전 호출 모두 수용(둘 중 하나만 채워도 됨)
    user_prompt: Optional[str] = None,
    question: Optional[str] = None,
    user_input: Optional[str] = None,  # 과거 호출 호환용
    # provider가 실스트리밍을 못하면 문장 분할 의사-스트리밍 여부
    split_fallback: bool = True,
) -> Iterator[str]:
    """
    LLM 스트림 래퍼.
    우선순위:
      1) providers.stream_text (실제 스트리밍)
      2) providers.call_with_fallback + callbacks(on_delta/on_token/yield_text)
      3) 콜백 미지원 시 단발 호출 → (split_fallback) 문장 분할/그대로
    """
    # user 텍스트 통합(호환 파라미터)
    user_text = (user_prompt or question or user_input or "").strip()

    try:
        from src.llm import providers as prov  # 외부에 존재(테스트에서 모킹·대체 가능)
    except Exception as e:  # pragma: no cover
        yield f"(오류) provider 로딩 실패: {type(e).__name__}: {e}"
        return

    # 1) stream_text(messages|prompt) — 있으면 그대로 사용
    stream_fn = getattr(prov, "stream_text", None)
    if callable(stream_fn):
        params = inspect.signature(stream_fn).parameters
        kwargs = _build_io_kwargs(params, system_prompt=system_prompt, user_text=user_text)
        for piece in stream_fn(**kwargs):
            yield str(piece or "")
        return

    # 2) call_with_fallback + callbacks
    call = getattr(prov, "call_with_fallback", None)
    if callable(call):
        params = inspect.signature(call).parameters
        kwargs = _build_io_kwargs(params, system_prompt=system_prompt, user_text=user_text)

        q: "Queue[Optional[str]]" = Queue()

        def _enqueue(t: Any) -> None:
            try:
                q.put("" if t is None else str(t))
            except Exception:
                # 큐 실패는 조용히 무시(스트림 중단 회피)
                pass

        used_cb = False
        for name in ("on_delta", "on_token", "yield_text"):
            if name in params:
                kwargs[name] = _enqueue
                used_cb = True
        if "stream" in params:
            kwargs["stream"] = True

        if used_cb:
            # 콜백 기반 실스트리밍
            def _call_runner() -> None:
                try:
                    call(**kwargs)
                except Exception as e:  # pragma: no cover
                    q.put(f"(오류) {type(e).__name__}: {e}")
                finally:
                    q.put(None)

            th = Thread(target=_call_runner, daemon=True)
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
        txt: Optional[str] = None
        try:
            res = call(**kwargs)  # noqa: F841 (txt로 가공)
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
