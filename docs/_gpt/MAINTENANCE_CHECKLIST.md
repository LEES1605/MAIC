# [01] START: docs/_gpt/MAINTENANCE_CHECKLIST.md
# MAIC Maintenance Checklist (SSOT)

본 문서는 PR 생성 전/후에 확인하는 운영 체크리스트입니다.
- 인덱스: `docs/_gpt/TREE.md`, `docs/_gpt/INVENTORY.json`
- 규약: `docs/_gpt/CONVENTIONS.md`
- 모드 캐논: `docs/_gpt/modes/_canon.yaml` (스키마: `_canon.schema.yaml`)

## A. 파일/폴더 정합
- [ ] 루트 README.md만 사용(중복/대소문자 변형 제거)
- [ ] 중복 워크플로 정리: `guard-patch.yml`, `gen-tree.yml`만 유지
- [ ] `tools/` 표준 스크립트 유지: `guard_patch.py`, `validate_canon.py`, `generate_mode_docs.py`

## B. SSOT/스키마
- [ ] `_canon.yaml` 스키마 검증 OK(권고 섹션 ‘근거/출처’ 포함)
- [ ] 템플릿 동의어 정규화 규칙 부합(혼용 표기 금지)

## C. CI 게이트
- [ ] Patch Guard: 숫자구획 전체 교체 위반 없음(No‑Ellipsis 포함)
- [ ] Coverage Gate 기준선 이상
- [ ] Security: gitleaks / pip-audit / bandit OK

## D. 문서 인덱스
- [ ] `scripts/gen_tree.py`로 TREE/INVENTORY 최신화(산출물은 `docs/_gpt/`만)
- [ ] `pyproject.toml`의 `[tool.gen_tree]` 설정 최신, `gen_tree.toml` 잔존 없음

## E. CHANGELOG
- [ ] 사용자 가시 변경은 `CHANGELOG.md` [Unreleased]에 반영
# [01] END: docs/_gpt/MAINTENANCE_CHECKLIST.md
