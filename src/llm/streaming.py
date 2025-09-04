# ============================== [01] 스트리밍 버퍼 유틸 — START ===============================
"""
Streaming utilities for token-to-text buffering with multiple strategies.

Strategies
---------
- "none":     emit every token immediately.
- "punct":    buffer until punctuation/newline is seen, then flush.
- "sentence": buffer until a sentence boundary is detected, then flush.

Safety
------
- Time-based and length-based forced flush to avoid long delays.
- Optional cancellation check to stop gracefully.
- Robust to provider quirks (tokens with/without spaces).

This module is intentionally stdlib-only and mypy/ruff friendly.
"""
from __future__ import annotations

from typing import Callable, Iterable, Iterator, Optional, Literal, Protocol
import re
import time

__all__ = ["buffer_tokens", "stream_text"]

# Recognized punctuation and sentence-ending marks (EN + KO + common)
_PUNCTS = set(list(".,?!:;)]}") + ["…", "。", "、", "！", "？", "”", "’"])

# Sentence-splitting regex: captures a *complete* sentence chunk.
#   - Ends with one of [.?!…。！？]
#   - Allows closing quotes/brackets after end mark
#   - Followed by whitespace or end-of-string
_SENT_SPLIT_RE = re.compile(
    r"(.+?(?:[\.!\?]|…|。|！|？)(?:[\"'\)\]]+)?)(?:\s+|$)",
    flags=re.S,
)


class _CancelCheck(Protocol):
    def __call__(self) -> bool: ...


def _has_punct(s: str) -> bool:
    """Return True if `s` contains punctuation or a newline boundary worth flushing."""
    if not s:
        return False
    if "\n" in s or "\r" in s:
        return True
    for ch in s:
        if ch in _PUNCTS:
            return True
    return False


def _split_complete_sentences(buf: str) -> tuple[str, str]:
    """
    Split `buf` into (complete, remainder) where `complete` includes
    all full sentences from the start of buffer.
    """
    last_end = -1
    m_last = None
    for m in _SENT_SPLIT_RE.finditer(buf):
        m_last = m
        last_end = m.end()
    if m_last is None:
        return "", buf
    # Include up to the last complete sentence boundary
    return buf[:last_end], buf[last_end:]


def buffer_tokens(
    tokens: Iterable[str],
    *,
    strategy: Literal["none", "punct", "sentence"] = "none",
    max_latency: float = 0.6,
    max_chars: int = 600,
    cancel: Optional[_CancelCheck] = None,
) -> Iterator[str]:
    """
    Convert a token stream into text chunks according to a buffering strategy.

    Parameters
    ----------
    tokens : Iterable[str]
        Incoming text tokens (already decoded from provider).
    strategy : {"none", "punct", "sentence"}
        Buffering strategy (see module docstring).
    max_latency : float
        Seconds before we force-flush any pending buffer (for non-"none").
    max_chars : int
        Max buffer length before forced flush.
    cancel : Callable[[], bool], optional
        Return True to cancel streaming; remaining buffer will be flushed.

    Yields
    ------
    str
        Buffered text chunk to render.

    Notes
    -----
    - "none": ignores latency/length and yields each token immediately.
    - "punct": flush on punctuation/newline OR forced by latency/length.
    - "sentence": flush on sentence boundary OR forced by latency/length.
    """
    if strategy not in ("none", "punct", "sentence"):
        strategy = "none"

    if strategy == "none":
        for tk in tokens:
            if cancel and cancel():
                return
            yield tk
        return

    buf: str = ""
    last_flush = time.monotonic()

    def _maybe_forced_flush(now: float) -> Optional[str]:
        nonlocal buf, last_flush
        if not buf:
            return None
        if (now - last_flush) >= max_latency or len(buf) >= max_chars:
            out = buf
            buf = ""
            last_flush = now
            return out
        return None

    try:
        for tk in tokens:
            if cancel and cancel():
                break

            s = str(tk or "")
            if not s:
                # Even if token empty, still honor latency flush to avoid starvation
                now = time.monotonic()
                forced = _maybe_forced_flush(now)
                if forced is not None:
                    yield forced
                continue

            if strategy == "punct":
                buf += s
                now = time.monotonic()
                if _has_punct(s):
                    out, buf = buf, ""
                    last_flush = now
                    yield out
                    continue
                forced = _maybe_forced_flush(now)
                if forced is not None:
                    yield forced
            else:
                # "sentence"
                buf += s
                now = time.monotonic()
                complete, remainder = _split_complete_sentences(buf)
                if complete:
                    last_flush = now
                    yield complete
                    buf = remainder
                    # After emitting a full sentence, also check latency on remainder
                    forced = _maybe_forced_flush(now)
                    if forced is not None:
                        yield forced
                else:
                    forced = _maybe_forced_flush(now)
                    if forced is not None:
                        yield forced

    except Exception as e:
        # Fail-safe: never swallow buffered content
        if buf:
            yield buf
        raise e

    # End-of-stream: flush whatever remains
    if buf:
        yield buf


def stream_text(
    tokens: Iterable[str],
    on_emit: Callable[[str], None],
    *,
    strategy: Literal["none", "punct", "sentence"] = "none",
    max_latency: float = 0.6,
    max_chars: int = 600,
    cancel: Optional[_CancelCheck] = None,
) -> None:
    """
    Consume tokens and call `on_emit(chunk)` for each buffered chunk.

    Example
    -------
    >>> def printer(x: str): print(x, end="")
    >>> stream_text(["Hel", "lo", ", ", "wo", "rld", "!"], printer, strategy="punct")
    Hello, world!
    """
    for chunk in buffer_tokens(
        tokens,
        strategy=strategy,
        max_latency=max_latency,
        max_chars=max_chars,
        cancel=cancel,
    ):
        if cancel and cancel():
            if chunk:
                on_emit(chunk)
            return
        if chunk:
            on_emit(chunk)
# =============================== [01] 스트리밍 버퍼 유틸 — END ================================
