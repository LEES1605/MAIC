# [01] START: tests/test_modes_router.py (FULL REPLACEMENT)
from src.modes.types import Mode
from src.modes.router import ModeRouter


def test_mode_from_str_aliases():
    assert Mode.from_str("문법") is Mode.GRAMMAR
    assert Mode.from_str("문장분석") is Mode.SENTENCE
    assert Mode.from_str("지문설명") is Mode.PASSAGE
    assert Mode.from_str("grammar") is Mode.GRAMMAR
    assert Mode.from_str("sentence") is Mode.SENTENCE
    assert Mode.from_str("passage") is Mode.PASSAGE


def test_sentence_prompt_sections_and_label():
    r = ModeRouter()
    b = r.render_prompt(
        mode=Mode.SENTENCE,
        question="Analyze: It was John that broke the window.",
        context_fragments=["교과서 p.32: It~that 강조 구문 예시"],
        source_label="[문법서적]",
    )
    # 섹션 고정 순서 확인
    assert "## 출력 스키마(섹션 순서 고정)" in b.prompt
    order = [b.prompt.find(s) for s in b.sections]
    assert all(x >= 0 for x in order) and order == sorted(order)
    # 라벨 가드
    assert "**라벨**: [문법서적]" in b.prompt
# [01] END: tests/test_modes_router.py
