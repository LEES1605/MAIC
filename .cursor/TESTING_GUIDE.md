# ============================ [01] TESTING GUIDE — START ============================

# MAIC Testing Guide
> 코딩 초보도 바로 따라 할 수 있게, **아주 쉬운 말**로 정리했습니다.  
> 목표: “**전원 버튼 눌러보기(스모크)** → 작은 부품(유닛) → 연결(통합) → 사용자 시나리오(E2E)” 순서로 안전하게 확인해요.

---

## 1) 테스트 피라미드 한눈에 보기
- **스모크(Smoke)**: “켜짐?” → 아주 빠르고, 외부 의존성 없음  
  - 예) 문법 오류 없는지, 필수 키 누락 즉시 잡는지
- **유닛(Unit)**: “작은 부품 하나 제대로?”  
  - 예) 가공 함수, 작은 유틸의 입력/출력 확인
- **통합(Integration)**: “부품끼리 연결하면 제대로?”  
  - 예) 로컬 인덱스 + 검색 조합
- **E2E(선택)**: “사용자 입장에서 처음~끝까지?”  
  - 느리고 복잡해서, 필요할 때만

> 지금 리포는 **스모크 중심**으로 깔끔하게 시작합니다.  
> 나중에 필요에 따라 유닛/통합/E2E를 단계적으로 늘려요.

---

## 2) 지금 리포에 들어있는 테스트
- `tests/test_smoke_gdrive_driver.py`  
  - `src.integrations.gdrive` 임포트 OK?  
  - **필수 환경변수**(`GDRIVE_PREPARED_FOLDER_ID`) 없으면 **친절한 오류**를 내나?
- `tests/test_smoke_app_import.py`  
  - `app.py`를 **실행하지 않고** `compile()`로 **문법만** 확인(네트/Streamlit 미의존)

---

## 3) 로컬에서 돌리는 방법 (명령어)
> macOS, Windows 모두 동일. 터미널/PowerShell에서 리포 루트 기준.

1) (처음 1회) 가상환경 만들고 진입 *(선택)*  
   ```bash
   python -m venv .venv
   # macOS/Linux
   source .venv/bin/activate
   # Windows (PowerShell)
   .\.venv\Scripts\Activate.ps1
