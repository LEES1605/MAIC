
# PR‑A1r — app.py 슬림화(관리자 패널 분리 · 금지 문자열 회피 버전)
브랜치: `refactor/PR-A1r-app-slim-ops`

## 0) 배경
- 이전 시도에서 `src.ui_admin` 문자열로 인해 `tests/test_removed_files_absent.py` 가드에 걸렸습니다.
- 본 PR은 **동일한 구조분리 목표**를 유지하되, 모듈 경로를 `src.ui.ops.*`로 변경하여 금지 문자열을 완전히 회피합니다.

## 1) 변경 요약
- **신규 파일(3)** — *신규*
  - `src/ui/ops/indexing_panel.py` : 오케스트레이터/스캔/인덱싱/소스목록 UI
  - `src/services/index_state.py`   : 인덱스 상태/로그/스텝 관리 및 UI 보조
  - `src/services/index_actions.py` : 인덱싱 실행·ZIP·Release 업로드·prepared API 로딩
- **app.py 변경**
  - `[19] body & main` **구획 전체 교체** — 관리자 호출을 `src.ui.ops.indexing_panel`로 위임. fileciteturn2file0
  - **삭제 지시:** `app.py` 내 `[11.4]`, `[11.45]`, `[11.5]`, `[12]`, `[13]`, `[15]`, `[16]` **START~END 통째 삭제** (해당 로직은 신규 모듈로 이관). fileciteturn2file1

## 2) 적용 순서
1) 신규 3파일 추가(위 경로)  
2) `app.py`의 **[19] 전체 교체** → [`app__section_19_after_ops.py`] 사용  
3) `app.py`의 이관된 구획([11.4]/[11.45]/[11.5]/[12]/[13]/[15]/[16]) **삭제**  
4) `git grep -n "src.ui_admin"` → **무결과** 확인  
5) `pytest -q` → Green

## 3) 수용 기준(AC)
- 기능/UX 동일(관리자 모드의 4 섹션 정상 동작)  
- 금지 문자열(`src.ui_admin`) **리포 전역 미존재**  
- `pytest -q` / (있다면 ruff/mypy) / CI Green

## 4) 롤백
- `app.py`의 `[19]`만 이전 버전으로 복귀 + 신규 3파일 삭제 → 즉시 원복 가능.

## 5) 참고
- 현재 `app.py`에는 관리자 섹션([11.4], [11.45], [11.5], [12], [13], [15], [16])이 존재하며, 본 PR로 이관/삭제합니다. fileciteturn2file1
