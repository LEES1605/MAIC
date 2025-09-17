# MAIC — 인덱스 복원/릴리스 업로드/RAG 품질 전수점검 보고서 (2025-09-17)

본 문서는 최근 관측된 증상(복원 검증 실패, 자동 업로드 미반영, RAG 미활용, 테스트 중복)을 한 번에 진단하고, 단기/중기 우선순위 패치 계획을 제시합니다.  
본 보고서는 SSOT 원칙에 따라 다음 경로를 기준으로 보관됩니다: `docs/_gpt/_reports/`.

---

## 목차
- [요약(Executive Summary)](#요약executive-summary)
- [1. 최신 인덱스 복원 실패 원인](#1-최신-인덱스-복원-실패-원인)
- [2. 자동 ZIP 업로드 및 GitHub Releases 미반영 원인](#2-자동-zip-업로드-및-github-releases-미반영-원인)
- [3. 응답이 AI지식에만 의존하는 이유와 괄호 규칙 미적용](#3-응답이-ai지식에만-의존하는-이유와-괄호-규칙-미적용)
- [4. 테스트 진단: 중복/정비 대상](#4-테스트-진단-중복정비-대상)
- [5. 진척률 평가와 향후 우선순위](#5-진척률-평가와-향후-우선순위)
- [부록 A. 프롬프트/페르소나 SSOT 설계안(관리자 패널 → Drive → Releases → 런타임 로더)](#부록-a-프롬프트페르소나-ssot-설계안관리자-패널--drive--releases--런타임-로더)
- [부록 B. 바로 실행 가능한 패치 번들 제안](#부록-b-바로-실행-가능한-패치-번들-제안)
- [부록 C. 운영 확인 체크리스트](#부록-c-운영-확인-체크리스트)

---

## 요약(Executive Summary)

- **복원 검증 실패의 근본 원인**은 `.ready` 파일 **내용 불일치**입니다. 경로에 따라 `"ok"`와 `"ready"`가 혼재해 검증 로직과 어긋납니다.  
  → **대응**: `.ready` 내용 **단일화("ready")** + 검증기는 과도한 실패 방지를 위해 `"ok"`도 한시 허용.

- **자동 ZIP 업로드 미반영**은 **시크릿 누락** 또는 **API 오류**가 UI에 충분히 드러나지 않기 때문입니다.  
  → **대응**: 시크릿 미설정 **경고 표시 강화**, 실패 시 **명시적 st.error**와 **재시도 안내**.

- **응답이 AI지식에만 의존**하는 이유는, 검색한 근거 스니펫을 **LLM 프롬프트에 주입하지 않기 때문**입니다.  
  → **대응**: `search_hits` 상위 스니펫을 `context_fragments`로 **프롬프트 합성**에 포함.

- **괄호 규칙 미적용**은 모델 지시 준수 이슈가 커서, **프롬프트 강화**와 **후처리/검증 루프**가 필요합니다.

- **테스트 스위트**는 스모크와 일부 단위가 존재하나 **중복 범위**가 있어 리팩터링 여지.  
  → **대응**: 라벨 정책 테스트는 **단위 vs RAG 통합** 역할 분담, GDrive smoke는 사용 여부에 따라 유지 재검토.

- **진척률**: 기능 구현은 70~80%이나, 제품 수준 안정성은 50% 내외.  
  → **우선순위**: 0) `.ready` 통일, 1) 업로드 오류 가시화, 2) RAG 컨텍스트 주입, 3) 통합 테스트 강화.

---

## 1. 최신 인덱스 복원 실패 원인

### 관측
- 복원 후에도 배지는 준비중으로 남거나, 검증 버튼이 **"산출물/ready 상태가 불일치"** 를 표시.
- 최근 복원 결과 패널에 성공 로그가 남지 않음.

### 원인
- 코드 경로별로 `.ready`에 쓰는 내용이 **혼재**: `"ok"` vs `"ready"`.  
- 검증 로직은 기본 `"ready"`만 정답으로 보기 때문에 `"ok"`가 기록되면 **오탐** 발생.

### 해결 방안
1) `.ready` **표준을 "ready"로 고정**.  
2) 과거 산출물 호환을 위해 검증기는 `"ok"`도 **한시 허용**(점진 제거 계획 포함).  
3) 복원/인덱싱 성공 시 **헤더 배지 세션 갱신**을 명시 호출하여 즉시 READY 반영.

---

## 2. 자동 ZIP 업로드 및 GitHub Releases 미반영 원인

### 관측
- 인덱싱 후 자동 업로드 토글이 켜져 있어도 Releases에 자산이 보이지 않음.
- UI에는 명확한 오류 메시지가 없거나, 단계 표시에만 간략히 드러남.

### 원인
- **시크릿 미설정**(토큰 또는 저장소 정보) 시 업로드 단계가 **조용히 skip**.  
- GitHub API 오류(권한, 자산 중복 등) 시 **단계 fail 텍스트만** 남고 사용자 경고가 약함.

### 해결 방안
1) 업로드 전 **시크릿 프리체크**. 누락 시 **st.warning**으로 즉시 알림, 토글 자동 OFF.  
2) API 오류 코드를 **st.error**로 팝업, 자세한 응답은 expander 자동 전개.  
3) 422(자산 중복) 등은 **삭제 후 재업로드** 또는 파일명에 타임스탬프 부여.

