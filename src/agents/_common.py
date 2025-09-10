# -----------------------------------------------------------------------------
# src/agents/_common.py
# Agents common helpers (public API: _split_sentences, _on_piece, _runner,
# StreamState, stream_llm)
# -----------------------------------------------------------------------------
from __future__ import annotations

import re
import inspect
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
)
from queue import Queue, Empty
from threading import Thread

__all__ = [
    "_split_sentences",
    "_on_piece",
    "_runner",
    "StreamState",
    "stream_llm",
]

# -------------------------- sentence segmentation ---------------------------
# 규칙:
#  - 일반 문장부호(영/한) 뒤 공백
#  - 개행 경계
#  - 세미콜론/콜론 뒤 공백
_SENT_SEP = re.compile(
    r"(?<=[\.\?!。？！…])\s+|"      # sentence enders + space
    r"(?<=\n)\s*|"                  # newline boundary
    r"(?<=[;:])\s+"                 # semicolon/colon + space
)

def _split_sentences(text: str) -> List[str]:
    """
    간단·견고한 문장 분리기.
    - 한국어/영어 혼합 입력에서도 작동
    - 개행은 보존(분리 기준으로만 사용), 그 외 연속 공백은 정규화
    """
    if not isinstance(text, str):
        return []
    raw = text.strip()
    if not raw:
        return []
    # 개행은 그대로 두고, 그 외 공백만 단일 공백으로 정규화
    normalized = re.sub(r"[ \t\f\v]+", " ", raw)
    parts = [p.strip() for p in _SENT_SEP.split(normalized)]
    return [p for p in parts if p]

# ---------------------------- streaming helpers -----------------------------
@dataclass
class StreamState:
    """스트리밍 누적 버퍼 상태를 보관합니다."""
    buffer: str = ""

def _on_piece(
    state: StreamState,
    piece: Optional[str],
    emit: Callable[[str], None],
) -> None:
    """
    조각(piece)을 누적하고 emitter로 전달합니다.
    - piece가 None/공백이면 무시
    순서: buffer += piece → emit(piece)
    """
    if not piece:
        return
    s = str(piece)
    state.buffer += s
    emit(s)

def _runner(chunks: Iterable[str], on_piece: Callable[[str], None]) -> None:
    """
    제너레이터/이터러블에서 조각을 꺼내 콜백(on_piece)에 전달합니다.
    - 조각이 비문자열일 수 있어 str() 강제
    - StopIteration 이외 예외는 상위에서 처리
    """
    for c in chunks:
        on_piece(str(c))

# ----------------------------- LLM stream facade ----------------------------
def _build_io_kwargs(
    params: Mapping[str, inspect.Parameter],
    *,
    system_prompt: str,
    user_input: str,
) -> Dict[str, Any]:
    """
    providers API 시그니처(messages/prompt/user_prompt/system|system_prompt)를
    런타임에 탐지하여 kwargs를 구성합니다.
    """
    kwargs: Dict[str, Any] = {}
    if "messages" in params:
        kwargs["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]
    else:
        # system/user를 분리로 받거나 단일 prompt로 받는 경우 모두 대응
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
    2) call_with_fallback(stream+callbacks) → 콜백/스레드로 청크 스트림
    3) 미지원 시 call_with_fallback(non-stream) 결과를 문장 분할/직출력

    split_fallback=True  → 폴백 시 문장 단위로 여러 번 방출
                    False → 폴백 시 한 번만 방출
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

        # 콜백 기반 실스트리밍을 큐로 브리지
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
            # 공급자 호출을 데몬 스레드에서 실행, None 센티넬로 종료 신호
            def _run() -> None:
                try:
                    call(**kwargs)
                except Exception as e:  # pragma: no cover
                    q.put(f"(오류) {type(e).__name__}: {e}")
                finally:
                    q.put(None)

            th = Thread(target=_run, daemon=True)
            th.start()

            # 큐에서 토막을 받아 순차 방출
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
