
---

## 2) `CHANGELOG.md` (신규)

```md
# Changelog
모든 눈에 보이는 변경은 이 파일에 기록합니다. 형식은 **Keep a Changelog**를 따르고, **Semantic Versioning**을 권장합니다.

## [Unreleased]
### Added
- CI: Nightly/Release 워크플로(엄격 게이트) 도입(스케줄/태그/수동 실행 지원)
- 보고서 문서(마스터 플랜)와 릴리스 노트 상호 링크

### Changed
- `src/backup/github_release.py`: 모듈 임포트 + 폴백/Protocol 기반으로 **완전 재구성**
- `src/llm/providers.py`: `openai` **동적 임포트**, `_secret` 가드화, 길이 초과(E501) 분리
- `src/config.py`: `Settings` 단일 바인딩 + 타입 선언(`type[_BaseFields]`)

### Fixed
- 반복 정의/attr-defined/unused-ignore 등 **mypy 경고 전수 해결**
- `ui_orchestrator` 로더 None 가드로 **런타임 안정성 향상**
- `rag_engine` 내부 타입 충돌/미사용 변수 정리

### Removed
- 불필요한 `# type: ignore[...]` 주석 다수

---

## [vX.Y.Z] - 2025-09-02
> 최초의 엄격 게이트 통과 릴리스. (버전/날짜는 실제 태그에 맞춰 갱신)

### Added
- CI 게이트: ruff, mypy(strict), pytest(있을 때)
- Nightly/Release 워크플로

### Fixed
- 린트/타입 이슈 다수

[Unreleased]: https://github.com/LEES1605/MAIC/compare/index-20250829-071822...HEAD
[index-20250829-071822]: https://github.com/LEES1605/MAIC/releases/tag/index-20250829-071822