---

## 3. 응답이 AI지식에만 의존하는 이유와 괄호 규칙 미적용

### 관측
- 출처 라벨은 대부분 `[AI지식]`. 문법/문장/지문 모드 구분은 화면상 있으나, 근거 인용이 없음.
- 문장 분석에서 괄호 규칙이 결과에 충분히 반영되지 않음.

### 원인
- RAG 검색 결과를 **LLM 프롬프트에 주입하지 않음**.  
- 괄호 규칙은 프롬프트에 안내되어 있으나, **모델 준수율** 부족.

### 해결 방안
1) `search_hits` 상위 N개 스니펫을 `context_fragments`로 전달해 **"자료 컨텍스트" 섹션**에 포함.  
2) 괄호 규칙을 **강조 문구**와 **형식 예시**로 재주입.  
3) 필요 시 간단한 **후처리 보정**(예: 품목 라벨 괄호 추가) 또는 **검증-재요청 루프** 도입.

---

## 4. 테스트 진단: 중복/정비 대상

- 라벨 정책 테스트가 **함수 단위 vs RAG 통합**으로 **유사 시나리오를 중복 검증**.  
  → 역할 분리 또는 하나의 **파라미터라이즈드 테스트**로 통합.  
- GDrive smoke는 현재 사용성에 따라 **유지/보류** 재평가.  
- `.ready` 표준 변경 시, 관련 테스트의 **기대값**도 `"ready"`로 동기화 필요.

---

## 5. 진척률 평가와 향후 우선순위

- **구현 진척**: 70~80% (주요 기능 골격 완성).  
- **제품 안정성**: 50% 내외 (복원/업로드 신뢰성과 RAG 효과 부족).  

### 우선순위 로드맵
1) **0단계**: `.ready="ready"` 단일화 + 검증기 `"ok"` 임시 허용.  
2) **1단계**: 업로드 시크릿 프리체크, 실패 가시화, 422 재시도.  
3) **2단계**: RAG 컨텍스트 주입, 출처 라벨과 실제 인용 일치.  
4) **3단계**: 통합 스모크(E2E) 추가, 테스트 중복 정리.  
5) **4단계**: 임베딩 검색 도입, UX/운영툴 확장.

---

## 부록 A. 프롬프트/페르소나 SSOT 설계안(관리자 패널 → Drive → Releases → 런타임 로더)

> 요청하신 내용을 안전·유지보수·Actions-only 원칙에 맞춰 정리했습니다.

### 한눈 요약
- 입력: 관리자 패널에서 자유형 텍스트 붙여넣기  
- 정규화: Gemini/GPT가 **스키마 기반 YAML**로 자동 정리 + 린트  
- 출판(SSOT):  
  - 1차 단일 진실 소스: **Google Drive `prepared/prompts.yaml`**  
  - 2차 배포/백업: **GitHub Releases**(불변 버전 + `latest` 포인터)  
- 로딩: 앱 기동/주기적 **ETag/해시 캐시**, 실패 시 이전본 자동 롤백  
- 런타임: 모드 라우팅 → 페르소나/가드레일/톤 적용 → RAG/라벨 일관 적용

### 아키텍처 개요

아래 개요는 "관리자 패널에서 붙여 넣은 프롬프트/페르소나"를 **정규화 → 출판(SSOT) → 앱 런타임 로딩**으로 이어 주고, 사용자의 질문은 **모드 라우팅 + RAG**를 거쳐 **출처 라벨 정책**과 함께 응답되도록 만드는 흐름을 설명합니다.

#### 1) 구성요소와 경계(Responsibilities)

