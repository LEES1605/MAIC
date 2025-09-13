# LEES AI Teacher — Master Plan (v2025-09-13)

> **목표**: “학생 친화적·일관된 영어학습 경험”을 위해 **SSOT(단일 진실 소스)** 중심의 모듈 구성과
> **품질 가드레일(러프·마이파이·UX 평가)**를 결합한 안정적 운영체계를 확립한다.

---

## 0) TL;DR

- **SSOT 아키텍처 확립**: Persist 경로, 인덱스 상태, 모드/출력형식을 각 코어 모듈에서 *단일로* 결정.  
  - Persist 경로: `effective_persist_dir()` / Session 공유: `share_persist_dir_to_session()`  → UI에서 경로 덮어쓰기 금지. fileciteturn0file6  
  - 인덱스 건강/준비: `probe_index_health()`, `is_brain_ready()`, `mark_ready()`  → CI/서비스/앱 공통. fileciteturn0file5  
  - 모드·출력·평가 관점: `src/core/modes.py`의 `MODES`/`enabled_modes()`/`find_mode_by_label()`을 **단일 출처**로 사용. fileciteturn0file1
- **준비자료(prepared) 파이프라인 표준화**: GDrive 드라이버와 prepared 어댑터(SSOT)를 분리해 동적 로딩.  
  - 목록/다운로드: `src/integrations/gdrive.py` (동적 import, REST 대체, 서비스계정/ADC 지원). fileciteturn0file7  
  - 변화검출/소비: `src/drive/prepared.py`(check/mark API, seen 관리). fileciteturn0file2
- **대화 UX**: 피티쌤(주답변) → 미나쌤(평가) **스트리밍** 흐름, 모드 라디오 **[15B]**, 채팅 패널 **[16]**, 본문 렌더 **[17]**로 구성. fileciteturn0file8  
- **품질 가드레일**:  
  - `ruff check . --fix`(E501≤100, E701, E731 등), `mypy .` (unused‑ignore 금지·alias 재정의 금지)  
  - 평가(미나쌤) **형식 체크 배지/총평**(다음 UX 2탄) + 소스 라벨 **화이트리스트**(`sanitize_source_label`). fileciteturn0file0

---

## 1) 현재 아키텍처(SSOT) 베이스라인

### 1.1 Persist/Index SSOT
- **경로 결정**: `src/core/persist.py` — `effective_persist_dir()`, `share_persist_dir_to_session()`  
  - 우선순위: 세션스탬프 → `MAIC_PERSIST` → `MAIC_PERSIST_DIR`(레거시) → 인덱서 상수 → 기본 `~/.maic/persist`  
  - *부작용 없이* Path만 반환(디렉터리 생성/수정 없음). fileciteturn0file6
- **인덱스 상태**: `src/core/index_probe.py` — `probe_index_health()`, `is_brain_ready()`, `mark_ready()`, `get_brain_status()`  
  - `.ready`와 `chunks.jsonl` 크기 및 JSON 샘플 파싱으로 경량 판정. UI/CI 공용. fileciteturn0file5

### 1.2 학습 모드 SSOT
- **모드 사양**: `src/core/modes.py`  
  - `ModeSpec(key,label,goal,output_shape,eval_focus,prompt_rules,enabled)`  
  - `enabled_modes()`(UI 노출 순서 보장), `find_mode_by_label()` (라벨→키 매핑). fileciteturn0file1
- **소스 라벨 가드**: `src/modes/types.py`  
  - `ALLOWED_SOURCE_LABELS`(화이트리스트), `sanitize_source_label()`(허용 외 → `[AI지식]`), `clamp_fragments()`(프롬프트 팽창 방지). fileciteturn0file0

### 1.3 Prepared 파이프라인
- **드라이브 목록/다운로드**: `src/integrations/gdrive.py` — 동적 import·REST 대체·서비스계정/ADC 지원. fileciteturn0file7
- **변화검출/소비 SSOT**: `src/drive/prepared.py` — `check_prepared_updates()`, `mark_prepared_consumed()` (seen 관리). fileciteturn0file2

### 1.4 앱 오케스트레이션(핵심 구획)
- **[10] 부팅 자동 복원**: 릴리스 `index_*.zip` 복원 → `.ready` 마킹/세션스탬프. (하위폴더 구조 대응 계획) fileciteturn0file8  
- **[13] 인덱싱 패널**: 6단계 스텝/로그/진행바·prepared 소비. fileciteturn0file8  
- **[15B] 모드 라디오**: SSOT 라벨/키 매핑, mypy 친화적 모듈 임포트 방식 권장. fileciteturn0file8  
- **[16] 채팅 패널**: 사용자→피티쌤(answer_stream)→미나쌤(evaluate_stream) 스트리밍. fileciteturn0file8  
- **[17] 본문 렌더**: 부팅 훅/오토플로우→패널들→폼 submit rerun. fileciteturn0file8

