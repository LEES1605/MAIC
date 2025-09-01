from .types import PromptParts

def build_fallback(mode_token: str, q: str, ev1: str, ev2: str, cur_label: str) -> PromptParts:
    BASE = "모든 출력은 한국어. 불필요한 맥락 요구 금지. 질문이 모호해도 간단 답변부터 시작하고, 부족하면 추가질문 1~2개를 제시."
    if mode_token == "문법설명":
        sys_p = BASE + " 장황한 배경설명 금지."
        lines = [
            "1) 한 줄 핵심", "2) 핵심 규칙 3–5개(•)", "3) 예문 1개(+해석)",
            "4) 보완 필요시 물어볼 추가질문 1–2개", "5) 한 줄 리마인드"
        ]
        usr_p = f"[질문]\n{q}\n\n[형식]\n" + "\n".join(f"- {x}" for x in lines)
    elif mode_token == "문장구조분석":
        sys_p = BASE + " 불확실한 판단은 '%'로 표기."
        usr_p = ("[출력 형식]\n0) 모호성 점검\n1) S–V–O–C–M 개요\n2) 성분 식별(•)\n3) 단계적 설명\n"
                 "4) 핵심 포인트 2–3개\n5) 필요시 추가질문 1–2개\n\n"
                 f"[문장]\n{q}")
    else:
        sys_p = BASE
        usr_p = ("[출력 형식]\n1) 한 줄 요지\n2) 단락별 핵심\n3) 핵심어 3–6개+이유\n4) 풀이 힌트\n5) 필요시 추가질문 1–2개\n\n"
                 f"[지문/질문]\n{q}")
    return PromptParts(system=sys_p, user=usr_p, source="Fallback")
