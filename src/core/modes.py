from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ModeSpec:
    key: str                 # 내부 키 (영문)
    label: str               # UI 라벨 (한글)
    goal: str                # 의도/목표
    output_shape: List[str]  # 출력 섹션 순서
    eval_focus: List[str]    # 평가 관점(미나쌤)
    prompt_rules: List[str]  # 프롬프트 핵심 규칙
    enabled: bool = True     # UI 노출 여부


# 사용자 규칙/교재명을 환경/시크릿에서 주입할 수도 있음(필요 시 확장).
MODES: Dict[str, ModeSpec] = {
    "grammar": ModeSpec(
        key="grammar",
        label="문법",
        goal="이유문법/깨알문법 근거로 규칙 설명 + 오류 교정",
        output_shape=["핵심규칙", "근거(국어↔영어)", "예문", "역예문(선택)", "한 줄 요약"],
        eval_focus=["정확도", "근거 제시", "간결성"],
        prompt_rules=[
            "근거 출처를 「이유문법」「깨알문법」에서 우선 인용(있으면)",
            "불필요한 창작 예시는 최소화, 반례는 1개 이내",
            "단계: 규칙→근거→예문→역예문→요약",
        ],
    ),
    "sentence": ModeSpec(
        key="sentence",
        label="문장",
        goal="사용자 괄호규칙/기타 규칙에 따른 문장 구조·어감 분석",
        output_shape=["토큰화", "구문(괄호규칙)", "의미해석", "개선 제안(선택)"],
        eval_focus=["규칙 준수", "분석 일관성", "재현성"],
        prompt_rules=[
            "사용자 제공 괄호규칙/분석 규칙을 최우선으로 적용",
            "단계: 원문→토큰화→구문→해석→개선 제안",
        ],
    ),
    "passage": ModeSpec(
        key="passage",
        label="지문",
        goal="수능형 지문을 쉬운 예시로 설명하고 주제/제목 정리",
        output_shape=["핵심 요지", "쉬운 예시/비유", "주제", "제목", "오답 포인트(선택)"],
        eval_focus=["평이화", "정보 보존", "집중도"],
        prompt_rules=[
            "순서: 요지→예시→주제→제목(→오답 포인트)",
            "문단이 길면 문단별 한 줄 요지 후 전체 요지",
        ],
    ),
    # 선택 모드(비활성 기본)
    "story": ModeSpec(
        key="story",
        label="이야기",
        goal="창작/구술형 서술 훈련",
        output_shape=["상황·등장인물", "전개", "마무리", "교정 포인트(선택)"],
        eval_focus=["전개", "연결성", "몰입감", "어휘 다양성"],
        prompt_rules=["친근한 톤, 비유 적극 사용, 장문 허용"],
        enabled=False,
    ),
}


def enabled_modes() -> List[ModeSpec]:
    """UI에 노출할 모드 목록(순서 보장: 문법→문장→지문→이야기)."""
    order = ["grammar", "sentence", "passage", "story"]
    return [MODES[k] for k in order if MODES.get(k) and MODES[k].enabled]


def find_mode_by_label(label: str) -> Optional[ModeSpec]:
    for m in MODES.values():
        if m.label == label:
            return m
    return None