---

## 2) 답변 품질 사양(SSOT와 합의 규칙)

- **문법(Grammar)**: 이유문법/깨알문법 근거 기반 설명 → 예문 → 역예문(선택) → 한 줄 요약.  
  평가 관점: 정확도·근거 제시·간결성. (MODES["grammar"].output_shape/eval_focus) fileciteturn0file1
- **문장(Sentence)**: **괄호규칙 라벨**(S,V,O,C,M,Sub,Rel,ToInf,Ger,Part,Appo,Conj)로 구문 제시 → 해석 → 개선 제안.  
  평가 관점: 규칙 준수·분석 일관성·재현성. (MODES["sentence"]) fileciteturn0file1
- **지문(Passage)**: 핵심 요지 → 쉬운 예시/비유 → 주제 → 제목(→ 오답 포인트).  
  평가 관점: 평이화·정보 보존·집중도. (MODES["passage"]) fileciteturn0file1
- **소스 라벨 칩**: `[이유문법]/[문법서적]/[AI지식]`만 허용(현재). 차기 확장: `[수업자료]/[검색]`. fileciteturn0file0

---

## 3) 협업 규약(패치 교환 포맷 포함)

1. **한 번에 하나의 패치**가 원칙. 단, **강연결(동일 기능·검증공유)**이면 **숫자구획 연속**으로 묶어 제출 가능.  
2. **숫자구획 패치 포맷**(중략 없음):  
   - `# [NN] START: <title>` … **전체 교체 코드** … `# [NN] END`  
   - 기존 구획이 없을 시 **정확한 파일 경로 + FULL REPLACEMENT** 제공.
3. **게이트**: `ruff check . --fix` → `mypy .` → (있다면) 유닛/스모크.  
4. **브랜치 전략**: `feat/<scope>` or `fix/<scope>` → **PR 설명 템플릿**(배경/해결/리스크/테스트/롤백).
5. **시크릿/민감정보**: 콘솔/로그/에러메시지에 토큰·경로 노출 금지. (GITHUB/GDRIVE는 secrets/env만) fileciteturn0file7
6. **UI 숫자구획 명명**: `[10]=부팅`, `[13]=인덱싱`, `[15]=UI(스타일/모드)`, `[16]=채팅패널`, `[17]=본문` 고정. fileciteturn0file8

---

## 4) 시행착오 & 재발 방지(실패 패턴 카탈로그)

- **mypy: import alias 재정의/할당 혼용 금지**  
  - `from X import func as _find` + 지역 ` _find = None` → Incompatible import 에러.  
  - **해결**: 모듈 임포트(`import X as mod; mod.func(...)`)로 전환. ([15B] 적용 권장) fileciteturn0file8
- **mypy: unused‑ignore 금지**  
  - 타입 무시 주석은 **실제 필요**할 때만, 정확한 코드에 한정.
- **ruff E701**: one‑liner `try: ... except: ...` 금지 → 블록으로 작성. (이미 교정)  
- **ruff E731**: `lambda` 대입 금지 → `def`로 치환. (prepared 파서에서 교정) fileciteturn0file2
- **릴리스 ZIP 하위폴더**: `chunks.jsonl`이 루트가 아닐 수 있음 → 하위 매칭 폴더 자동 채택 필요. ([10] 개선안) fileciteturn0file8
- **rerun 폭주**: 직접 `st.rerun()` 난발 금지 → `_safe_rerun(tag, ttl)` 사용. ([07] 유틸) fileciteturn0file8

---

## 5) 로드맵(파동·Wave)

### ✅ Wave‑S (Stability — 현재 반영/진행)
- [15B] **mypy 안전화**: 모듈 임포트 방식(함수 alias 제거). fileciteturn0file8
- [10] **릴리스 복원 신뢰성**: ZIP 해제 + `.ready` 마킹(하위폴더 자동 채택은 2단계). fileciteturn0file8
- [13]/[13B] **관리자 패널**: 스텝/로그/스캔·소비(check/mark) 안정화. fileciteturn0file8
- [16]/[17] **대화 스트리밍**: 피티쌤→미나쌤 흐름, 소스칩 화이트리스트 가드. fileciteturn0file8

### ▶ Wave‑Q (Quality UX 2탄 — 다음)
- **evaluator 업그레이드**: 출력 고정형식 `[형식 체크]→[피드백]→[한 줄 총평]` + **괄호규칙 검증**.  
- **배지/총평 UI**: [16]에서 평가 텍스트를 파싱해 **OK/WARN/FAIL** 배지와 총평을 하단에 표시.  
- **소스 라벨 확장**: `ALLOWED_SOURCE_LABELS`에 `[수업자료]`, `[검색]` 추가 + [16] 임포트 우선순위 `src.modes.types → modes.types → 폴백`. fileciteturn0file0

