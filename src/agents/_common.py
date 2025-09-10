# -----------------------------------------------------------------------------
# src/agents/_common.py
# Wave‑2.1: Agents common helpers (public API kept stable)
# - 목적: responder.py / evaluator.py 중복 유틸 단일화 준비
# - 이 파일만 교체하며, 에이전트 파일은 다음 PR에서 연동
# -----------------------------------------------------------------------------
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable, Iterator, List, Optional

__all__ = [
    "_split_sentences",
    "_on_piece",
    "_runner",
    "StreamState",
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

    # 개행은 보존하고, 그 외 공백만 단일 공백으로 정규화
    # (개행을 먼저 없애면 (?<=\n) 분리 규칙이 무력화됨)
    normalized = re.sub(r"[ \t\f\v]+", " ", raw)

    # 분리 규칙 적용
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
    - emit 예외는 상위에서 처리(이 함수는 전파)
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
