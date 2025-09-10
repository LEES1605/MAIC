# ================================ [01] Answer Stream — START ================================
from __future__ import annotations

from typing import Iterator, Dict, Any, Optional, Callable, Mapping
import inspect
from queue import Queue, Empty
from threading import Thread

# 공통 문장분리기(중복 제거)
from src.agents._common import _split_sentences


def _system_prompt(mode: str) -> str:
    hint = {
        "문법설명": "핵심 규칙 → 간단 예시 → 흔한 오해 순서로 쉽게 설명하세요.",
        "문장구조분석": "품사/구문 역할을 표처럼 정리하고 핵심 포인트 3개를 요약하세요.",
        "지문분석": "주제/요지/세부정보를 구분하고 근거 문장을 제시하세요.",
    }.get(mode, "학생 눈높이에 맞춰 핵심→예시→한 줄 정리로 설명하세요.")
    return (
        "당신은 학생을 돕는 영어 선생님입니다. 불필요한 말은 줄이고, "
        "짧은 문장과 단계적 설명을 사용하세요. " + hint
    )


def _build_io_kwargs(
    params: Mapping[str, inspect.Parameter],
    *,
    system_prompt: str,
    question: str,
) -> Dict[str, Any]:
    """providers API 시그니처에 맞게 kwargs 구성"""
    kwargs: Dict[str, Any] = {}
    if "messages" in params:
        kwargs["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]
    else:
        if "prompt" in params:
            kwargs["prompt"] = question
        elif "user_prompt" in params:
            kwargs["user_prompt"] = question
        if "system_prompt" in params:
            kwargs["system_prompt"] = system_prompt
        elif "system" in params:
            kwargs["system"] = system_prompt
    return kwargs


def _iter_provider_stream(
    *, system_prompt: str, question: str
) -> Iterator[str]:
    """
    가능한 경우 실제 스트리밍으로 토막을 yield.
    - 우선순위: providers.stream_text → call_with_fallback(stream+callbacks)
    - 전부 불가하면 문장 단위로 분할하여 의사-스트리밍
    """
    try:
        from src.llm import providers as prov
    except Exception as e:  # pragma: no cover
        yield f"(오류) provider 로딩 실패: {type(e).__name__}: {e}"
        return

    # 1) stream_text(messages|prompt)를 지원하면 그대로 사용
    stream_fn = getattr(prov, "stream_text", None)
    if callable(stream_fn):
        params = inspect.signature(stream_fn).parameters
        kwargs = _build_io_kwargs(
            params, system_prompt=system_prompt, question=question
        )
        for piece in stream_fn(**kwargs):
            yield str(piece or "")
        return

    # 2) call_with_fallback + callbacks(on_delta / on_token / yield_text)
    call = getattr(prov, "call_with_fallback", None)
    if callable(call):
        params = inspect.signature(call).parameters
        kwargs = _build_io_kwargs(
            params, system_prompt=system_prompt, question=question
        )

        q: "Queue[Optional[str]]" = Queue()

        def _on_piece(t: Any) -> None:
            try:
                q.put(str(t or ""))
            except Exception:
                pass

        used_cb = False
        for name in ("on_delta", "on_token", "yield_text"):
            if name in params:
                kwargs[name] = _on_piece
                used_cb = True
        if "stream" in params:
            kwargs["stream"] = True

        # 콜백이 있으면 진짜 스트리밍
        if used_cb:
            def _runner() -> None:
                try:
                    call(**kwargs)
                except Exception as e:  # pragma: no cover
                    q.put(f"(오류) {type(e).__name__}: {e}")
                finally:
                    q.put(None)

            th = Thread(target=_runner, daemon=True)
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

        # 콜백 미지원 → 최종 텍스트를 문장 단위로 쪼개어 의사-스트리밍
        try:
            res = call(**kwargs)
            txt = res.get("text") if isinstance(res, dict) else str(res)
            for chunk in _split_sentences(str(txt or "")):
                yield chunk
            return
        except Exception as e:  # pragma: no cover
            yield f"(오류) {type(e).__name__}: {e}"
            return

    # 3) 어떤 provider도 없으면 메시지
    yield "(오류) LLM 어댑터를 찾을 수 없어요."


def answer_stream(
    *, question: str, mode: str, ctx: Optional[Dict[str, Any]] = None
) -> Iterator[str]:
    """
    주답변(피티쌤) 스트리밍 제너레이터.
    App 단에서 문장 버퍼링을 적용하므로, 여기서는 '토막'을 잘게 흘려보내면 됩니다.
    """
    system_prompt = _system_prompt(mode)
    # 필요 시 ctx 활용 여지(예: RAG 요약 삽입) — 현 단계에선 미사용
    yield from _iter_provider_stream(
        system_prompt=system_prompt, question=question
    )
# ================================= [01] Answer Stream — END =================================
