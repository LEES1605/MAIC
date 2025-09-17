# 협의규약 — Paste‑Safe 코드 블록 원칙 (2025‑09‑17)

## 목적
패치 적용 중 “코드 블록 내부 메타 텍스트(파일명/구획/START·END/줄번호 등)”로 인해 복붙 오류가 발생하는 문제를 방지하고, 브랜치·PR 운영을 표준화한다.

## 적용 범위
- 코드/문서/설정 파일 전체에 적용
- GitHub Actions 기반 **Actions‑only** 워크플로에 상시 적용

## 핵심 원칙 (Paste‑Safe)
1. **코드 블록에는 순수 코드만** 포함한다.  
   - 금지: START/END, 파일 경로, 구획명, 줄번호, diff 머리글 등의 메타 텍스트
2. **메타 정보는 코드 블록 밖**(본문 텍스트)에서 설명한다.  
   - 예: 파일 경로, 구획명, 변경 유형, 테스트/롤백 절차
3. **상호 연관 변경은 한 PR로 원자적(Atomic) 묶음**으로 제시한다.  
   - 같은 기능/정책을 완성하는 변경은 함께 제출, 무관한 정리는 별도 PR
4. **코드 제시 전 브랜치 이름을 선(先)제안**한다.  
   - 제안 → 코드 제시 → PR 생성 → CI 검증의 순서를 지킨다.

## 브랜치 네이밍 규약
- 형식: `<type>/<scope>-<short>-<YYYYMMDD>[-bN]`
- `type`: feat | fix | refactor | docs | chore | ci | test | perf | build  
- `scope`: 모듈/영역(예: rag-label, admin-ui, indexer)  
- `short`: 짧은 설명(소문자-하이픈)  
- `YYYYMMDD`: 생성일자, `-bN`: 동일 주제의 단계 번호  
- 예시  
  - `fix/rag-label-ssot-20250917-b1`  
  - `docs/collab-rules-paste-safe-20250917-b0`  
  - `docs/secrets-example-20250917-b0`

## 패치 제시 형식
- (본문) 파일 경로, 변경 요약, 테스트 방법, 롤백 절차 명시  
- (코드 블록) **복붙 가능한 순수 코드만** 첨부

## PR & CI 절차 (Actions‑only)
1. 제안된 브랜치 생성(웹 UI)  
2. 변경 적용(순수 코드 블록 사용)  
3. PR 생성 → 자동 CI 실행(ruff, mypy, pytest 등)  
4. 통과 시 머지, 문제 시 즉시 Revert

## Definition of Done (DoD)
- CI 전부 통과(정적 검사·테스트)  
- 연관 변경이 누락 없이 포함되어 주제 단위로 완결  
- 문서/로그/UI 표기가 SSOT 정책과 일치
