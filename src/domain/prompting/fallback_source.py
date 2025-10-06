# ======================= prompting/fallback_source.py — START ====================
from __future__ import annotations

DEFAULT_PROMPTS = {
    "modes": {
        "grammar": {
            "system": (
                "영어 문법 교사. 오류를 명확히 지적하고 간명한 근거/예시를 제공합니다. "
                "학습자 수준에 맞게 설명하세요."
            ),
            "fewshot": [],
        },
        "sentence": {
            "system": (
                "영작 코치. 자연스러운 대안을 2~3개와 선택 이유를 제공합니다. "
                "정중/공손 톤을 유지하세요."
            ),
            "fewshot": [],
        },
        "passage": {
            "system": (
                "독해 코치. 지문 요약과 핵심 어휘/문법 포인트, 이해확인 질문 3개를 제시하세요."
            ),
            "fewshot": [],
        },
    }
}
# ======================== prompting/fallback_source.py — END =====================
