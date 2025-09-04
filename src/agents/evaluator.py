# ============================== [01] Co-Teacher Evaluator — START ==============================
"""
Co-teacher(미나쌤) — '비평'이 아니라 '보완' 설명을 스트리밍으로 제공합니다.
가능하면 provider의 실스트리밍을 사용하고, 불가하면 최종 텍스트를 문장 단위로 나눠 yield합니다.
"""
from __future__ import annotations

from typing import Dict, Iterator, Optional, Any, List, Mapping
import inspect
import re
from queue import Queue, Empty
from threading import Thread


def _system_prompt(mode: str) -> str:
    mode_hint = {
        "문법설명": "핵심 규칙 → 간단 예시 → 흔한 오해 순서로 학생 눈높이에 맞춰 설명.",
        "문장구조분석": "품사/구문 역할을 표처럼 정리, 핵심 포인트 3개 요약.",
        "지문분석": "주제/요지/세부정보를 구분하고 근거 문장을 명확히 제시.",
    }.get(mode, "핵심→예시→한 줄 정리 순으로 간결히 설명.")
    return (
        "당신은 '미나쌤'이라는 보조 선생님(Co-teacher)입니다. "
        "첫 번째 선생님(피티쌤)의 답변을 바탕으로, 학생이 더 쉽게 이해하도록 "
        "중복을 최소화하며 빠진 부분을 보충하고 쉬운 비유/예시 또는 심화 포인트를 추가하세요. "
        "비평/채점/메타 피드백은 금지. " + mode_hint
    )


def _user_prompt(question: str, answer: Optional[str]) -> str:
    a = (answer or "").strip()
    head = "학생 질문:\n" + question.strip()
    if a:
        head += "\n\n첫 번째 선생님(피티쌤)의 답변을 바탕으로 보완해 주세요."
        body = (
            "\n\n[피티쌤의 답변]\n"
            f"{a}\n\n[요청]\n"
            "- 비평 금지, 중복 최소화\n"
            "- 더 쉬운 설명 또는 심화 포인트 보완\n"
            "- 핵심 → 예시 → 한 줄 정리"
        )
    else:
        body = (
            "\n\n[요청]\n"
            "- 핵심 → 예시 → 한 줄 정리\n"
            "- 질문 의도에 맞는 보완 설명"
        )
    return head + body


def _split_sentences(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r"(?<=[\.!\?。！？])\s+", text.strip())
    return [p for p in parts if p]


def _build_io_kwargs(
    params: Mapping[str, inspect.Parameter],
    *,
    system_prompt: str,
    user_prompt: str,
) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {}
    if "messages" in params:
        kwargs["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    else:
        if "prompt" in params:
            kwargs["prompt"] = system_prompt + "\n\n" + user_prompt
        elif "user_prompt" in params:
            kwargs["user_prompt"] = user_prompt
        if "system_prompt" in params:
            kwargs["system_prompt"] = system_prompt
        elif "system" in params:
            kwargs["system"] = system_prompt
    return kwargs


def _iter_provider_stream(*, system_prompt: str, user_prompt: str) -> Iterator[str]:
    """가능하면 실스트리밍으로, 아니면 폴백."""
    try:
        from src.llm import providers as prov
    except Exception as e:  # pragma: no cover
        yield f"(오류) provider 로딩 실패: {type(e).__name__}: {e}"
        return

    # 1) stream_text 우선
    st_fn = getattr(prov, "stream_text", None)
    if callable(st_fn):
        params = inspect.signature(st_fn).parameters
        kwargs = _build_io_kwargs(
            params, system_prompt=system_prompt, user_prompt=user_prompt
        )
        for piece in st_fn(**kwargs):
            yield str(piece or "")
        return

    # 2) call_with_fallback + callbacks
    call = getattr(prov, "call_with_fallback", None)
    if callable(call):
        params = inspect.signature(call).parameters
        kwargs = _build_io_kwargs(
            params, system_prompt=system_prompt, user_prompt=user_prompt
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

        # 콜백 미지원 → 폴백
        try:
            res = call(**kwargs)
            txt = res.get("text") if isinstance(res, dict) else str(res)
            yield str(txt or "")
            return
        except Exception as e:  # pragma: no cover
            yield f"(오류) {type(e).__name__}: {e}"
            return

    yield "(오류) LLM 어댑터를 찾을 수 없어요."


def evaluate_stream(
    *,
    question: str,
    mode: str,
    answer: Optional[str] = None,
    ctx: Optional[Dict[str, Any]] = None,
) -> Iterator[str]:
    """
    미나쌤 보완 스트림.
    - provider가 스트리밍을 지원하면 토막 단위로 yield
    - 아니면 최종 텍스트를 문장 단위로 분할 후 여러 번 yield
    """
    if not answer and ctx and isinstance(ctx, dict):
        maybe = ctx.get("answer")
        if isinstance(maybe, str):
            answer = maybe

    sys_p = _system_prompt(mode)
    usr_p = _user_prompt(question, answer)

    # 실스트리밍 시도
    got_any = False
    for piece in _iter_provider_stream(system_prompt=sys_p, user_prompt=usr_p):
        got_any = True
        yield str(piece or "")

    if got_any:
        return

    # 폴백: 문장 분할 스트림
    try:
        from src.llm import providers as prov
        call = getattr(prov, "call_with_fallback", None)
    except Exception:
        call = None

    if callable(call):
        params = inspect.signature(call).parameters
        kwargs = _build_io_kwargs(params, system_prompt=sys_p, user_prompt=usr_p)
        try:
            res = call(**kwargs)
        except Exception as e:  # pragma: no cover
            yield f"(오류) {type(e).__name__}: {e}"
            return
        txt = res.get("text") if isinstance(res, dict) else str(res)
        if not txt:
            txt = "보완할 내용을 찾지 못했어요. 질문을 조금 더 구체적으로 알려줄래요?"
        for chunk in _split_sentences(txt):
            yield chunk
        return

    yield "보완 에이전트를 사용할 수 없어서, 주 답변만 제공했어요."
# =============================== [01] Co-Teacher Evaluator — END ===============================
