from .types import PromptParts

def build_fallback(mode_token: str, q: str, ev1: str, ev2: str, cur_label: str) -> PromptParts:
    NOTICE = "안내: 현재 자료 연결이 원활하지 않아 간단 모드로 답변합니다. 핵심만 짧게 안내할게요."
    BASE = "너는 한국의 영어학원 원장처럼 따뜻하고 명확하게 설명한다. 모든 출력은 한국어로 간결하게."

    if mode_token == "문법설명":
        sys_p = BASE + " 주제에서 벗어난 장황한 배경설명은 금지한다."
        lines = []
        if not ev1 and not ev2:
            lines.append(NOTICE)
        lines += [
            "1) 한 줄 핵심", "2) 이미지/비유 (짧게)", "3) 핵심 규칙 3–5개 (• bullet)",
            "4) 예문 1개(+한국어 해석)", "5) 한 문장 리마인드", "6) 출처 1개: [출처: GPT지식/GEMINI지식/자료명]"
        ]
        usr_p = f"[질문]\n{q}\n\n[작성 지침]\n- 형식을 지켜라.\n" + "\n".join(f"- {x}" for x in lines)

    elif mode_token == "문장구조분석":
        sys_p = BASE + " 불확실한 판단은 '약 ~% 불확실'로 명시한다."
        usr_p = ("[출력 형식]\n0) 모호성 점검\n1) 괄호 규칙 요약\n2) S–V–O–C–M 한 줄 개요\n"
                 "3) 성분 식별: 표/리스트\n4) 구조·구문 단계적 설명\n5) 핵심 포인트 2–3개\n6) 출처 유형만 표기\n\n"
                 f"[문장]\n{q}")

    else:  # 지문분석
        sys_p = BASE + " 불확실한 판단은 '약 ~% 불확실'로 명시한다."
        usr_p = ("[출력 형식]\n1) 한 줄 요지\n2) 구조 요약(단락별 핵심)\n3) 핵심어 3–6개+이유\n4) 풀이 힌트\n\n"
                 f"[지문/질문]\n{q}")

    return PromptParts(system=sys_p, user=usr_p, source="Fallback")
