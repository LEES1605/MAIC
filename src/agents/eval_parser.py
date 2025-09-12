# src/agents/eval_parser.py
from __future__ import annotations

from typing import TypedDict


class EvalField(TypedDict, total=False):
    state: str
    reason: str


class EvalParsed(TypedDict, total=False):
    sections: EvalField
    bracket: EvalField
    factual: EvalField
    summary: str


def parse_eval_block(text: str) -> EvalParsed:
    """
    미나쌤 출력 텍스트에서 결과를 파싱해 구조화.

    포맷 예:
    [형식 체크]
    - 섹션: OK (모두 충족)
    - 괄호규칙: FAIL (라벨 누락 S/V/O/C)
    - 사실성: WARN (추정 표현 과다)
    [피드백]
    - …
    [한 줄 총평]
    - …

    반환 키:
    - sections/bracket/factual: {"state": "...", "reason": "..."}
    - summary: "..."
    """
    import re

    res: EvalParsed = {
        "sections": {"state": "", "reason": ""},
        "bracket": {"state": "", "reason": ""},
        "factual": {"state": "", "reason": ""},
        "summary": "",
    }

    def _cap(pattern: str) -> tuple[str, str]:
        m = re.search(pattern, text, flags=re.MULTILINE)
        if not m:
            return "", ""
        return (m.group(1) or "").strip(), (m.group(2) or "").strip()

    s, r = _cap(r"^-?\s*섹션:\s*(OK|FAIL)\s*(?:\((.*?)\))?")
    if s:
        res["sections"]["state"] = s
        if r:
            res["sections"]["reason"] = r

    s, r = _cap(r"^-?\s*괄호규칙:\s*(OK|FAIL)\s*(?:\((.*?)\))?")
    if s:
        res["bracket"]["state"] = s
        if r:
            res["bracket"]["reason"] = r

    s, r = _cap(r"^-?\s*사실성:\s*(OK|WARN)\s*(?:\((.*?)\))?")
    if s:
        res["factual"]["state"] = s
        if r:
            res["factual"]["reason"] = r

    m = re.search(r"\[한 줄 총평\]\s*\n-?\s*(.+)", text, flags=re.MULTILINE)
    if m:
        res["summary"] = (m.group(1) or "").strip()

    return res
