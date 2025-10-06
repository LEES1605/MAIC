from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Final


@dataclass(frozen=True)
class ModeSpec:
    key: str                 # 내부 키 (영문)
    label: str               # UI 라벨 (한글)
    goal: str                # 의도/목표
    output_shape: List[str]  # 출력 섹션 순서
    eval_focus: List[str]    # 평가 관점(미나쌤)
    prompt_rules: List[str]  # 프롬프트 핵심 규칙
    enabled: bool = True     # UI 노출 여부


# SSOT — canonical labels (Korean, 외부노출용)
MODE_GRAMMAR: Final[str] = "문법"
MODE_SENTENCE: Final[str] = "문장"
MODE_PASSAGE: Final[str] = "지문"

# 평가 루브릭용(라우팅은 SSOT 우선)
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
        # ✅ 테스트 스펙과 SSOT에 맞춰 정확 문구 포함
        goal='사용자 괄호규칙/기타 규칙과 "괄호 규칙 라벨 표준"에 따른 문장 구조·어감 분석',
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


# ---------------- SSOT 정규화 유틸 (내부/외부에서 공통 사용) ----------------

# 약어/영문/한글 섞인 토큰을 표준 라벨로 정규화
#  - 반환값은 한글 라벨(외부 노출 기준): "문법" / "문장" / "지문"
_CANON_MAP: Dict[str, str] = {
    # 문법
    "문법": MODE_GRAMMAR,
    "grammar": MODE_GRAMMAR,
    "gram": MODE_GRAMMAR,
    "g": MODE_GRAMMAR,
    # 문장
    "문장": MODE_SENTENCE,
    "sentence": MODE_SENTENCE,
    "sent": MODE_SENTENCE,
    "s": MODE_SENTENCE,
    # 지문
    "지문": MODE_PASSAGE,
    "passage": MODE_PASSAGE,
    "reading": MODE_PASSAGE,
    "read": MODE_PASSAGE,
    "p": MODE_PASSAGE,
}


def canon_mode(value: str) -> str:
    """
    주어진 토큰을 표준 라벨(문법/문장/지문)로 정규화한다.

    Examples
    --------
    >>> canon_mode("Grammar")
    '문법'
    >>> canon_mode("문장")
    '문장'
    >>> canon_mode("reading")
    '지문'
    """
    token = value.strip().lower()
    if not token:
        raise ValueError("empty mode token")
    try:
        return _CANON_MAP[token]
    except KeyError as exc:
        raise ValueError(f"unknown mode token: {value!r}") from exc
