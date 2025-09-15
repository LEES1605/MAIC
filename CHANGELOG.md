[01] START CHANGELOG.md
# Changelog
모든 눈에 보이는 변경은 이 파일에 기록합니다. 형식은 **Keep a Changelog**를 따르고, **Semantic Versioning**을 권장합니다.

## [Unreleased]
### Added
- CI: Nightly/Release 워크플로(엄격 게이트) 도입(스케줄/태그/수동 실행 지원)
- 보고서 문서(마스터 플랜)와 릴리스 노트 상호 링크

### Changed
- `src/backup/github_release.py`: 모듈 임포트 + 폴백/`Protocol` 기반으로 **완전 재구성**
- `src/llm/providers.py`: `openai` **동적 임포트**, `_secret` 가드화, 길이 초과(E501) 분리
- `src/config.py`: `Settings` 단일 바인딩 + 타입 선언(`type[_BaseFields]`)
- **출처 라벨 표준화**: `[문법책]` → **`[문법서적]`** (칩 표기 통일, 과거 라벨은 에일리어스로 흡수)
- **관리자 세션 키 통일**: `admin_mode` 단일 키 사용 (하위호환: 세션의 `is_admin` 감지 시 1회성 승격 후 제거)
- **CI 보강**: `.github/workflows/ci.yml`에 **persist 경로 매트릭스** 추가  
  - 케이스: 기본(ENV 미설정), `MAIC_PERSIST_DIR` 지정  
  - 단계: `ruff` → **No-Ellipsis Gate** → `mypy` → `pytest`
- **문서/정책**: **SSOT Persist 우선순위(현 버전) 명시**  
  `st.session_state['_PERSIST_DIR']` → `src.rag.index_build.PERSIST_DIR` → `env: MAIC_PERSIST_DIR` → `~/.maic/persist` 
  *(향후 `MAIC_PERSIST` 환경변수를 도입·우선으로 승격 예정)*
- 모드 프로필 섹션 **정규화 계층** 도입(get_profile): 동의어를 표준명으로 치환하고,
  `근거/출처`를 **항상 보강**. 모드별 표준 순서로 정렬하여 템플릿 표기 차이로
  테스트가 깨지는 문제를 근본적으로 방지.

### Fixed
- 반복 정의/`attr-defined`/`unused-ignore` 등 **mypy 경고 전수 해결**
- `ui_orchestrator` 로더 None 가드로 **런타임 안정성 향상**
- `rag_engine` 내부 타입 충돌/미사용 변수 정리
- Grammar/Passage 템플릿 테스트에서 요구하던 `근거/출처` 섹션 부재 문제 해결.
- `src/backup/github_release.py`: 누락된 상수/헬퍼로 인한 F821 연쇄 오류와 구획 불일치 수정.
  - 안전한 압축 해제(경로 탈출 차단), 릴리스 조회/업로드 견고화, 라인 길이 100자 준수.
  - 유니코드 생략기호 제거로 No‑Ellipsis Gate 통과.

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
[01] END CHANGELOG.md
