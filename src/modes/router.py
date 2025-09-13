# [PATCH-ROUTER-04] START: src/modes/router.py - replace render_prompt() only
def render_prompt(
    self,
    *,
    mode: Mode,
    question: str,
    context_fragments: Optional[Sequence[str]] = None,
    source_label: Optional[str] = None,
) -> PromptBundle:
    profile = get_profile(mode, ssot_root=self._ssot_root)
    label = sanitize_source_label(source_label)
    frags = clamp_fragments(context_fragments, max_items=5, max_chars_each=500)

    header = profile.header_template.format(
        title=profile.title,
        mode_kr=profile.extras.get("mode_kr", mode.value),
    )

    lines: list[str] = []
    lines.append(f"# {header}")
    lines.append("")
    # 헤더 표기는 기존대로 **라벨** 유지 (다른 테스트 호환)
    lines.append(f"**모드**: {mode.value}  |  **라벨**: {label}")
    lines.append("")
    lines.append("## 질의")
    lines.append(question.strip())
    lines.append("")

    if frags:
        lines.append("## 자료 컨텍스트 (최대 5개)")
        for i, s in enumerate(frags, 1):
            lines.append(f"- ({i}) {s}")
        lines.append("")

    lines.append("## 의도/목표")
    lines.append(profile.objective)
    lines.append("")

    # ✅ 문장 모드 전용: 괄호 규칙 라벨 표준 섹션 주입
    if mode is Mode.SENTENCE:
        lines.append("### 괄호 규칙 라벨 표준")
        lines.append(
            "라벨: S(주어), V(동사), O(목적어), C(보어), M(수식어), "
            "Sub(부사절), Rel(관계절), ToInf(to부정사), "
            "Ger(동명사), Part(분사), Appo(동격), Conj(접속)"
        )
        lines.append(
            "예시 형식: [Sub because it rained] , [S I] [V stayed] [M at home]"
        )
        lines.append("")

    if profile.must_do:
        lines.append("## 반드시 할 일")
        for item in profile.must_do:
            lines.append(f"- {item}")
        lines.append("")
    if profile.must_avoid:
        lines.append("## 피할 것")
        for item in profile.must_avoid:
            lines.append(f"- {item}")
        lines.append("")

    if profile.sections:
        lines.append("## 출력 스키마(섹션 순서 고정)")
        for i, sec in enumerate(profile.sections, 1):
            lines.append(f"{i}. {sec}")
        lines.append("")

    lines.append("> 위 스키마를 **순서대로** 준수하고, 각 섹션은 간결한 소제목으로 시작하세요.")
    prompt = "\n".join(lines).strip()

    return PromptBundle(
        mode=mode,
        profile=profile,
        source_label=label,
        prompt=prompt,
        sections=profile.sections,
        context_fragments=tuple(frags),
    )
# [PATCH-ROUTER-04] END
