# MAIC Master Plan (SSOT)
Source-of-Truth: github://LEES1605/MAIC@main/docs/_gpt/MASTERPLAN.md
Version: 2025-09-14
Owner: @LEES1605
> **Scope**: 프로젝트 전체 구조 이해 · 기능별 모듈 분석 · 보안 취약점 식별 · 로드맵 수립 · 코드/테스트 최적화  
> **Owner**: @LEES1605  
> **SSOT**: `docs/_gpt/` (모든 문서 수정은 PR로 관리)

---

## 0. 목표와 원칙

- **핵심목표**
  1) 프로젝트 전체 구조 이해 및 문서화  
  2) 기능별 모듈 동작 원리 파악  
  3) 코드 품질/보안 취약점 식별 및 리팩토링 계획  
  4) 테스트 구조(특히 `tests/`) 정리 및 최적화(중복/불필요 제거)  
  5) 실행 가능한 **우선순위 기반 로드맵** 수립

- **개발 원칙**
  - 보안, 성능, 가독성, 모듈성, 견고성 우선
  - **SSOT 문서화 + PR 절차**로 변경 관리
  - CI 게이트(ruff, mypy, pytest) **그린 유지**
  - “한 번에 하나의 변경” + “전체 구획 단위 교체(START/END)” 규약 준수

---

## 1. 시스템 구조 및 기술 스택

> 실제 레포의 디렉터리 구조와 파일명은 이 섹션을 기준으로 **주기적 동기화**하세요.