### ◇ Wave‑R (Release/Backup)
- **Private 에셋 다운로드**: `uploads.github.com` 업로드/다운로드 API **토큰 인증** 경로 정식화. ([10] 보강) fileciteturn0file8
- **증분 인덱싱**: prepared 변화만 반영하는 경로(추가 SSOT API: last_scan_ts).

### ◆ Wave‑S2 (Stability+)
- **rerun 가드 전면 적용**: [13B]/[17]의 직접 rerun → `_safe_rerun()` 통일. fileciteturn0file8
- **프롬프트 클램프**: `clamp_fragments()` 적용 지점 통일(프롬프트 주입 방지). fileciteturn0file0

---

## 6) 수용 기준(Definition of Done)

- [ ] 러프/마이파이 **제로 에러** (`ruff check . --fix`, `mypy .`)  
- [ ] **학생 플로우**: 질문→피티쌤 스트리밍 답변→미나쌤 평가 스트리밍이 3회 이상 정상 동작  
- [ ] **관리자 플로우**: prepared 스캔→인덱싱→요약 표시→(선택) ZIP 업로드  
- [ ] **릴리스 복원**: 깡통 persist에서 [10] 동작으로 `.ready`+`chunks.jsonl` 확보  
- [ ] **로그/보안**: 토큰/시크릿이 UI/로그에 노출되지 않음(점검)

---

## 7) 엔지니어링 표준

- **코딩 스타일**: 100자 줄폭, 의미있는 변수·함수명, 예외는 구체적 처리(빈 except 금지).  
- **타이핑**: `Optional`, `Dict[str, Any]` 명시, 동적 임포트는 모듈 별칭 방식으로 **이름 재정의 금지**.  
- **오류 처리**: `_errlog(msg, where, exc)` 사용(민감정보 금지). fileciteturn0file8  
- **의존 최소화**: Streamlit 없는 환경 고려(모듈 최상단 방어적 import). fileciteturn0file8

---

## 8) 테스트/운영 체크리스트

**로컬/CI 공통**
```bash
ruff check . --fix
mypy .
python -m pytest -q   # (있다면)
```

**핸드 스모크**
1) 깨끗한 persist에서 앱 부팅 → [10] 자동복원 확인. fileciteturn0file8  
2) 관리자 모드: [13] 인덱싱(6스텝) → `.ready` 확인. fileciteturn0file8  
3) 질의: 문법/문장/지문 모드 각각 1개 → 스트리밍/칩/평가 흐름 확인. fileciteturn0file8

---

## 9) 백로그 (우선순위 상→하)
- [Q] 평가 배지/총평 UI + evaluator 출력 고정.  
- [S] 릴리스 ZIP 하위폴더 자동 채택 보강, Private 에셋 토큰 다운로드. fileciteturn0file8  
- [Q] 소스 라벨 확장([수업자료]/[검색]) 및 칩 생성기 강화. fileciteturn0file0  
- [S] `_safe_rerun()` 전면 적용(직접 rerun 제거). fileciteturn0file8  
- [Q] 모드별 프롬프트 클램프 적용. fileciteturn0file0  

---

## 10) 부록 A — 숫자구획 패치 템플릿

```
# [NN] START: <title> (FULL REPLACEMENT)
<교체할 코드 전체>  # 중략 없음
# [NN] END
```

**PR 템플릿**
- 배경/문제: …  
- 해결/접근: …  
- 리스크/롤백: …  
- 테스트: 러프/마이파이/스모크 결과 …  

---

## 11) 부록 B — 보안·시크릿

- GitHub: `GH_TOKEN` 또는 `GITHUB_TOKEN`, `GH_OWNER/REPO` 또는 `GITHUB_OWNER/REPO_NAME`  
- GDrive: `GDRIVE_PREPARED_FOLDER_ID`, 서비스계정 JSON 또는 ADC.  
- 노출 금지: 토큰/민감 경로/개인 데이터(로그/에러 포함). fileciteturn0file7

---

## 12) 변경 이력(요약)
- 모드/SSOT·prepared 어댑터·GDrive 드라이버·Persist/Index 코어 확립. fileciteturn0file1turn0file2turn0file7turn0file5turn0file6  
- 앱 오케스트레이션 UI 구획 정리 [10]/[13]/[15]/[16]/[17]. fileciteturn0file8  
- 러프(E701/E731/E501) 및 mypy(alias/unused‑ignore) 정착.

---

**Authoring**: 이 문서는 현재 HEAD 기준 소스코드에 근거해 작성되었으며,  
구체적인 라인/구획은 `app.py`/SSOT 모듈 주석의 구획 마커를 따른다. fileciteturn0file8
