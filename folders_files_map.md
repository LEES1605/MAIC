루트

app.py — 메인 앱. 헤더([07]), 상태/진행선([06]), 관리자 패널 로더([11]), 채팅 스타일/버블/모드([12]), 채팅 패널([13])을 모두 포함.

prompts.yaml — 기본 프롬프트 템플릿(폴백 또는 샘플).

.streamlit/config.toml — 테마/페이지 설정.

requirements.txt, pyproject.toml, ruff.toml, mypy.ini — 패키지/정적분석 세팅.

PROJECT_STATUS.md — 프로젝트 상태 기록.

src/

config.py — 설정/경로 상수 바인딩(여러 모듈에서 import).

prompt_modes.py — Drive+로컬 캐시 기반 프롬프트 엔진(modes/system/user 조립, 안전치환).

rag_engine.py — RAG(문서 첨부/품질/백업) 오케스트레이터(드라이브 폴더 ID 탐색 등).

ui_components.py — 배지/리스트 등 UI 스니펫.

ui_admin.py — 관리자 로그인/상태 표시에 관한 UI 헬퍼.

ui_orchestrator.py — 진단/관리 화면 랜더러(오케스트라 실행, 오류 누적 등).

features/build_flow.py — 인덱스 빌드 플로우 정의.

features/drive_card.py — 드라이브 카드형 UI.

llm/providers.py — LLM 공급자 어댑터(OpenAI/Gemini 등, Fallback 호출).

rag/index_build.py — 문서 인덱스 빌더(Drive ↔ 로컬, 압축/해시/매니페스트).

rag/quality.py — 품질 측정/리포트.

backup/github_release.py — GitHub Release 백업/복원 유틸.

compat/config_bridge.py — 과거 버전 호환(경로 브릿지).

compat/llama.py — 호환용 래퍼.