```text
app.py                # 앱 진입점 (Streamlit UI 조립 및 서비스 호출)
src/
  ui/                 # UI 컴포넌트 (헤더/채팅/관리자패널 등)
  services/           # 비즈니스 로직(인덱싱, prepared 소비 등)
  core/               # SSOT 헬퍼(경로/persist/index 상태 probe 등)
  rag/                # RAG: 인덱스 빌드(HQ), 경량 검색(TF-IDF), 라벨 결정
  agents/             # 이중 에이전트(주답변/평가)
  llm/                # LLM Provider 래퍼(OpenAI/Gemini), 스트리밍
  vision/             # OCR 등 비전 유틸
tests/                # 스모크/유닛/통합 테스트
docs/_gpt/            # SSOT 문서(이 파일 포함)
Frontend/Runtime: Streamlit (Python)

LLM: OpenAI / Google (API 키는 환경변수·secrets로 관리)

RAG: 경량 TF-IDF(기본), HQ 인덱싱 파이프라인(청크/중복제거/메타)

Persist: ~/.maic/persist (예: chunks.jsonl, .ready), GitHub Releases 백업

CI: ruff + mypy + pytest (+ CodeQL/SBOM 권장)

2. 핵심 기능 및 모듈 설명
2.1 듀얼 에이전트 응답
responder: 1차 주답변 생성(스트리밍 지원)

evaluator: 2차 품질평가/교정(포맷·근거 확인)

출처 라벨: RAG 라벨링([이유문법]/[문법서적]/[AI지식])을 칩 형태로 표현

2.2 인덱싱 오케스트레이션(관리자 기능)
스캔: prepared 폴더의 신규 파일 유입 탐지(개수/목록)

HQ 인덱싱: 청킹·중복제거·메타 반영 → chunks.jsonl 생성

준비 완료 표시: .ready 파일 생성(상태 프로브에서 참조)

백업: 인덱스 ZIP 생성 후 GitHub Releases 업로드(복원용)

2.3 인덱스 상태 모니터링
부팅 시 .ready/파일 무결성 등 검사 → READY/MID/LOW 배지 표시

관리자 헤더에 상태/타임스탬프/간이 진단 제공

2.4 관리자 전용 모드
환경변수·secrets 기반 비밀번호 인증 → 세션 flag로 권한 제어

인덱싱/스캔/소스목록/로그 등 관리자 패널 UI 렌더링

2.5 다중 학습 모드(문법/문장/지문)
모드별 프롬프트/출력 포맷을 SSOT로 통일(섹션 순서 고정)

라우터가 모드→프롬프트 템플릿→LLM 호출 일관 처리

2.6 OCR 이미지 처리
이미지 업로드 → OCR 추출 → 질문 입력창에 자동 채움(실패시 안전 폴백)

2.7 인덱스 자동 복원
부팅 시 .ready 없으면 최신 Release ZIP 자동 복원(네트워크 실패 시 폴백)

3. 코드 품질 및 보안 분석 (요약)
3.1 구조/품질
UI vs 서비스 결합도: app.py 비대화 → src/ui·src/services로 분리 강화 필요

중복 구현: 인덱싱/상태판정/세션키 초기화 등 공통화(SSOT 함수로 집중)

예외 처리: 외부 의존 안전 가드(try-import, 기능 폴백) 유지·강화

성능: 대용량 대비 메모리 효율/비동기 인덱싱/캐시 검토(중기)

3.2 보안
관리자 비밀번호 인증(세션 기반) → 다계정/권한 분리 확장 여지

Secrets: 환경변수/Streamlit secrets로 안전 관리(로그 노출 금지)

정적 보안: CodeQL·SBOM CI 추가 권장

데이터 보호: 인덱스 ZIP 암호화/사설 저장소/보존정책(장기)

4. 테스트 전략 및 개선 계획
4.1 현황
스모크: import/실행 최소 보장

유닛: RAG 검색/라벨/평가 파서 등 핵심 로직

레거시 가드: 삭제 모듈 잔존 감시(일시적 테스트)

4.2 부족한 부분
통합 테스트 부재(파일→인덱싱→질의 흐름)

LLM/Streamlit 의존 구간에 모의객체 주입 부족

4.3 개선 로드맵
스모크 보강: App 부팅/환경 누락 친절 메시지 점검

유닛 확대: services/core 유틸(ready, persist, prepared 소비)

통합 테스트: 소형 예시 인덱싱→질의→라벨 확인(LLM stub)

(선택) E2E: 필요 구간만 최소화해 도입

5. 향후 개발 로드맵 (우선순위)
5.1 즉시(최우선)
pytest 스모크 2종 추가 + 기존 유닛 보강 → CI 안정성 상승

main 브랜치 보호 규칙(필수 상태 체크: ruff/mypy/pytest)

5.2 단기(1~2 스프린트)
pre-commit(ruff, mypy, black) 도입

의존성 잠금(pip-tools/uv)으로 재현성 확보

보안 CI: CodeQL + SBOM 추가

5.3 중기(3~6개월)
RAG 품질 고도화: 임베딩 검색 옵션, 청킹/메타 개선, 간이 리콜@K 지표

UI/UX: 진단 패널 상세·로그 다운로드/이슈 생성, 모바일 대화 UI 최적화

운영 도구: 인덱스/로그 관리 버튼, 세션 상태 리셋/내보내기

5.4 장기(6개월+)
컨테이너화/Docker·IaC로 배포 표준화

관측성: 구조화 로그/메트릭/트레이싱

데이터 거버넌스: 백업 암호화/보존주기/자동 청소

6. 작업 방식(협의 규약 체크리스트)
변경 전 대상 파일 최신본 요청 → 전수 검토

한 번에 하나의 변경

숫자 구획 [NN] START/END 전체 교체(중략 금지)

제출 순서: 원인 분석 → 수정 목표 → 구획 전체 코드 → 테스트 방법 → 검증 로그

Streamlit secrets 예시: 세 개의 작은따옴표 ('''~''')

Actions-only(로컬 명령 강요 금지) · CI 그린 유지

7. 운영 체크(요약)
인덱스 상태: .ready/chunks.jsonl/ZIP 동기화

릴리스: 인덱스 ZIP 백업·복원·버전 태깅

비상복구: 최신 Release 자동 복원 폴백 작동 확인

8. 부록(유지되는 SSOT 문서)
docs/_gpt/MASTERPLAN.md (본 문서)

docs/_gpt/CONVENTIONS.md (협의 규약/작성 규칙)

docs/_gpt/MAIC_refactor_report.md (리팩토링 리포트/변경 이력 요약)