- **Admin UI(관리자 패널)**  
  - 인풋 수집: 자유형 텍스트 프롬프트/페르소나  
  - 사전 검토: 라이브 미리보기, diff, 테스트-런  
  - 제출: 정규화 파이프라인 트리거
- **Normalizer(정규화 파이프라인)**  
  - 스키마화: LLM 보조로 YAML 스키마에 정리  
  - 린트/검증: 길이, 금칙어, PII, 필수 필드, JSON Schema  
  - 버전/서명: sha256, 시맨틱 태그, 체인지로그
- **Publishers(출판 채널, SSOT 원칙)**  
  - **Google Drive**: `prepared/prompts.yaml` (HEAD/실시간 반영)  
  - **GitHub Releases**: `prompts-vYYYYMMDD-###` 불변 아카이브 + `prompts-latest` 포인터
- **Runtime Loader(앱 런타임 로더)**  
  - ETag/sha256 비교로 변경 감지, 증분 다운로드  
  - 서명 검증 실패 시 이전 검증본 유지(롤백)  
  - 캐시: `prompts-cache.json` 등
- **Indexer(인덱서)**  
  - prepared 문서 스캔, HQ 청킹, 중복 제거, `chunks.jsonl`, `.ready`  
  - 백업 ZIP 생성, Releases 업로드(옵션)
- **Responder(응답 생성기)**  
  - **Mode Router**: grammar/sentence/passage 모드 분기  
  - **Prompt Composer**: 페르소나/가드레일/톤 + **RAG 컨텍스트** 합성  
  - **Labeling**: `[이유문법] / [문법서적] / [AI지식]` 라벨 결정
- **Observability(가시化)**  
  - 상태 배지(READY), 복원 기록, 업로드 로그, 오류 팝업

#### 2) 시스템 다이어그램 (Flow)

```mermaid
flowchart LR
    A[Admin UI\n붙여넣기+미리보기+테스트] --> B[Normalizer\n스키마화+린트+서명]
    B --> C1[(Drive: prepared/prompts.yaml)]
    B --> C2[(GitHub Releases\nprompts-vYYYYMMDD-###,\nprompts-latest)]
    C1 --> D[Runtime Loader\nETag/sha256, 캐시, 롤백]
    C2 --> D
    D --> E[Mode Router\n문법/문장/지문]
    E --> F[Prompt Composer\n페르소나+가드레일+톤\n+ RAG 컨텍스트]
    F --> G[(LLM Providers)]
    G --> H[Answer+Labels\n[이유문법|문법서적|AI지식]]
    subgraph RAG
      I[Indexer\n청킹/중복제거] --> J[(chunks.jsonl + .ready)]
      K[Searcher\nTF-IDF/임베딩] --> F
    end
    I --- D
    J --- D

[Admin UI] -> [Normalizer] -> [Drive HEAD / Releases]
                     |               |
                     v               v
               [Runtime Loader] <----
                     |
            [Mode Router -> Prompt Composer (+RAG)]
                     |
                    LLM
                     |
                [Answer + Labels]
| 단계  | 산출물                                   | 설명                                        |
| --- | ------------------------------------- | ----------------------------------------- |
| 정규화 | `prompts.yaml`, `checksum`, `version` | 스키마화된 프롬프트/페르소나, sha256, 시맨틱 태그           |
| 출판  | Drive HEAD, Releases 불변               | HEAD는 최신본, Releases는 버전 보관 and latest 포인터 |
| 인덱싱 | `chunks.jsonl`, `.ready`              | 검색용 청킹 결과와 준비 플래그(`ready`)                |
| 로더  | `prompts-cache.json`                  | ETag/sha256 비교 후 캐시 JSON                  |
| 백업  | `index_*.zip`                         | 인덱스 ZIP(옵션, Releases 업로드 가능)              |

sequenceDiagram
  participant U as User
  participant A as App (Runtime)
  participant M as Mode Router
  participant S as Searcher
  participant P as Prompt Composer
  participant L as LLM

  U->>A: 질문 입력
  A->>M: 모드 결정(grammar/sentence/passage)
  M->>S: 관련 스니펫 검색
  S-->>M: 상위 N개 스니펫
  M->>P: 페르소나/가드레일/톤 + 스니펫 전달
  P->>L: 합성 프롬프트(context_fragments 포함)
  L-->>A: 답변 초안
  A-->>U: 답변 + 출처 라벨

### 데이터 스키마(핵심)
- `version`, `checksum(sha256)`  
- `modes.{grammar|sentence|passage}`: `persona`, `system_instructions`, `guardrails`, `examples`, `citations_policy`, `routing_hints`  
- `routing`: 전역 모델 오버라이드, 폴백 순서  
- `assets`: 배포 위치 식별자  
- `policy_labels`: 라벨 정책

### 관리자 패널 필수 기능
- 붙여넣기 편집기 + 미리보기 + diff  
- 테스트-런 샌드박스  
- 품질검사(토큰 한도, 금칙어, PII, 필수 필드)  
- 체인지로그 기록, 승인→출판 원클릭, 되돌리기, 감사로그

### 정규화 파이프라인
- to-structure, de-dup & trim, guardrail injection, schema validate, sign & tag

### 배포(Drive + Releases, Actions-only)
- Drive: `prepared/prompts.yaml` HEAD  
- Releases: `prompts-vYYYYMMDD-###` 불변, `prompts-latest` 포인터  
- CI 검증: yamllint, JSON Schema, 금칙어, 길이 상한, 서명검증 통과 시 출판

