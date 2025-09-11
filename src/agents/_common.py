# src/agents/_common.py
# -----------------------------------------------------------------------------
# Wave‑2.0: Agents common helpers (no functional change for responder/evaluator)
# - 목적: responder.py / evaluator.py의 중복 유틸을 단일화할 준비
# - 이 파일만 추가하며, 기존 에이전트 파일은 다음 PR에서 수정
# -----------------------------------------------------------------------------
from __future__ import annotations

import re
import inspect
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Callable, Iterable, Iterator, List, Optional

__all__ = [
    "_build_io_kwargs",
    "_errlog",
    "_split_sentences",
    "_on_piece",
    "_runner",
    "StreamState",
]


# -------------------------- sentence segmentation ---------------------------
_SENT_SEP = re.compile(
    r"(?<=[\.\?!。？！…])\s+|"       # 일반 문장부호 + 공백
    r"(?<=\n)\s*|"                   # 줄바꿈
    r"(?<=[;:])\s+"                  # 세미콜론/콜론
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
    state.buffer += str(piece)
    emit(str(piece))

def _runner(chunks: Iterable[str], on_piece: Callable[[str], None]) -> None:
    """
    제너레이터/이터러블에서 조각을 꺼내 콜백(on_piece)에 전달.
    - pieces가 문자열이 아닐 수도 있어 str() 강제
    - StopIteration 이외 예외는 상위에서 처리
    """
    for c in chunks:
        on_piece(str(c))

def _build_io_kwargs(
    params: Mapping[str, inspect.Parameter],
    *,
    system_prompt: str,
    user_prompt: str,
) -> Dict[str, Any]:
    """
    providers API 시그니처에 맞게 kwargs 구성
    """
    kwargs: Dict[str, Any] = {}
    if "messages" in params:
        kwargs["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    else:
        if "prompt" in params:
            # 시스템 프롬프트 포함 여부에 따라 처리
            if "system" not in params and "system_prompt" not in params:
                kwargs["prompt"] = f"{system_prompt}\n\n{user_prompt}"
            else:
                kwargs["prompt"] = user_prompt
        if "user_prompt" in params:
            kwargs["user_prompt"] = user_prompt
        if "system_prompt" in params:
            kwargs["system_prompt"] = system_prompt
        elif "system" in params:
            kwargs["system"] = system_prompt
    return kwargs

def _errlog(msg: str, where: str = "", exc: Exception | None = None) -> None:
    """
    표준 에러 로깅 (민감정보 제외).
    """
    try:
        prefix = f"{where} " if where else ""
        print(f"[ERR] {prefix}{msg}")
        if exc:
            import traceback
            tb_lines = traceback.format_exception(exc, value=exc, tb=exc.__traceback__)
            for line in "".join(tb_lines).strip().splitlines():
                print(f"[ERR] {prefix}{line}")
    except Exception:
        print(f"[ERR] {where} {msg}")
