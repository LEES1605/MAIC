# MAIC 마스터 플랜 (MASTERPLAN)

Source-of-Truth: github://LEES1605/MAIC@main/docs/_gpt/MASTERPLAN.md
Version: 2025-09-07
Owner: @LEES1605

## 0) 비전
MAIC(LEES AI Teacher)는 학생에게 **정확하고 친절한 학습 도움**을 제공하고, 운영자는 **안정적이고 투명한 관리**를 할 수 있도록 설계한다. 핵심은 **데이터 품질(인덱싱)**, **응답 품질(LLM+RAG)**, **사용성(미니멀 UI)**, **안정성(관측/백업/릴리스)**.

---

## 1) 목표(우선순위)
1. **관리자 기능의 안정**  
   - 인덱싱·스캔·업로드·복원 플로우를 서비스 계층으로 일원화, UI는 호출만.
2. **아이들 질문에 대한 답변 퀄리티 향상**  
   - 재랭킹/중복제거/근거성 평가 루프 적용, 실패 시 폴백 메시지.
3. **사용자 친화적 챗 UI(미니멀리즘)**  
   - 헤더 상태칩 + 펄스, 말풍선 개선, 노이즈 최소화.
4. **안정성**  
   - Ready Probe, 스텝퍼/로그, 예외 핸들링 강화, 자동 복원.
5. **신규파일 업로드마다 품질 증가**  
   - prepared 스캔→HQ 인덱싱→`.ready`→릴리스/백업 자동화.
6. **회원가입/관리 편의성**  
   - 학생/관리자 권한 분리, 관리자 패널은 게이트 뒤.
7. **UI 업데이트·앱 코드 관리 용이**  
   - `ui/`, `services/`, `core/` 분리, 구획 관리, 어댑터 점진 제거.

---

## 2) 아키텍처 개요
```
app.py  (진입/조립)
 ├─ ui/ (Streamlit UI)
 │   ├─ header.py
 │   ├─ chat_panel.py
 │   ├─ diagnostic_panel.py
 │   └─ admin/
 │       ├─ index_panel.py
 │       ├─ scan_panel.py
 │       └─ indexed_list.py
 ├─ services/ (비즈니스 로직)
 │   ├─ index.py        # reindex(), restore_or_attach(), backup_zip_release()
 │   └─ prepared.py     # check_new_files(), list_files(), mark_consumed()
 ├─ core/
 │   ├─ persist.py      # effective_persist_dir()
 │   └─ index_probe.py  # probe_index_health()
 ├─ rag/     # index_build.py, search.py, label.py ...
 ├─ agents/  # responder.py, evaluator.py
 ├─ llm/     # providers.py, streaming.py
 └─ vision/  # ocr.py
```

---

## 3) 기능별 설계와 “왜 필요한가”
### 3.1 인덱싱 오케스트레이션 (관리자 전용)
- **왜**: 데이터 품질이 답변 품질을 좌우. 인덱싱 상태/산출물은 추적 가능해야 함.
- **무엇**: 스캔(변화 감지) → HQ 인덱싱 → `.ready` 생성 → ZIP/Release 업로드 → 로컬 백업.
- **어디에**: `services/index.py`(로직), `ui/admin/index_panel.py`(UI).
- **완료 기준**: `chunks.jsonl` > 0, `.ready` 존재, 상태칩 HIGH.

### 3.2 Ready Probe & 미니멀 헤더
- **왜**: 학생에게 과도한 관리자 정보 노출 금지. 단, 상태는 명확히.
- **무엇**: “준비완료/준비중/점검중” 상태칩 + 펄스 점, 툴팁 제거.
- **어디에**: `core/index_probe.py` + `ui/header.py`.

