git mv PROJECT_STATUS.md PROJECT_STATUS.md
git grep -n "PROJECT_STATUS" || true          # 혹시 남은 오탈자 참조 검색
git commit -m "chore(docs): fix typo PROJECT_STATUS -> PROJECT_STATUS"


# Re-create PROJECT_STATUS.md and confirm it exists
from datetime import datetime
from textwrap import dedent
import os, json, pathlib

now = datetime.now().strftime("%Y-%m-%d %H:%M")

content = dedent(f"""
# PROJECT_STATUS.md — LEES AI Teacher
_Updated: {now} (Asia/Seoul)_

## 0) 실행 요약 (Executive Summary)
- **목표:** 학원 학생들이 24/7로 질문할 수 있는 **Streamlit 기반 Q&A 앱** 구축. (OpenAI/Gemini 듀얼, GitHub·Google Drive 연동)
- **현상태:** 무한 로딩 이슈 해결을 위해 **빠른 부팅(로컬 붙이기)** + **관리자 수동 '깊은 점검'** 구조로 안정화.  
  채팅 UI는 **말풍선 + 파스텔 하늘색 컨테이너** + **스트리밍**을 적용했고, **모드 버튼(어법/문장/지문)**은 미니멀 스타일로 동작.
- **프롬프트 단일 출처:** `prompts.yaml`을 **GitHub**에 두고, **GitHub → Fallback** 순으로 사용.
- **인덱스(지식베이스):** 신규/변경 감지는 Deep Check에서 수행. 변경 없음이면 **GitHub Release에서 자동 복구(로컬 attach)** 로 빠르게 준비.

---

## 1) 마스터 플랜 (Master Plan)
1. **기능 아키텍처**
   - UI: Streamlit (채팅형 인터페이스, 말풍선, Enter 제출)
   - LLM: **OpenAI + Gemini** (자동 fallback), 필요 시 이중 설명 지원
   - 프롬프트: `prompts.yaml` **단일 소스** (레포에 보관)
   - RAG: Google Drive `prepared` 폴더(읽기 전용) + 로컬 캐시(`~/.maic/persist`)
   - 백업: **GitHub Release**를 인덱스 백업/복구에 사용 (OAuth 장기 권한 이슈 회피)
   - 버전관리: GitHub (코드/프롬프트 분리 관리, PR 리뷰)
   - 학생들 회원가입을 통한 로그인 기능 지원
   - 회원관리(정보수정, 가입허용, 강제탈퇴) 기능 지원
2. **UX 원칙**
   - 학생 UI: **미니멀**·**즉시 반응**·**시각적 구분(질문=하늘색, 답변=흰색)**
   - 관리자 UI: 우상단 아이콘(⚙️) 최소화, 필요 시 패널 확장
   - 실패/지연 시: **부드러운 안내문** 및 **Fallback 응답** 제공
3. **운영/배포**
   - Streamlit Cloud/서버 배포
   - Health-check 통과 보장: 초기 프레임은 **네트워크 I/O 없이** 렌더
   - 비밀정보: `.streamlit/secrets.toml` 사용 (키/토큰/모드)

---

## 2) 협의 규약 (Working Agreements)
- **한 번에 한 단계(One step at a time).**
- **Plan → Agreement → Code.** 변경 의도/근거를 먼저 설명하고 합의 후 코드 요청
- **업로드 된 코드를 전수점검 후 
- **“코드 보여줄까요?”** 합의 확인 후 코드 제시.

- **전체 블록 교체 규칙.** 파일은 번호 블록 `# [01]START =============… # [01]END============`로 나누고, 변경 시 **해당 블록 전체** 교체.  
  3개 블록 이상 바뀌면 **파일 전체 재생성**.

- **Cause → Goal → Code → Test.** 수정 이유→목표→코드→테스트 순서 준수.
- **학생 톤:** 원장님이 직접 설명하는 **따뜻하고 친절한 한국어**.
- **프롬프트 단일 소스:** `prompts.yaml`(GitHub) 최우선. Fallback 문구는 **부드러운 안내** 포함.
- **Drive 쓰기 금지.** (OAuth 영속 이슈) — 인덱스 백업/복구는 **GitHub Release**만 사용.
- **UI 합의 사항:** 말풍선(오른쪽=학생/하늘색, 왼쪽=AI/흰색), 파스텔 하늘색 채팅 컨테이너, 모드 버튼은 **색상만 변화**(크기 불변·아이콘 제거).

---

## 3) 현재 구현 상태 (As-Is)
### 3.1 앱 구동/헬스체크
- **빠른 부팅:** `_quick_local_attach_only()` — 로컬 시그널(`.ready`, `chunks.jsonl`, `manifest.json`)만 확인 → 첫 화면 즉시 렌더.
- **깊은 점검:** `_run_deep_check_and_attach()` — 관리자 버튼으로 수동 실행.  
  - Drive 준비상태 점검(가능 시)  
  - **GitHub Releases 복구** 시도 → 로컬 붙이기  
  - `diff_with_manifest()`로 변경 통계 확인(added/changed/removed)
- **자동 시작 옵션:** `_auto_start_once()` — `AUTO_START_MODE in {"restore","on"}`일 때만 Release 복구 시도 (기본 off).

### 3.2 채팅 UI
- **말풍선/색상:** 질문=우측·하늘색, 답변=좌측·흰색. 채팅 컨테이너는 **파스텔 하늘색** 유지.
- **스트리밍:** “답변 준비중…” 말풍선을 좌측에 먼저 띄운 뒤 토큰 단위로 갱신.
- **모드 선택:** “어법/문장/지문” pill 라디오 — **선택 시 색만 바뀜**(크기 동일·아이콘 없음).

### 3.3 프롬프트 로딩
- 우선순위: **GitHub → Drive → Fallback**
  - GitHub: 레포/브랜치/경로는 `GH_REPO`, `GH_BRANCH`, `GH_PROMPTS_PATH`로 설정.
  - Drive: 보조 모듈(`src.prompt_modes.build_prompt`) 있으면 사용.
  - Fallback: 자료 연결이 없을 때 **안내 문구**가 선행된 간결 답변.

### 3.4 증거(근거) 사용 규칙
- **1차:** 학원 수업자료(텍스트/Markdown) — 파일명이 **‘이유문법’/‘깨알문법’**으로 시작하면 **최우선**.
- **2차:** 기존 문법서 **PDF 발췌** — 파일명이 **영어**로 시작하면 **보조 근거**.
- **3차:** 위 자료가 없을 때 **AI 자체지식**으로 간략 안내.

---

## 4) 최근 수정 요약 (What Changed)
- **무한 로딩 방지:** 초기 네트워크 I/O를 제거하고, **관리자 수동 ‘깊은 점검’** 버튼으로 분리.
- **LLM 시그니처 호환:** 인자 자동 탐지(`messages`/`prompt`/`user_prompt`/스트리밍 콜백).
- **UI 고정화:** 말풍선/배경/모드 버튼 스타일을 한 번만 주입하여 리런에도 유지.
- **DISABLE_BG:** 배경은 `secrets.toml`의 `DISABLE_BG="true"`로 제어(※ `config.toml`이 아님).

---

## 5) 파일/경로 규약
- **앱 엔트리:** `app.py` (번호 블록 구조 유지: `[01]..[END]`)
- **인덱스/RAG:** `src/rag/index_build.py`
- **오케스트레이터:** `src/ui_orchestrator.py`
- **관리자 패널:** `src/ui_admin.py`
- **LLM 프로바이더:** `src/llm/providers.py`
- **지속 디렉터리:** `~/.maic/persist` (인덱스·매니페스트·체크포인트)
- **프롬프트:** `prompts.yaml` (레포 루트 권장, `GH_PROMPTS_PATH`로 경로 재지정 가능)

---

## 6) 설정 가이드 (Config & Secrets)
### 6.1 `.streamlit/config.toml`
```toml
[server]
fileWatcherType = "none"
runOnSave = false

[logger]
level = "warning"

# LLM
OPENAI_API_KEY = "…"
GEMINI_API_KEY = "…"

# GitHub prompts
GH_TOKEN = "…"
GH_REPO  = "owner/repo"
GH_BRANCH = "main"
GH_PROMPTS_PATH = "prompts.yaml"

# App
APP_MODE = "student"          # or "admin"
APP_ADMIN_PASSWORD = "0000"
AUTO_START_MODE = "off"       # "restore" | "on" | "off"
DISABLE_BG = "false"          # "true"로 끄기

7) 운영 로직 (결정 트리)

앱 시작 → _quick_local_attach_only()

로컬 인덱스 있으면 READY로 붙임

없으면 관리자에게 깊은 점검 유도

관리자 · 깊은 점검 클릭 → _run_deep_check_and_attach()

Drive 점검(가능할 때) → GitHub Release 복구 → diff로 변경 감지

변경 있음: 재빌드 의사결정 표출, 변경 없음: READY

질문 입력

prompts.yaml GitHub → Drive → Fallback 순으로 생성 후 LLM 호출(스트리밍)

8) 앞으로 할 일 (Next Actions)

 프롬프트 에디터([10C]): 관리자 화면에서 모드별 텍스트 편집 → GitHub 업로드 안정화

 증거 주입 자동화: ‘이유문법/깨알문법’·영문 PDF를 자동 스니펫 추출해 EVIDENCE_*에 주입

 Deep Check UI: 변경 통계 카드 + “재빌드/유지” 버튼

 인덱스 빌더: 하위폴더 스캔·Markdown 우선, 증분 빌드(+체크포인트)

 오류 메시지 개선: 학생에게 친절 메시지, 관리자에게 상세 로그

 회귀 테스트: 말풍선/스트리밍/모드 UI 스냅샷 테스트

 릴리즈 플로우: GitHub Actions로 prompts.yaml 유효성 + 인덱스 산출물 업로드 자동화

9) 배포/릴리즈 체크리스트

 .streamlit/secrets.toml 채움(키/토큰/모드)

 AUTO_START_MODE="off"로 최초 부팅 확인 → 건강 체크 OK

 관리자 로그인 → “🔎 자료 자동 점검(깊은 검사)” 수행 → READY

 prompts.yaml GitHub 경로/브랜치 확인

 샘플 질문 3종 테스트(어법/문장/지문)

 Release 업로드(인덱스 산출물) 후 복구·부팅 재검증

10) 부록 — 문제해결 히스토리(요약)

무한 로딩: 초기에 네트워크 I/O → 빠른 부팅 + 수동 깊은 점검

LLM 인자 불일치: 인자 자동 탐지로 호환

UI 불안정: 스타일 1회 주입으로 리런 호환

배경 토글: DISABLE_BG는 secrets에서만 제어

11) 메모

프롬프트·인덱스 소스는 GitHub 단일 소스 지향. Drive는 읽기 전용 보조.

학생 경험을 우선하여 지연·에러 시에도 즉시 피드백 제공.
""").strip() + "\n"

out_path = "/mnt/data/PROJECT_STATUS.md"
pathlib.Path(out_path).write_text(content, encoding="utf-8")

print(out_path, "written:", os.path.exists(out_path))
