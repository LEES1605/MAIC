# Wave‑2.2: Agents common helpers & streaming shim (contract-stable)
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
    r"(?<=[\.\?!。？！…])\s+|"  # end marks then space
    r"(?<=\n)\s*|"              # newline
    r"(?<=[;:])\s+"             # semicolon/colon
)


def _split_sentences(text: str) -> List[str]:
    """Lightweight, language-agnostic sentence splitter."""
    if not isinstance(text, str) or not text.strip():
        return []
    raw = re.sub(r"\s+", " ", text.strip())
    parts = [p.strip() for p in _SENT_SEP.split(raw)]
    return [p for p in parts if p]


# ---------------------------- streaming helpers -----------------------------
@dataclass
class StreamState:
    """Streaming buffer state."""
    buffer: str = ""


def _on_piece(state: StreamState, piece: Optional[str], emit: Callable[[str], None]) -> None:
    """Accumulate piece to state.buffer and emit."""
    if not piece:
        return
    s = str(piece)
    state.buffer += s
    emit(s)


def _runner(chunks: Iterable[str], on_piece: Callable[[str], None]) -> None:
    """Feed pieces from iterable/generator to on_piece."""
    for c in chunks:
        on_piece(str(c))


# ------------------------ providers I/O normalization ------------------------
def _build_io_kwargs(
    params: Mapping[str, inspect.Parameter],
    *,
    system_prompt: str,
    user_text: str,
) -> Dict[str, Any]:
    """Create kwargs that match various provider signatures."""
    kwargs: Dict[str, Any] = {}
    if "messages" in params:
        kwargs["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]
        return kwargs

    if "prompt" in params:
        kwargs["prompt"] = user_text
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
    system_prompt: Optional[str] = None,
    user_prompt: Optional[str] = None,
    question: Optional[str] = None,
    split_fallback: bool = True,
) -> Iterator[str]:
    """
    Unified streaming entry:
    1) providers.stream_text → yield directly
    2) providers.call_with_fallback with callbacks
    3) Non-stream call → split or return whole text
    """
    text = user_prompt if user_prompt is not None else (question or "")
    system_prompt = system_prompt or ""

    try:
        from src.llm import providers as prov  # runtime import
    except Exception as e:  # pragma: no cover
        yield f"(오류) provider 로딩 실패: {type(e).__name__}: {e}"
        return

    # 1) Prefer real streaming if available
    st_fn = getattr(prov, "stream_text", None)
    if callable(st_fn):
        params = inspect.signature(st_fn).parameters
        kwargs = _build_io_kwargs(params, system_prompt=system_prompt, user_text=text)
        for piece in st_fn(**kwargs):
            yield str(piece or "")
        return

    # 2) Fallback with callbacks
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

        # Non-stream call → split or whole
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

    # 3) No provider available
    yield "(오류) LLM 어댑터를 찾을 수 없어요."
