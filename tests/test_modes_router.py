# [01] START: tests/test_modes_router.py (NEW FILE)
import pathlib
import sys

# Ensure 'src' is importable in Actions environments without editable installs
ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modes.types import Mode  # noqa: E402
from modes.router import ModeRouter  # noqa: E402


def test_mode_from_str_aliases():
    assert Mode.from_str("문법") is Mode.GRAMMAR
    assert Mode.from_str("문장분석") is Mode.SENTENCE
    assert Mode.from_str("지문설명") is Mode.PASSAGE
    assert Mode.from_str("grammar") is Mode.GRAMMAR
    assert Mode.from_str("sentence") is Mode.SENTENCE
    assert Mode.from_str("passage") is Mode.PASSAGE


def test_select_profile_and_render_prompt_structure():
    router = ModeRouter()
    # select_profile returns a bundle with profile metadata (no prompt text yet)
    empty_bundle = router.select_profile(Mode.SENTENCE)
    assert empty_bundle.profile.title
    assert len(empty_bundle.sections) > 0
    assert empty_bundle.prompt == ""

    # render_prompt builds a deterministic scaffold with sections in order
    bundle = router.render_prompt(
        mode=Mode.SENTENCE,
        question="Analyze the sentence: 'She had barely noticed the change.'",
        context_fragments=[
            "Source doc line 120: past perfect nuance around 'had + p.p.'",
            "Note: 'barely' as a limiter; often pairs with negatives.",
            "Subject 'She' refers to the narrator in paragraph 2.",
        ],
        source_label="[AI지식]",  # later will be [문법서적]/[이유문법] if RAG hits
    )
    assert "## 출력 스키마(섹션 순서 고정)" in bundle.prompt
    # verify sections order appears in prompt
    idx = [bundle.prompt.find(s) for s in bundle.sections]
    assert all(x >= 0 for x in idx) and idx == sorted(idx)
    # label guard
    assert "**라벨**: [AI지식]" in bundle.prompt
# [01] END: tests/test_modes_router.py
