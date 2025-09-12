# src/agents/responder.py
# ================================ Answer Stream ================================
from __future__ import annotations

from typing import Iterator, Optional, Dict
from src.agents._common import stream_llm

# ================================ _system_prompt (REPLACE) ================================
def _system_prompt(mode: str) -> str:
    """
    교육 품질 규칙(선생님 지침) 반영:
    - grammar : 이유문법→핵심 규칙→예시 2개→깨알문법 박스→한 줄 정리
    - sentence: 괄호규칙(라벨) 엄격 적용
    - passage : 쉬운 설명 + 예시, 주제/제목, 근거 문장(짧게)
    """
    base = (
        "당신은 학생을 돕는 영어 선생님입니다. 불필요한 말은 줄이고, "
        "짧은 문장과 단계적 설명을 사용하세요. "
        "출처 우선순위: (1) 선생님 수업자료 > (2) 표준 문법서/교과 > (3) 일반 지식."
    )
    if mode in ("grammar", "문법"):
        rules = (
            "형식:\n"
            "1) [이유문법] 규칙이 생긴 이유와 핵심 원리를 한 문단으로 설명\n"
            "2) [핵심 규칙]을 번호 목록으로 2~4개\n"
            "3) [예시] 간단한 예문 2개 (한글 해설 포함)\n"
            "4) [깨알문법] 자주 하는 오해/함정 2개를 박스 형태로 정리\n"
            "5) [한 줄 정리]\n"
        )
    elif mode in ("sentence", "문장"):
        rules = (
            "문장구조분석은 반드시 괄호규칙으로 출력합니다.\n"
            "라벨 표준: S(주어), V(동사), O(목적어), C(보어), M(수식어), "
            "Sub(부사절), Rel(관계절), ToInf(to부정사), Ger(동명사), Part(분사), Appo(동격), Conj(접속)\n"
            "예시 형식: [Sub because it rained] , [S I] [V stayed] [M at home]\n"
            "출력 순서: 괄호분석 → 한 줄 요약(핵심 포인트 3개)\n"
        )
    elif mode in ("passage", "지문"):
        rules = (
            "지문을 쉬운 말로 설명하고, 주제/제목을 명시하며, 근거 문장을 1~2개 짧게 제시하세요.\n"
            "형식: ①핵심 요지(쉬운 말) ②예시/비유 ③주제 ④제목 ⑤근거 문장(짧게 인용)\n"
        )
    else:
        rules = "학생 눈높이에 맞춰 핵심→예시→한 줄 정리로 설명하세요."
    return base + "\n" + rules
# =========================================================================================

def answer_stream(
    *, question: str, mode: str, ctx: Optional[Dict[str, str]] = None
) -> Iterator[str]:
    """
    주답변(피티쌤) 스트리밍 제너레이터.
    - 공통 SSOT(stream_llm)만 호출하여 중복 제거
    - split_fallback=True: 콜백 미지원 provider에서 문장단위로 의사 스트리밍
    """
    sys_p = _system_prompt(mode)
    yield from stream_llm(
        system_prompt=sys_p,
        user_prompt=question,
        split_fallback=True,
    )