### 3.3 답변 품질(LLM+RAG)
- **왜**: 신뢰성과 학습효과를 위해.  
- **무엇**:
  - 상위 n(예: 12) 문서 → **재랭킹**(BM25/semantic) → **중복 제거** → **근거성 스코어**.
  - 생성 후 **자체 평가 루프** 1회: 근거 부족/과장 시 재생성(temperature↓).
  - 실패 시 “추가 자료 필요” 폴백.
- **어디에**: `agents/*`, `rag/search.py`, `rag/label.py`.

### 3.4 자동 복원 & 백업
- **왜**: 서버 재시작/배포 후에도 즉시 Ready 보장.
- **무엇**: `.ready` 없으면 Release ZIP 복원 → 상태칩 즉시 HIGH.
- **어디에**: `services/index.py::restore_or_attach()`.
- **업로드**: 인덱싱 후 ZIP → Release 업로드 + 로컬 백업.

### 3.5 관리자 게이트
- **왜**: 권한 분리/실수 방지. 학생 화면은 미니멀.
- **무엇**: 세션 `admin_mode` True일 때만 관리자 패널 렌더.
- **어디에**: `ui/admin/*.py`, `ui/header.py`(로그인/로그아웃).

---

## 4) 데이터 흐름 (요약)
1) **Prepared 스캔** → 신규 파일 존재 수 표시(숫자 유지).  
2) **HQ 인덱싱** → persist 디렉터리에 `chunks.jsonl` 작성.  
3) **.ready 생성** → 상태칩 HIGH, 학생 화면도 즉시 Ready.  
4) **ZIP/Release 업로드**(선택) + 로컬 백업.  
5) **앱 재시작 시 자동 복원** (`.ready` 없고 Release 있으면).

---

## 5) 상태·시각화 규칙
- 상태칩: **HIGH=준비완료**, **MID=준비중**, **LOW=점검중**.
- 스텝퍼: ①Persist 확정 ②HQ 인덱싱 ③Prepared 소비 ④요약 ⑤업로드/백업
- 로그: 최근 200줄, 시계열 갱신. 멈춘 듯 보일 경우 ETA 대신 **진짜 진행 이벤트**만 표시.

---

## 6) 시크릿/환경 변수
- `GH_TOKEN`(또는 `GITHUB_TOKEN`), `GH_OWNER/GH_REPO` **또는** `GITHUB_REPO`
- `ADMIN_PASSWORD`(또는 `APP_ADMIN_PASSWORD`, `MAIC_ADMIN_PASSWORD`)
- `MAIC_PERSIST`(우선), 없으면 기본 `~/.maic/persist`

---

## 7) 품질 기준
- CI: `ruff → mypy → pytest` 전부 통과.
- 린트: E701/E702/E402/F404/F401 위반 금지. 라인 100자.
- 타입: Public 함수는 타입힌트 필수, `ignore` 최소화.
- 문서: 변경 시 `docs/_gpt/CHANGELOG.md` 갱신.

---

## 8) 릴리스/백업 정책
- 인덱싱 성과물 ZIP(`index_<ts>.zip`) 생성 후 Release 업로드.
- 로컬 백업: `${persist}/backups/` 병행 보관.
- 복원 우선순위: **로컬**(있으면) > **릴리스**(없으면 받기).

---

## 9) 로드맵(단기 → 중기)
- **단기(1~2주)**: 폴더 구조 이관, 어댑터 배치, app.py 경량화, 관리자 패널 안정화.
- **단/중기(2~4주)**: 재랭킹/평가 루프 반영, 인덱스 모니터링 개선, 오류 텔레메트리.
- **중기(4~8주)**: 사용자 계정/권한 관리(간단), 멀티-인덱스/버전 아카이브.

---

## 10) 운영 가이드
- 대규모 변경 전: 사전 질문(승인) → 구획 전체 교체본 제공.
- 문서 정본은 `docs/_gpt/` 유지. 워크스페이스엔 포인터만.
- 레거시 경로는 어댑터 1줄 남기고 2~3 릴리스 후 제거.
