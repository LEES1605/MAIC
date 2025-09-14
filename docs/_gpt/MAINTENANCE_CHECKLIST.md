# [03] START: docs/_gpt/MAINTENANCE_CHECKLIST.md
# MAIC Maintenance Checklist (SSOT)

본 문서는 PR 생성 전/후에 확인하는 운영 체크리스트입니다.
문서·코드·테스트·CI 정책은 SSOT 원칙에 따라 docs/_gpt/ 하위에 정리됩니다.  # GPT Docs Index 참조
- 인덱스: TREE.md, INVENTORY.json  # scripts/gen_tree.py 산출물
- 규약: CONVENTIONS.md
- 모드 캐논: modes/_canon.yaml (스키마: _canon.schema.yaml)

## A. 파일/폴더 정합
- [ ] 루트 README.md만 사용(대소문자·중복 제거). 문서 본문은 docs/_gpt/로 일원화.  # 인덱스 가이드
- [ ] 중복 워크플로 정리: guard-patch.yml, gen-tree.yml만 남김(기능 중복본 삭제).
- [ ] tools/ 스크립트는 표준 경로 유지: guard_patch.py, validate_canon.py, generate_mode_docs.py

## B. SSOT/스키마
- [ ] docs/_gpt/modes/_canon.yaml 스키마 검증 OK(권고 섹션 ‘근거/출처’ 포함).
- [ ] modes 템플릿 동의어 표준화 규칙과 일치(혼용 표기 금지).  # 과거 혼재 이슈 방지

## C. CI 게이트(필수)
- [ ] Patch Guard: 숫자구획 전체 교체 위반 없음(No-Ellipsis 포함).
- [ ] Coverage Gate: 기준선(ratchet) 이상.
- [ ] Security: gitleaks/pip-audit/bandit OK.

## D. 문서 인덱스
- [ ] scripts/gen_tree.py로 TREE.md/INVENTORY.json 최신화(산출물은 docs/_gpt/만).
- [ ] pyproject.toml의 [tool.gen_tree] 설정이 최신(중앙화)이며, gen_tree.toml 잔존본 없음.

## E. CHANGELOG
- [ ] 사용자 가시 변경은 CHANGELOG.md [Unreleased]에 반영.

> 참고
> - 도구 설정 포인터(ruff/mypy)는 pyproject.toml에서 중앙 관리.  # [tool.*] 포인터
> - GPT Docs Index: PR 전 인덱스 산출물 확인 루틴 고정.
# [03] END: docs/_gpt/MAINTENANCE_CHECKLIST.md
