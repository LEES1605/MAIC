# PR 개요
- **주제(브랜치):** <!-- 예: ci/progress-smoke-20250917-b0 -->
- **변경 요약:** <!-- 한 줄 요약 -->
- **범위:** <!-- 파일/모듈 -->

## Plan/Part 진행 보고
- **Plan:** <!-- 예: CI 속도·안정화(2025-09) -->
- **Part:** <!-- 예: 빠른 피드백(병렬·캐시·스킵) -->
- **남은 브랜치 수:** <!-- 예: 1 / 총 3 -->
- **상태표(예시):**
  | Plan | Part | 브랜치 | 상태 |
  |---|---|---|---|
  | CI 속도·안정화(2025‑09) | pip 캐시 키 일관화 | ci/pip-cache-keys-20250917-b1 | ✅ |
  | CI 속도·안정화(2025‑09) | 릴리즈 아티팩트 안정화 | ci/release-artifacts-fix-20250917-b0 | ⏳/✅ |
  | CI 속도·안정화(2025‑09) | 빠른 피드백(병렬·스킵) | ci/fast-feedback-20250917-b0 | ⏳/✅ |

## 기능 활성화 확인(Activation)
- **스모크 체크(필수):** CI에서 `scripts/smoke_checks.py` 실행
- **앱/기능 확인(선택):** 필요 시 수동 확인 절차 기입
  - 로컬 예시:
    ```bash
    export PYTHONPATH=src
    python scripts/smoke_checks.py
    ```

## 체크리스트
- [ ] CI 성공(ruff/mypy/pytest)
- [ ] 스모크 체크 통과(`scripts/smoke_checks.py`)
- [ ] (해당 시) 앱 기동·접속 확인
- [ ] 문서/로그 표기(SSOT) 일치
- [ ] 릴리즈 자산/태그(해당 시) 정상
