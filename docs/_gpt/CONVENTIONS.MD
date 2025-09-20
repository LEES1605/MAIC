# 협의규약 (CONVENTIONS)
**Source-of-Truth**: 이 문서는 MAIC의 개발/리뷰/릴리스 표준 규약입니다.
원칙: **보안 · 정확성 · 일관성 · 가독성 · 유지보수성**.  
모든 변경은 “숫자구획 전체 교체([NN] START/END)” 원칙을 따른다. :contentReference[oaicite:2]{index=2}

---

## 0) 목적
- 코드/문서/릴리스 프로세스의 품질과 속도를 동시에 확보한다.
- **SSOT(단일 진실 원천)** 을 통해 템플릿/코드/문서의 표기를 일치시킨다.
- CI 게이트로 **사전에 회귀를 차단**하고, 수동 절차를 최소화한다. :contentReference[oaicite:3]{index=3}

---

## 1) 공통 원칙
- **보안**: 토큰·시크릿·개인정보는 로그/에러/스크린샷 등에 절대 노출 금지.
- **정확성**: 기능·문서·코드 간 싱크 유지. 문서 변경은 커밋과 함께 반영.
- **일관성**: 폴더 구조·네이밍·숫자구획·코드 스타일을 끝까지 지킨다.
- **가독성**: 한 기능 = 한 책임(SRP). UI/서비스/코어 로직 분리. :contentReference[oaicite:4]{index=4}
- **운영 원칙**: 사용자 요청에 따라 **로컬 방식 안내는 하지 않는다**(CI/레포 반영 중심).

---

## 2) 패치 규칙 (매우 중요)
- **숫자구획 전체 교체**:  
  - 코드/스크립트/워크플로는 `# [NN] START: ...` ~ `# [NN] END: ...` 구획 단위로만 교체한다.  
  - **라인 부분 수정·중략 금지**. 구획 번호는 **파일별 1부터 연속 정수**로 증가. :contentReference[oaicite:5]{index=5}
- **스타일 게이트**: `ruff`/`mypy`/`pytest` 그린 유지. E501은 인접 리터럴 분할 등으로 해결.  
  - `except` 재-raise 시 **`raise ... from e`**(Ruff B904) 필수.  
- **명명/키 일관화**: 세션 키·환경변수·헬퍼 함수명 통일.  
- **“로컬 실행 지시” 금지**: 문서/PR에서는 CI·레포 반영만 기술한다.  
- **더 나은 방법 제안 의무**: 사용자가 요청한 방법보다 안전/효율적인 안이 있으면 반드시 제안한다. :contentReference[oaicite:6]{index=6}

---

## 3) 폴더/파일 규칙
- **소스 레이아웃**: `src/...` (임포트 기준은 **레포 루트**).  
- **테스트 레이아웃**: 최상위 `tests/` 단일 디렉터리.  
  - 파일명 오타·중첩 금지 (예: `test_modes_canon_config.py`가 표준, `...caon...`/`tests/tests/..` 금지).
- **문서/SSOT**: `docs/_gpt/` 아래에 모드/캐논/규약을 둔다(본 문서 포함). :contentReference[oaicite:7]{index=7}

---

## 4) SSOT(단일 진실 원천) — 모드 정규화 규칙
### 4.1 구성 파일
- `docs/_gpt/modes/_canon.yaml`: 모드별 **표준 섹션 순서(order)**, **필수(required)**, **동의어(synonyms)** 정의.
- `docs/_gpt/modes/_canon.schema.json`: `_canon.yaml`의 **JSON 스키마**(구조 잠금).
- `docs/_gpt/modes/*.yaml`: (선택) 모드별 템플릿(존재 시 SSOT로 우선, 없으면 내장값). :contentReference[oaicite:8]{index=8}

### 4.2 표준 섹션 정책
- **모든 모드에서 `근거/출처`는 필수(required)** 로 권장.  
  - Grammar: `["핵심 규칙", "근거/출처", "예문", "역예문(선택)", "한 줄 요약"]`  
  - Sentence: `["원문", "구조 분석(괄호 규칙)", "어휘·표현", "해석", "요약", "근거/출처"]`  
  - Passage: `["요지/주제", "쉬운 예시/비유", "제목", "오답 포인트(선택)", "근거/출처"]` :contentReference[oaicite:9]{index=9}

