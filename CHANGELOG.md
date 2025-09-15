# File: CHANGELOG.md
# Changelog
모든 눈에 보이는 변경은 이 파일에 기록합니다. 형식은 **Keep a Changelog**를 따르고, **Semantic Versioning**을 권장합니다.

## [Unreleased]
### Added
- CI: Nightly/Release 워크플로(엄격 게이트) 도입(스케줄/태그/수동 실행 지원)
- 보고서 문서(마스터 플랜)와 릴리스 노트 상호 링크

### Changed
- `src/backup/github_release.py`: 자산 해제 로직을 **안전 해제**(경로 탈출/링크 차단)로 전환. `.zip/.tar.gz` 모두 적용.
- `src/rag/search.py`: 스니펫의 유니코드 줄임표(`…`)를 **ASCII `...`**로 표준화(No‑Ellipsis Gate 통과).
- `app.py`: UI placeholder `"질문을 입력하세요..."`로 통일(줄임표 ASCII화).
- **PDF 백엔드**: 코드에서 `pypdf` 우선, 실패 시 `PyPDF2` 폴백으로 일원화.
- **의존성**: `pypdf>=6,<7`로 상향(보안 권고 반영).

### Fixed
- Patch Guard(줄임표 금지)로 인한 실패 케이스 제거.
- 릴리스 자산 해제 중 경로 탈출 가능성 제거.

### Removed
- 불필요한 `# type: ignore[...]` 주석 다수 (기존 항목 유지)

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
