
# PR‑A1 — app.py 슬림화(관리자 패널 분리 · All‑in‑One)
브랜치: `refactor/PR-A1-app-slim-admin-panel`

## 0) 원인 분석
- 관리자 패널 관련 로직([11.4]/[11.45]/[11.5]/[12]/[13]/[15]/[16])이 `app.py`에 집중되어 파일이 비대하고 유지보수가 어렵습니다. 【근거: app.py 구획 참조】
- UI/서비스 로직 분리를 통해 모듈 경계를 명확히 하고, 이후 비동기화/테스트 강화에 유리한 구조를 마련합니다.

## 1) 수정 목표
- 기능/UX 변화 없이 **관리자 패널**을 `src/ui_admin/*`/`src/services/*`로 분리하여 `app.py`를 슬림화.
- 기존 보조 헬퍼/세션키 체계를 재사용(호환), 회귀 위험 최소화.

## 2) 변경 요약
- **신규 파일(3)** — *신규 파일*
  - `src/ui_admin/indexing_panel.py` : 오케스트레이터 헤더/스캔/인덱싱/소스목록 UI
  - `src/services/index_state.py`     : 인덱스 상태/로그/스텝 관리 및 UI 보조
  - `src/services/index_actions.py`   : 인덱싱 실행·ZIP·Release 업로드·prepared API 로딩
- **app.py 변경**
  - `[19] body & main` **구획 전체 교체**: 관리자 영역을 외부 모듈 호출로 대체.  
    (reference: `src.ui_admin.indexing_panel`)  fileciteturn2file0
  - 아래 **구획 전체 삭제**(이관 완료):
    - `[11.4] admin index: request consumer`  fileciteturn2file0
    - `[11.45] index steps render helpers`    fileciteturn2file0
    - `[11.5] admin index helpers`            fileciteturn2file0
    - `[12] diag header`                       fileciteturn2file0
    - `[13] admin indexing panel`              fileciteturn2file0
    - `[15] prepared scan panel`               fileciteturn2file0
    - `[16] indexed sources panel`             fileciteturn2file0

## 3) 교체/추가 코드
### 3-1) app.py — `[19] body & main` **구획 전체 교체**
> 파일: `app.py`  
> 교체본: [`app__section_19_after.py`](../app__section_19_after.py) 내 블록 그대로 사용

### 3-2) *신규 파일* — `src/ui_admin/indexing_panel.py`
> 파일 생성, 전체 내용은 리포 아래 첨부 또는 PR diff 참고.

### 3-3) *신규 파일* — `src/services/index_state.py`
> 파일 생성, 전체 내용은 리포 아래 첨부 또는 PR diff 참고.

### 3-4) *신규 파일* — `src/services/index_actions.py`
> 파일 생성, 전체 내용은 리포 아래 첨부 또는 PR diff 참고.

## 4) 삭제 지시(구획 전체 삭제)
- `app.py`에서 다음 구획을 **START~END 통째로 삭제**하세요: [11.4]/[11.45]/[11.5]/[12]/[13]/[15]/[16].  
  (이관 완료. 호출부는 `[19]` 교체본에서 외부 모듈을 사용함.)  fileciteturn2file0

## 5) 테스트 방법 (Actions‑only)
- `pytest -q` (임포트/스모크) → Green
- Streamlit 런타임:
  - 관리자 모드 진입 → ①🧪오케스트레이터 ②🔍스캔 ③🔧인덱싱 ④📄소스목록 4섹션 정상 동작
  - 일반 모드 UX 변화 없음
- 문자열 검색(레거시 재유입 방지):
  - `app.py` 내 `_render_admin_*`/`_run_admin_index_job` 직접 호출 **미사용** 확인
- 회귀 체크: 강제 재인덱싱(진행바/로그/요약/ZIP/Release 업로드) 플로우 정상

## 6) 롤백 전략
- `[19]` 구획을 이전 버전으로 복귀, 신규 3파일 삭제 → 즉시 원상복구 가능.

## 7) 메모
- 본 PR은 “호출 경계” 외부화 + “실제 본문 이관”을 **한 번에** 수행했습니다.
- 추후 비동기 인덱싱/스트리밍 라이터/CI 보안 강화 등은 후속 PR에서 진행합니다.