### 앱 런타임 로더
- ETag/sha256 비교 후 증분 다운로드, 검증 실패 시 이전 검증본 유지  
- 핫 리로드(주기/수동), 오프라인 폴백

### 런타임 응답 흐름
1) 모드 결정 → 2) 시스템 프로ンプ팅 구성 → 3) RAG 스니펫 주입 → 4) 라벨 정책 적용  
5) 모델 라우팅 → 6) 안전 필터

### 보안/품질 리스크와 대응
- Prompt Injection, Secrets 노출, 한도 초과, 데이터 손상, 컴플라이언스에 대한 린트/서명/롤백/감사 대책

### 장애 시나리오 처리
- 정규화/배포/로딩 실패 각각에 대한 사용자 경고와 재시도, 롤백 전략

### 테스트 전략(액션스-온리)
- 스키마 유닛, 회귀, 성능, 혼합 실패 주입, E2E(PR 라벨 트리거 → Releases/Drive 동시 출판 → 앱 핫리로드)

### 다음 단계
1) 스키마 동결 → 2) 관리자 UX → 3) 정규화 체인 → 4) 출판 파이프라인 → 5) 런타임 로더 → 6) 모니터링/감사

---

## 부록 B. 바로 실행 가능한 패치 번들 제안

- **브랜치**: `fix/ready-standard-and-verify`  
- **PR 제목**: `fix: unify .ready='ready' + verify accepts ok (temporary)`  
- **내용**:
  1) 인덱싱/복원 성공 경로의 `.ready` 기록을 **"ready"로 통일**.  
  2) 검증 스크립트/버튼은 `"ready"|"ok"` **둘 다 허용**(추후 `"ok"` 제거 예정).  
  3) 복원/검증 버튼 클릭 시 **헤더 배지 세션 갱신**.  

- **브랜치**: `feat/rag-context-injection`  
- **PR 제목**: `feat: inject RAG snippets into LLM prompt (context_fragments)`  
- **내용**:
  1) `search_hits` 상위 N개 스니펫을 `context_fragments`로 합성.  
  2) 답변 하단에 사용한 스니펫 출처를 표시(선택).  
  3) 라벨과 실제 인용 불일치 시 경고 배지.

- **브랜치**: `ci/release-upload-guardrails`  
- **PR 제목**: `ci: precheck secrets + surface upload errors`  
- **내용**:
  1) 토큰/저장소 정보 프리체크, 누락 시 토글 OFF + st.warning.  
  2) 업로드 오류 코드를 st.error로 가시화, 422 재시도.

- **브랜치**: `test/e2e-index-qa-smoke`  
- **PR 제목**: `test: add e2e smoke (index -> query -> cite)`  
- **내용**:
  1) 작은 fixture로 인덱싱 → 질의 → 근거 포함 응답 확인.  
  2) 라벨 정책과 실제 인용의 일치 여부 검사.

---

## 부록 C. 운영 확인 체크리스트

- 복원 직후: `chunks.jsonl` 존재, `.ready` 내용 "ready", 헤더 배지 READY.  
- 관리자 패널 검증: 성공 메시지와 최근 기록 JSON에 `"result": "성공"`.  
- 자동 업로드: ZIP 업로드 단계가 OK, Releases 페이지에 자산 확인.  
- RAG 반영: 질문 시 하단에 근거 요약 또는 출처 배지와 일치하는 내용.  
- 테스트: E2E 스모크가 그린, 라벨 단위/통합 테스트 중복 제거 후도 그린.

---