### 4.3 동의어 규칙(정규화 예시)
- `"핵심규칙"` → `"핵심 규칙"`  
- `"근거(국어↔영어)"` → `"근거/출처"`  
- `"핵심 요지"`/`"요지"` → `"요지/주제"`  
> 과거 내장 `ModeSpec`에 혼재돼 있던 비표준 표기 때문에 테스트가 불안정했던 전례가 있으므로, **동의어 매핑으로 자동 치환**하여 재발을 원천 차단한다. :contentReference[oaicite:10]{index=10}

### 4.4 로더/정규화
- `get_profile()`는 SSOT를 읽고 섹션을 **동의어 표준화 → 필수 보강 → 표준 순서 정렬**로 정규화한다(SSOT 부재 시 내장 표준으로 폴백).  
- Sentence 모드는 **“괄호 규칙 라벨 표준”** 섹션을 항상 포함(SSOT → 폴백). :contentReference[oaicite:11]{index=11}

---

## 5) CI 품질 게이트
### 5.1 캐논 검증(Canon Validate)
- 워크플로: `.github/workflows/canon-validate.yml`  
- 검사: `_canon.yaml` **스키마(jsonschema)** + **수동 규칙**(중복/빈 문자열/자기참조 금지, `근거/출처` 권고 필수).  
- 실패 시 머지 불가. SSOT 변경은 **문서/코드/테스트** 일관성 검증 후에만 통과. :contentReference[oaicite:12]{index=12}

### 5.2 커버리지 래칫(Coverage Gate)
- 워크플로: `.github/workflows/coverage.yml`  
- 스크립트: `tools/check_coverage.py`  
- 정책: **비감소 래칫** — `tools/coverage_baseline.txt`의 기준선 **이상**만 요구(최초 실행 시 자동 부트스트랩). (고정 % 실패 방지) :contentReference[oaicite:13]{index=13}

### 5.3 RAG 픽스처 회귀(RAG Fixture Regression)
- 워크플로: `.github/workflows/rag-fixture.yml`  
- 엔진 매트릭스: `hash` / `bm25` / `disabled` (순수 파이썬, 결정적).  
- 픽스처: `tests/fixtures/rag_fixture.jsonl` — 대표 질의가 **항상 동일 문서**를 1순위로 회수. :contentReference[oaicite:14]{index=14}

### 5.4 보안 스캔(Security)
- 워크플로: `.github/workflows/security.yml`  
- `pip-audit`: 파이썬 의존성 취약점 스캔.  
- `gitleaks`: 시크릿 스캔 (PR 스캔에는 `GITHUB_TOKEN` 필요).

---

## 6) 프롬프트/문서 자동화
- **문서 생성기**: `tools/ggenerate_mode_docs.py` → `docs/_gpt/_generated/MODES.md` 생성.  
  - CI에서 **레포 루트를 PYTHONPATH**에 추가해 `src/...` 임포트 안정화.  
  - 문장 모드의 **규칙 섹션**(괄호 규칙 라벨 표준)도 포함. :contentReference[oaicite:15]{index=15}
- **라우터 안전성**: 출력 스키마(섹션 순서 고정)를 **must_do/avoid보다 먼저** 출력해 섹션명 최초 등장 위치를 고정. (순서 테스트 안정화) :contentReference[oaicite:16]{index=16}

---

## 7) 릴리스 정책
- **CHANGELOG**: **Keep a Changelog** 형식. 모든 사용자 가시 변경을 기록.  
- **릴리스 컷**: `.github/workflows/release-cut.yml` — `[Unreleased]` 본문을 **새 버전 블록**으로 내리고 **태그/릴리스** 생성. (날짜/프리릴리스 옵션 지원) :contentReference[oaicite:17]{index=17}

---

## 8) PR/커밋 가이드(체크리스트)
- [ ] 숫자구획 전체 교체로 패치했는가? (START/END, 번호 연속) :contentReference[oaicite:18]{index=18}  
- [ ] ruff/mypy/pytest/게이트(CI) 그린인가? (E501/B904 등 해결)  
- [ ] SSOT(_canon.yaml/스키마)·문서·코드가 일관적인가?  
- [ ] 보안(시크릿/토큰/PII) 노출 위험이 없는가?  
- [ ] CHANGELOG에 사용자 가시 변경이 반영됐는가? :contentReference[oaicite:19]{index=19}

---

## 9) 부칙
- 본 규약은 **SSOT**로 관리한다. 예외는 반드시 문서화·승인 후 반영.  
- 본 문서와 충돌하는 관행/코드는 **본 문서를 우선**한다.
