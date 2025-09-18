from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class BuildResult:
    """조립 결과물(실행계로 전달)."""
    system_prompt: str
    model: str
    max_tokens: Optional[int]
    temperature: Optional[float]
    guardrails: Dict[str, Any]
    mode_key: str
    raw_mode_entry: Dict[str, Any]


def _require(obj: Dict[str, Any], key: str) -> Any:
    if key not in obj:
        raise ValueError(f"missing required key: {key!r}")
    return obj[key]


def _to_text_guardrails(guard: Dict[str, Any]) -> str:
    """가드레일을 간단한 텍스트 규칙으로 표현."""
    if not guard:
        return "No additional safety switches."
    parts: list[str] = []
    for k, v in guard.items():
        parts.append(f"- {k}: {v}")
    return "\n".join(parts)


def compose_system_prompt(mode_key: str, entry: Dict[str, Any]) -> str:
    """모드 엔트리에서 시스템 프롬프트 문자열 생성."""
    persona = str(_require(entry, "persona")).strip()
    sysins = str(_require(entry, "system_instructions")).strip()
    cpol = str(_require(entry, "citations_policy")).strip()
    guard = entry.get("guardrails", {}) or {}

    guard_text = _to_text_guardrails(guard)

    # 구조적 템플릿(간결·일관)
    lines = [
        "[ROLE]",
        persona,
        "",
        "[INSTRUCTIONS]",
        sysins,
        "",
        "[CITATIONS]",
        f"출처 표시는 다음 라벨 중 하나를 사용합니다: {cpol}",
        "",
        "[GUARDRAILS]",
        guard_text,
        "",
        f"[MODE] {mode_key}",
    ]
    return "\n".join(lines).strip()


def build_for_mode(prompts: Dict[str, Any], mode_key: str) -> BuildResult:
    """
    prompts.yaml을 바탕으로 특정 모드의 시스템 프롬프트를 조립.
    - 필수 키: modes.{mode_key}.{persona, system_instructions, citations_policy}
    - 선택 키: guardrails, routing_hints.{model,max_tokens,temperature}
    """
    modes = _require(prompts, "modes")
    if mode_key not in modes:
        raise ValueError(f"unknown mode_key: {mode_key!r}")
    entry: Dict[str, Any] = modes[mode_key] or {}

    rh = entry.get("routing_hints", {}) or {}
    model = str(rh.get("model") or "").strip() or "gpt-5-pro"
    max_tokens = rh.get("max_tokens")
    temperature = rh.get("temperature")

    system_prompt = compose_system_prompt(mode_key, entry)

    return BuildResult(
        system_prompt=system_prompt,
        model=model,
        max_tokens=(
            int(max_tokens) if isinstance(max_tokens, int) else None  # noqa: PLR2004
        ),
        temperature=(
            float(temperature) if isinstance(temperature, (int, float)) else None
        ),
        guardrails=(entry.get("guardrails", {}) or {}),
        mode_key=mode_key,
        raw_mode_entry=entry,
    )
