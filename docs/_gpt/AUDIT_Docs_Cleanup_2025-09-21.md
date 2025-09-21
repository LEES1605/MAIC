
# AUDIT — Docs Cleanup Proposal (2025-09-21)

**목표:** 혼선/중복을 줄이고, SSOT(단일 진실 원천)를 `docs/_gpt/MASTERPLAN_vNext.md`로 고정.

## 1) 분류표

### ✅ 유지(Keep)
| 파일 | 이유 |
|---|---|
| `docs/_archive/2025-09-07_PROJECT_STATUS.md` | 이미 보관됨 |
| `docs/_gpt/MASTERPLAN_vNext.md` | SSOT (최신 합의안) |
| `docs/_gpt/prompts.sample.yaml` | 샘플 보존(YAML 표준) |
| `docs/_gpt/_policies/COLLAB_RULES_ADDENDUM_2025-09-17.md` | 정책문서(유지) |
| `docs/_gpt/_policies/COLLAB_RULES_PASTE_SAFE_2025-09-17.md` | 정책문서(유지) |
| `docs/_gpt/_policies/COLLAB_RULES_PROGRESS_2025-09-17.md` | 정책문서(유지) |
| `docs/_gpt/_policies/MODE_SSOT_2025-09-17.md` | 정책문서(유지) |
| `docs/_gpt/_reports/AUDIT_INDEX_RAG_2025-09-17.md` | 감사/리포트(유지) |
| `docs/_gpt/modes/_canon.schema.yaml` | 모드 설정/정의(테스트 참조 가능성 높음) |
| `docs/_gpt/modes/_canon.yaml` | 모드 설정/정의(테스트 참조 가능성 높음) |
| `docs/_gpt/modes/grammar.yaml` | 모드 설정/정의(테스트 참조 가능성 높음) |
| `docs/_gpt/modes/passage.yaml` | 모드 설정/정의(테스트 참조 가능성 높음) |
| `docs/_gpt/modes/sentence.yaml` | 모드 설정/정의(테스트 참조 가능성 높음) |

### ✏️ 이름 정규화(Rename)
| 파일 | 조치 | 이유 |
|---|---|---|
| `docs/pr/PR-A1r_app_slim_ops' | → `.md` 확장자 추가 | 확장자 누락 → .md로 변경 (문법 강조/렌더 안정화) |

### 🗄️ 보관(Archive → `docs/_archive/`로 이동)
| 파일 | 조치 | 이유 |
|---|---|---|
| `docs/_gpt/INVENTORY.json' | → `docs/_archive/`로 이동 | CI 환경 경로 포함(재생성 권장) |
| `docs/_gpt/MASTERPLAN.md' | → `docs/_archive/`로 이동 | 이전 마스터플랜(혼동 방지 목적) |
| `docs/_gpt/TREE.md' | → `docs/_archive/`로 이동 | 자동 생성본은 날짜 스냅샷화 권장(동기화 어려움) |
| `docs/pr/PR-A1_app_slim_admin_panel.md' | → `docs/_archive/`로 이동 | A1r에 의해 대체됨(역사 보존용) |
| `docs/roadmap/PLAN_legacy_sweep_and_app_slim.md' | → `docs/_archive/`로 이동 | MASTERPLAN_vNext로 통합됨(혼선 방지) |

### 🗑️ 삭제(Delete)
| 파일 | 조치 | 이유 |
|---|---|---|
| `docs/_gpt/prompts.sample.json' | → 삭제 | 동일 샘플의 YAML 버전 보유 → 중복 제거 |

## 2) 운영 권고
- `docs/_gpt/MASTERPLAN_vNext.md`만 SSOT로 유지(이전 MASTERPLAN은 보관).  
- PR 문서는 **머지 후** `docs/_archive/`로 이동해 이력 보존(현행 PR-A1 문서는 A1r로 대체).  
- 샘플 포맷은 **YAML로 통일**(JSON 샘플 제거).  
- `TREE.md`/`INVENTORY.json`은 날짜를 붙인 스냅샷만 남기고, 과거본은 보관.  

## 3) Git 명령 예시
```bash
# 이름 정규화
git mv docs/pr/PR-A1r_app_slim_ops docs/pr/PR-A1r_app_slim_ops.md

# 보관 (폴더가 없다면 생성)
mkdir -p docs/_archive
git mv docs/_gpt/MASTERPLAN.md docs/_archive/
git mv docs/roadmap/PLAN_legacy_sweep_and_app_slim.md docs/_archive/
git mv docs/pr/PR-A1_app_slim_admin_panel.md docs/_archive/

# 삭제
git rm docs/_gpt/prompts.sample.json

# (선택) 스냅샷 정리
git mv docs/_gpt/TREE.md docs/_archive/TREE_legacy.md
git mv docs/_gpt/INVENTORY.json docs/_archive/INVENTORY_legacy.json
```
