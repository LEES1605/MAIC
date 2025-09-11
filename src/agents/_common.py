# Wave‑2.1: Agents common helpers & streaming shim (contract-stable)
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
    r"(?<=[\.\?!。？！…])\s+|"      # 종결부호 + 공백
    r"(?<=\n)\s*|"                  # 줄바꿈
    r"(?<=[;:])\s+"                 # 세미콜론/콜론
)

def _split_sentences(text: str) -> List[str]:
    """
    간단하고 견고한 문장 분리기.
    한국어/영어 혼합 입력에서도 동작. 빈 토큰 제거.
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
    piece가 None/공백이면 무시. emit 예외는 상위로 전파.
    """
    if not piece:
        return
    s = str(piece)
    state.buffer += s
    emit(s)

def _runner(chunks: Iterable[str], on_piece: Callable[[str], None]) -> None:
    """
    제너레이터/이터러블에서 조각을 꺼내 콜백에 전달.
    StopIteration 외 예외는 상위에서 처리.
    """
    for c in chunks:
        on_piece(str(c))

# ------------------------ providers I/O normalization ------------------------
def _build_io_kwargs(
    params: Mapping[str, inspect.Parameter],
    *,
    system_prompt: str,
    user_text: str,
) -> Dict[str, Any]:
    """
    providers API 시그니처(messages/prompt/user_prompt/system/...)에
    맞춰 안전하게 kwargs를 생성한다.
    """
    kwargs: Dict[str, Any] = {}
    if "messages" in params:
        kwargs["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]
    else:
        if "prompt" in params:
            kwargs["prompt"] = system_prompt + "\n\n" + user_text
        elif "user_prompt" in params:
            kwargs["user_prompt"] = user_text
        if "system_prompt" in params:
            kwargs["system_prompt"] = system_prompt
        elif "system" in params:
            kwargs["system"] = system_prompt
    return kwargs

# ------------------------------ public streaming ----------------------------
def stream_llm(
    *,
    system_prompt: str,
    user_prompt: Optional[str] = None,
    user_input: Optional[str] = None,
    split_fallback: bool = False,
) -> Iterator[str]:
    """
    LLM 스트림 통합 진입점.
    우선 providers.stream_text → 콜백 기반 call_with_fallback → 단발 호출.
    단발 호출 시 split_fallback=True면 문장 단위로 분할하여 의사-스트리밍.
    """
    text = user_prompt if user_prompt is not None else (user_input or "")
    try:
        from src.llm import providers as prov
    except Exception as e:  # pragma: no cover
        yield f"(오류) provider 로딩 실패: {type(e).__name__}: {e}"
        return

    # 1) stream_text(messages|prompt)를 지원하면 그대로 사용
    st_fn = getattr(prov, "stream_text", None)
    if callable(st_fn):
        params = inspect.signature(st_fn).parameters
        kwargs = _build_io_kwargs(params, system_prompt=system_prompt, user_text=text)
        for piece in st_fn(**kwargs):
            yield str(piece or "")
        return

    # 2) call_with_fallback + callbacks(on_delta / on_token / yield_text)
    call = getattr(prov, "call_with_fallback", None)
    if callable(call):
        params = inspect.signature(call).parameters
        kwargs = _build_io_kwargs(params, system_prompt=system_prompt, user_text=text)

        q: "Queue[Optional[str]]" = Queue()

        def _enqueue(tok: Any) -> None:
            try:
                q.put(str(tok or ""))
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

        # 콜백 미지원 → 단발 호출
        try:
            result = call(**kwargs)
        except Exception as e:  # pragma: no cover
            yield f"(오류) {type(e).__name__}: {e}"
            return

        txt = result.get("text") if isinstance(result, dict) else str(result)
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
