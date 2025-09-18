from __future__ import annotations

from pathlib import Path

from src.runtime.prompt_builder import build_for_mode
from src.runtime.prompts_loader import load_prompts


def _load_sample():
    root = Path(__file__).resolve().parents[1]
    sample_path = root / "docs" / "_gpt" / "prompts.sample.json"
    return load_prompts(
        owner="dummy",
        repo="dummy",
        local_path=sample_path,
    )


def test_build_for_grammar_contains_persona_and_citations() -> None:
    prompts = _load_sample()
    res = build_for_mode(prompts, "grammar")
    assert "[ROLE]" in res.system_prompt
    assert "[INSTRUCTIONS]" in res.system_prompt
    assert "이유문법" in res.system_prompt  # 샘플 내용에 포함
    assert "CITATIONS" in res.system_prompt
    assert res.model  # 존재 확인


def test_build_for_sentence_uses_routing_hints() -> None:
    prompts = _load_sample()
    res = build_for_mode(prompts, "sentence")
    # 샘플은 gemini-pro로 설정되어 있음
    assert res.model in ("gemini-pro", "gpt-5-pro")
