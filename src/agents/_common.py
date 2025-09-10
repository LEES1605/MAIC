# =============================== [01] Agents Common — START ===============================
from __future__ import annotations

from typing import Iterator, Mapping, Dict, Any, Optional, Callable
import inspect
import re
from queue import Queue, Empty
from threading import Thread

__all__ = ["_split_sentences", "stream_llm", "_on_piece", "_runner", "StreamState"]


def _split_sentences(text: str) -> list[str]:
    """
    간단한 문장 분리기(영/한 마침부호 기준).
    - 목적: 토막 응답을 '문장' 단위로 자연스럽게 쪼개기
    """
    if not text:
        return []
    parts = re.split(r"(?<=[\.!\?。！？])\s+", text.strip())
    return [p for p in parts if p]


def _build_io_kwargs(
    params: Mapping[str, inspect.Parameter],
    *,
    system_prompt: str,
    user_input: str,
) -> Dict[str, Any]:
    """
    providers API 시그니처(messages/prompt/user_prompt/system|system_prompt)를
    런타임에 탐지하여 kwargs를 구성한다.
    """
    kwargs: Dict[str, Any] = {}
    if "messages" in params:
        kwargs["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]
    else:
        if "prompt" in params:
            # 일부 제공자는 단일 prompt만 받으므로 system/user 결합
            kwargs["prompt"] = user_input
        elif "user_prompt" in params:
            kwargs["user_prompt"] = user_input
        if "system_prompt" in params:
            kwargs["system_prompt"] = system_prompt
        elif "system" in params:
            kwargs["system"] = system_prompt
    return kwargs


class StreamState:
    """
    공급자 콜백 기반 스트리밍을 위한 상태/유틸 집합.
    - make_callback(): 공급자에 전달할 콜백 생성
    - start(call, **kwargs): 공급자 호출을 데몬 스레드에서 수행
    - iter(timeout): 큐에서 토막을 꺼내어 yield
    """
    def __init__(self) -> None:
        self.q: "Queue[Optional[str]]" = Queue()
        self._th: Optional[Thread] = None

    def make_callback(self) -> Callable[[Any], None]:
        def cb(t: Any) -> None:
            _on_piece(self, str(t or ""), None)
        return cb

    def start(self, call: Callable[..., Any], **kwargs: Any) -> None:
        _runner(call, self, **kwargs)

    def iter(self, timeout: float = 0.1) -> Iterator[str]:
        while True:
            try:
                item = self.q.get(timeout=timeout)
            except Empty:
                if self._th is not None and (not self._th.is_alive()) and self.q.empty():
                    break
                continue
            if item is None:
                break
            yield str(item or "")


def _on_piece(state: StreamState, text: str, emit: Optional[Callable[[str], None]] = None) -> None:
    """
    공개 콜백 헬퍼(테스트 기대 시그니처).
    - emit가 주어지면 먼저 emit(text)
    - 그 다음 state.q에 text를 push
    """
    try:
        if emit:
            emit(text)
    except Exception:
        pass
    try:
        state.q.put(str(text or ""))
    except Exception:
        pass


def _runner(call: Callable[..., Any], state: StreamState, **kwargs: Any) -> None:
    """
    공급자 호출 러너(테스트 노출용).
    - 별도 스레드에서 call(**kwargs)를 실행
    - 예외를 메시지로 큐잉
    - 종료 시 None 센티넬을 큐잉
    """
    def _run() -> None:
        try:
            call(**kwargs)
        except Exception as e:  # pragma: no cover
            try:
                state.q.put(f"(오류) {type(e).__name__}: {e}")
            except Exception:
                pass
        finally:
            try:
                state.q.put(None)
            except Exception:
                pass

    th = Thread(target=_run, daemon=True)
    th.start()
    state._th = th


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

        state = StreamState()
        cb = state.make_callback()

        used_cb = False
        for name in ("on_delta", "on_token", "yield_text"):
            if name in params:
                kwargs[name] = cb
                used_cb = True
        if "stream" in params:
            kwargs["stream"] = True

        if used_cb:
            state.start(call, **kwargs)
            for piece in state.iter():
                yield piece
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
# ================================ [01] Agents Common — END ===============================
