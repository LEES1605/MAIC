Source-of-Truth: github://LEES1605/MAIC@<commitSHA>/docs/_gpt/MAIC_refactor_report.md
Version: 2025-09-07

MAIC 코드베이스 리팩토링 보고서
주요 기능 흐름과 코드 위치 (파일:함수/구획)
프로젝트의 핵심 기능들을 파악한 결과, 현재 코드베이스에서 각 기능은 아래와 같은 위치에 구현되어 있습니다:
채팅 인터페이스 (대화 흐름) – Streamlit 프런트엔드의 app.py 내 채팅 패널 함수(_render_chat_panel)에서 구현됩니다. 이 함수는 사용자의 질문을 받아 **두 단계의 에이전트 응답(피티쌤 → 미나쌤)**을 스트리밍 출력하며, 내부적으로 src.agents.responder.answer_stream(첫 번째 답변)과 src.agents.evaluator.evaluate_stream(두 번째 답변)을 호출합니다. 또한 이 과정에서 출처 라벨 결정을 위해 src.rag.label 모듈의 search_hits(TF-IDF 검색)와 decide_label 함수를 사용하여 답변에 [이유문법]/[문법책]/[AI지식] 등의 출처 칩을 붙입니다. 채팅 UI의 말풍선 스타일(CSS)은 app.py의 _inject_chat_styles_once 함수에서 정의되고, _emit_bubble 헬퍼를 통해 사용자(나) 말풍선과 AI 답변 말풍선이 HTML로 생성됩니다.
인덱싱 및 RAG – 지식파일 인덱싱 기능은 주로 src/rag/index_build.py 모듈에 구현되어 있으며, 관리자 모드에서 실행됩니다. 관리 패널 UI는 app.py의 인덱싱 패널 함수(_render_admin_index_panel)로 제공되며, “강제 재인덱싱(HQ)” 버튼 클릭 시 이 함수 내에서 src.rag.index_build.rebuild_index()를 호출하여 고품질(HQ) 인덱싱을 수행합니다. 해당 HQ 인덱싱 로직은 문단 단위 청킹, 중복 제거, .ready 신호파일 생성 등을 처리하고 있으며 src/rag/index_build.py에 자세히 정의되어 있습니다. 예를 들어 HQ 인덱싱은 MAIC_INDEX_MODE=HQ 환경변수에 따라 청크 크기와 오버랩 등을 조절하여 수행됩니다
GitHub
. 간단한 TF-IDF 기반 기본 인덱싱 및 검색 기능은 src/rag/search.py 모듈에 있으며, 이전 버전에서는 관리자 패널이 이 기본 인덱싱 함수를 사용했습니다. 현재는 HQ 인덱싱으로 통합되었고, 검색은 여전히 질문 시 search_hits()로 수행됩니다. 인덱싱 결과는 .maic/persist 경로 아래 chunks.jsonl로 저장되고 .ready 파일로 준비 완료 상태를 표시합니다.
지식 데이터 준비 및 스캔 – prepared 디렉토리에 저장된 학습 자료 파일들을 스캔하고 새로운 파일 유입 여부를 확인하는 기능이 있습니다. 이는 app.py의 새 파일 스캔 패널(_render_admin_prepared_scan_panel)에 구현되어 있습니다. 관리자 모드에서 “🔍 스캔 실행” 버튼을 누르면 prepared 모듈(또는 gdrive 통합 모듈)의 check_prepared_updates() 함수를 호출하여 인덱싱 없이 새로운 파일 개수를 확인합니다. 결과로 prepared 폴더의 총 파일 수와 신규 파일 수를 JSON으로 보여주고, 신규 파일 목록을 UI에 표시합니다. 이 패널은 실제 인덱싱을 수행하지 않고 변화 여부만 검사하며, 인덱싱 작업은 별도의 “강제 재인덱싱” 패널에서 이루어집니다.
인덱스 지속성과 상태 표시 – 인덱스 퍼시스턴스(지속 저장) 경로와 상태 관리는 app.py 및 관련 모듈에서 이루어집니다. app.py 최상단에는 _effective_persist_dir와 _persist_dir 함수가 있으며, 환경변수나 기본값을 기준으로 인덱스 저장 경로(~/.maic/persist)를 결정합니다. 또한 app.py에는 _mark_ready() (준비 완료 신호파일 생성)와 _is_brain_ready() (인덱스 준비 여부 체크) 함수가 있어, .ready 파일과 chunks.jsonl 존재 여부를 확인해 인덱스 상태 배지를 결정합니다. 이 상태는 스트림릿 세션 상태 brain_status_code/msg로 관리되며, 헤더에 아이콘 배지(예: 🟩 READY 또는 🟥 MISSING)와 함께 표시됩니다. 상태 표시는 오케스트레이터 패널에서 간략하게 제공되는데, app.py의 _render_index_orchestrator_header 함수는 Persist 경로와 READY/MISSING 배지를 보여주고 관리자 패널을 이용하라는 안내를 출력합니다. 추가로 _render_ready_probe 함수는 .chunks.jsonl 파일의 크기와 JSON 유효성 등을 검사하여 Ready 진단 Pill(🟢/🟡/🔴)을 시각화합니다.
관리자 기능 – 관리자 모드 전환 및 패널 접근은 app.py 헤더 섹션에서 구현됩니다. 사용자 상단 헤더에서 “🔐 관리자” 버튼을 누르면 비밀번호 입력 폼이 표시되고, 미리 환경변수/시크릿에 설정된 관리자 비밀번호와 일치하면 st.session_state["admin_mode"] = True로 설정됩니다. 로그인 성공 시 헤더에 “로그아웃” 버튼이 나타나며, 세션을 초기화합니다. 관리자 모드가 활성화되면 _is_admin_view()가 True를 반환하여, 관리자용 UI 패널들이 본문에 렌더링됩니다. 여기에는 앞서 언급한 인덱싱 패널, 새 파일 스캔 패널, 인덱싱된 소스 목록 패널(_render_admin_indexed_sources_panel) 등이 포함됩니다. 인덱싱된 소스 목록 패널은 현재 chunks.jsonl 내용을 집계하여 어떤 문서들이 인덱싱되었는지 표로 보여주는 읽기 전용 대시보드입니다. 관리자 기능 전반에 걸쳐 세션 상태와 .ready 파일 등이 연동되어, 학생 모드(일반 사용자 모드)와 관리자 모드 간에 인덱스 준비 상태 등이 공유되도록 합니다.
OCR 이미지 질문 – 업로드된 이미지 -> OCR -> 질문 자동입력 흐름도 지원됩니다. src/vision/ocr.py 모듈에 OCR 기능이 구현되어 있으며, Pillow 및 pytesseract가 설치된 경우 이미지를 텍스트로 추출합니다. Streamlit 앱에서 사용자가 이미지를 업로드하면 (예: 드래그&드롭 등) 해당 텍스트를 채팅 입력창에 자동 주입하도록 연결되어 있습니다. 현재 app.py에서는 _quick_local_attach_only()라는 훅을 통해 로컬 첨부된 입력을 감지하는 코드가 있으며, OCR 결과를 세션 상태 (예: inpane_q)에 넣어 다음 재렌더 시 질문으로 처리하는 것으로 추정됩니다. 이 흐름은 선택적 의존성으로 구현되어 있어, OCR 라이브러리가 없으면 빈 문자열만 반환하고 앱은 오류 대신 UI에 안내 메시지를 띄워줍니다.
위와 같이 주요 기능들이 분산되어 있지만, 현재는 대부분의 UI 로직이 app.py 한 파일에 밀집되어 있고, 핵심 로직 역시 일부 UI 함수 내부에 포함되어 있습니다. 이러한 구조를 다음 섹션에서 역할별로 분리하고 재구성하는 방안을 제시합니다.
코드 역할별 모듈 분리 가능성 및 중복 분석
현재 코드베이스를 기능별로 살펴보면 UI, 인덱싱 로직, 퍼시스턴스 관리, 채팅(LLM 호출) 로직, 관리자 도구 등이 혼재되어 있습니다. 유지보수를 쉽게 하기 위해 다음과 같이 역할별 모듈 분리를 분석했습니다:
UI 컴포넌트 vs. 비즈니스 로직 분리: app.py는 Streamlit UI 구성과 함께 인덱싱 수행, 상태관리 등의 로직을 동시에 다루고 있어 복잡도가 높습니다. 이를 UI 레이어와 서비스/로직 레이어로 나누는 것이 좋습니다. 예를 들어, 현재 관리자 인덱싱 패널은 UI 폼과 버튼을 구성한 다음 바로 _idx.rebuild_index()를 호출하고 .ready 파일을 쓰는 작업까지 합니다. 이러한 인덱싱 동작은 UI에서 분리하여 별도의 인덱싱 서비스 모듈에서 처리하고, UI 코드에서는 그 서비스를 호출하는 형태로 단순화할 수 있습니다. 마찬가지로 오케스트레이터 패널과 관리자 패널이 모두 인덱싱/복원 기능을 다루는데, 현재 코드상 두 패널의 구현이 일부 중복되어 있었습니다. UI는 둘로 나뉘어 있을지라도 내부 로직은 단일 함수만 호출하도록 일원화하는 것이 바람직합니다.
중복 기능 및 정의의 통합: 전체 코드를 검토한 결과, 동일하거나 유사한 기능이 여러 곳에 중복 구현되어 있는 사례가 발견되었습니다. 예를 들면:
인덱싱 함수 중복: src/rag/search.py의 build_index(단순 인덱싱)와 src/rag/index_build.py의 rebuild_index(HQ 인덱싱)가 분리되어 있는데, 관리자 패널과 Orchestrator가 각기 다른 것을 호출하면서 결과 반영에 불일치가 발생했었습니다. 최신 코드에서는 관리자 패널이 HQ 인덱싱으로 통합되었지만, 근본적으로 한 곳에서만 인덱싱 로직을 유지하고 다른 곳에서는 이를 호출만 하도록 구조를 잡아야 합니다. 이를 위해 단일 서비스 함수 (services/index.py의 reindex() 등)로 인덱싱 동작을 묶어 제공하면, 여러 UI 패널에서 이 함수를 재사용함으로써 논리 중복을 없앨 수 있습니다.
인덱스 상태 판정 중복: 인덱스 준비여부(.ready 존재 및 chunks 크기 확인) 로직이 app.py의 _is_brain_ready()와 src/rag/index_status.py (또는 services/index.py) 등에 중복될 수 있습니다. 실제로 app.py와 index_build.py 양쪽에 PERSIST_DIR 및 .ready 처리 코드가 중복 정의되어 있었는데, 한 곳에서만 정의하고 import하여 쓰도록 일원화하는 것이 권장됩니다. 새로 도입할 서비스 모듈에서 **SSOT(Single Source of Truth)**로 인덱스 상태를 판정하는 함수(_local_ready 등)를 제공하고
GitHub
, UI에서는 가능하면 이 함수를 통해 상태를 조회하도록 하면 중복이 제거됩니다.
prepared 스캔 및 소비 로직: prepared 폴더의 새 파일 검사와 소비(표시 후 mark_prepared_consumed 호출) 기능이 스캔 패널과 인덱싱 패널 양쪽에 매우 유사한 형태로 구현되어 있습니다. 두 곳 모두 check_prepared_updates()와 mark_prepared_consumed()를 호출하는데, 현재는 각각 내부에 _load_prepared_api() 헬퍼를 중복 정의하고 있습니다. 이 또한 공용 유틸 함수로 분리하거나, prepared 전용 서비스/헬퍼 모듈로 추출하여 하나의 함수로 구현해두고 두 UI에서 사용하도록 개선할 수 있습니다.
기타 중복/불필요 코드: 코드 리뷰 결과, 사용되지 않는 import나 변수, 여러 곳에서 반복 설정되는 세션 키 등이 발견되었습니다. 예컨대 app.py와 index_build.py 모두에서 PERSIST_DIR 경로를 계산하고 기본값을 설정하는 로직이 따로 있고, st.session_state.setdefault("admin_mode", False)를 여러 위치에서 호출하는 등 불필요 반복이 있습니다. 이러한 부분은 각각 단일한 초기화 모듈 또는 함수로 묶어서 한 번만 실행되도록 정리하는 것이 좋습니다. (예: 여러 세션 상태 기본값 설정을 _ensure_session_keys() 같은 함수로 모으기). 불필요한 import/변수도 제거하여 린터 오류를 없애고 코드 가독성을 높일 수 있습니다.
以上の分析を踏まえ、次のセクションでは、上述した役割別にファイル/モジュールを再編成する具体的な提案を示します.
폴더 및 모듈 구조 재구성 제안
위 기능별 분리 방안을 실제 프로젝트 구조로 적용하기 위해, 디렉토리 구조 개편안을 다음과 같이 제안합니다. 새로운 구조에서는 기능별로 폴더를 구분하고, 관련 코드와 함수들을 해당 모듈로 이동시킵니다:
MAIC/
├── app.py                # 메인 실행 스크립트 (최소한의 UI 조립만 담당)
├── src/
│   ├── ui/               # **UI 레이어 모듈 모음**
│   │   ├── header.py         # 헤더 및 로그인/로그아웃 UI
│   │   ├── chat_panel.py     # 채팅 패널 UI 및 말풍선 렌더링
│   │   ├── admin_panel.py    # 관리자 패널 UI (스캔, 인덱싱, 소스목록)
│   │   └── diagnostic_panel.py  # 오케스트레이터/진단 UI (상태 표시 등)
│   ├── services/         # **서비스 레이어 모듈 모음** (UI에 호출되는 비즈니스 로직)
│   │   ├── index.py          # 인덱스 관리 서비스 (인덱싱, 복원, 상태판정 등)
│   │   ├── prepared.py       # (선택) prepared 폴더 관리 서비스 (파일 스캔, 소비)
│   │   └── ... (기타 서비스 모듈: 필요시 추가)
│   ├── agents/           # (기존) 에이전트 로직 (responder.py, evaluator.py)
│   ├── llm/              # (기존) LLM API 연동 (providers.py, streaming.py 등)
│   ├── rag/              # (기존) RAG 인덱싱/검색 (search.py, label.py, index_build.py 등)
│   ├── vision/           # (기존) 비전 처리 (ocr.py 등)
│   └── ... 기타 모듈 ...
설계 의도:
app.py는 최소한의 책임만 갖도록 합니다. 구체적으로, 페이지 초기 설정과 UI 구성 함수 호출 순서만 포함하고, 세부 로직은 모두 src/ 하위 모듈에서 가져옵니다. 이로써 app.py의 길이를 대폭 줄이고 가독성을 높입니다.
src/ui/ 패키지는 모든 Streamlit UI 구성을 담당합니다. 과거 app.py에 흩어져 있던 헤더, 채팅, 관리자, 진단 패널 함수를 각각 별도 모듈로 분리함으로써, UI 코드를 한 곳에서 관리할 수 있습니다. 예컨대 ui/chat_panel.py에는 _inject_chat_styles_once, _emit_bubble, _render_chat_panel 함수가 옮겨지고, ui/admin_panel.py에는 _render_admin_prepared_scan_panel, _render_admin_index_panel, _render_admin_indexed_sources_panel 등이 이동합니다. 이들 모듈은 모두 Streamlit을 import하여 사용하므로 UI 컨텍스트에 종속적이지만, app.py로부터 분리되어 파일별로 기능이 명확해집니다.
src/services/ 패키지는 비즈니스 로직 서비스 계층으로, UI와 핵심 로직을 연결하는 역할을 합니다. 예를 들어, services/index.py는 인덱싱/복원 관련 공통 함수를 제공하여 UI에서 이를 호출하도록 합니다. 관리자 패널의 “재인덱싱” 버튼이나 자동 복원 기능은 이제 services.index.reindex() 함수를 호출하면 되며, 내부에서 src/rag/index_build.rebuild_index를 실행하고 결과를 확인하는 식입니다
GitHub
GitHub
. 이렇게 하면 UI 코드에는 if submit_reindex: services.index.reindex() 정도로 단순화되고, 인덱싱 완료 후 상태 업데이트도 services.index._set_brain_status("READY", "...") 등을 통해 일관되게 처리할 수 있습니다
GitHub
. 또한 services/index.py에 _local_ready, _ensure_ready_signal 등의 유틸리티를 구현하여 .ready 파일 생성 및 체크 로직을 한 곳에서 관리하면, app.py나 UI 모듈에서 직접 파일을 만지는 대신 이 서비스 함수를 호출하는 구조로 개선됩니다
GitHub
GitHub
.
기존 도메인별 모듈 유지: src/agents, src/llm, src/rag, src/vision 등은 기존에 잘 분리되어 있으므로 그대로 유지합니다. 이들은 각각 에이전트 응답 생성, LLM API 연동, RAG 인덱싱/검색, OCR 등 **핵심 로직(코어 로직)**을 담당하며, UI나 서비스 계층과는 명확히 분리되어 있습니다. 따라서 상호 의존성을 최소화하면서, UI → 서비스 → 코어 로직의 계층을 형성하게 됩니다. (예: UI가 서비스 함수를 호출하면, 서비스가 다시 rag나 agents 모듈의 함수를 호출하는 구조)
환경설정/공통 상수의 일원화: PERSIST_DIR와 같은 설정값 정의는 src/config.py (또는 services/index.py 내부)에서 한 번만 설정하고, 다른 모듈들이 이를 참조하도록 합니다. 예컨대 index_build.py와 app.py 양쪽에 있었던 PERSIST_DIR 정의는 제거하고, src/config.py에 PERSIST_DIR = Path.home()/".maic"/"persist"로 명시한 뒤 index_build.py에서 이를 import해서 사용하도록 수정합니다. 이밖에 사용되는 환경변수 키나 기본값들도 config 모듈에 모아두면, 추후 경로 변경이나 설정 변경 시 한 곳만 수정해 반영할 수 있어 유지보수가 수월해집니다.
파일/클래스 명명: 모듈 및 함수 이름은 기존 컨벤션을 따르되, 더 명확하게 조정합니다. 예를 들어 ui/admin_panel.py 내 함수들은 _render_admin_index_panel 등 기존 이름을 유지하거나, 필요한 경우 render_admin_index_panel처럼 prefix를 정리할 수 있습니다. 서비스 계층 함수들은 UI에 노출되는 동작을 의도로 하기 때문에 reindex(), restore_or_attach(), attach_local() 등 현재 services/index.py에 초안이 있는 이름을 그대로 활용합니다
GitHub
GitHub
. 이들은 테스트에서도 쉽게 호출해볼 수 있는 단순 함수로 만들어, 스트림릿 세션이 없어도 동작하거나 최소한 예외 없이 무시되도록 (try: import streamlit 블록) 구현합니다
GitHub
.
위 구조 개편을 통해 **관심사의 분리(Separation of Concerns)**가 이루어져, 각 폴더의 목적이 명확해집니다. UI 개발자는 src/ui/만 보면 되고, 인덱싱 로직 개선은 src/services/index.py와 src/rag/index_build.py를 보면 되는 식으로 모듈 책임이 구획화됩니다.
거대화된 app.py의 분할 및 재배치 계획
현재 app.py 파일은 약 1800여 줄에 달하며, 숫자 구획 [01]부터 [18]까지 여러 기능이 연속 배치되어 있습니다. 이를 기능 단위로 분할하고, 가볍게 만드는 구체적인 방안은 다음과 같습니다:
스트림릿 초기화 및 환경설정 분리: app.py 상단의 임포트 및 환경 부트스트랩 코드([01]~[04] 구획)와 페이지 설정 부분을 그대로 유지하거나 src/config로 이전합니다. _bootstrap_env() 함수와 st.set_page_config 호출부는 가능하면 별도 모듈로 분리해 app.py에서 호출만 하도록 합니다. 이렇게 하면 앱 실행시 필요한 환경변수 승격과 페이지 타이틀/레이아웃 설정을 깔끔하게 한 블록으로 묶을 수 있습니다.
UI 렌더링 분리: app.py에서 UI 그리는 부분([08]~[16] 구획)을 모두 src/ui/ 모듈 호출로 대체합니다. 예를 들어, app.py의 본문 렌더 함수 _render_body() 내 코드를 다음과 같이 단순화합니다:
import streamlit as st
from src.ui import header, diagnostic_panel, admin_panel, chat_panel

def _render_body():
    header.render_header()             # 상단 헤더 및 로그인/로그아웃
    diagnostic_panel.render_header()   # 진단 도구 헤더 (상태 배지 표시)
    diagnostic_panel.render_ready_probe()  # Ready 상태 진단 Pill

    if admin_panel.is_admin():         # 세션의 admin_mode 검사
        admin_panel.render_index_panels()  # 관리 패널 (스캔 + 인덱싱 + 소스 목록)

    chat_panel.render_chat()           # 채팅 패널 출력 (질문 및 답변 스트리밍)
    chat_panel.render_input_form()     # 질문 입력 폼
위 코드처럼, 각 부분이 역할별 모듈의 함수로 대체됩니다. 실제 구현에서는 header.render_header() 등이 내부에서 Streamlit st 호출을 수행하며 기존 _header() 함수의 내용을 가지게 됩니다. Chat 패널의 경우 _render_chat_panel()의 내용을 chat_panel.render_chat()로 이동하고, 질문 입력 폼 부분(현재 _render_body에 직접 있던)을 chat_panel.render_input_form() 등으로 떼어냅니다. 이런 분할로 app.py에서는 UI 구성의 호출 순서만 제어하고, 상세 구현은 보이지 않게 되어 가독성이 향상됩니다.
관리자 패널 구성 재배치: 기존 app.py에서는 관리자 모드일 때 여러 함수를 순서대로 호출하여 패널들을 그렸습니다. 이를 admin_panel.render_index_panels() 하나의 함수로 통합합니다. 이 함수 내부에서 다시 render_prepared_scan_panel(), render_reindex_panel(), render_indexed_sources_panel() 등을 순서대로 호출하여 하위 섹션들을 그립니다. 필요하면 화면 배치를 위해 st.expander나 st.container 등을 사용해 섹션을 구분할 수 있습니다. 이렇게 하면 app.py에는 관리자 모드 패널 호출이 한 줄로 축약되고, 추후 관리자용 UI 변경도 해당 모듈만 수정하면 됩니다.
공통 유틸리티의 모듈화: app.py에 정의된 여러 헬퍼 함수들도 적절한 곳으로 이동시킵니다. 예를 들어 _safe_rerun, _errlog 등 Streamlit 동작 보조나 로깅 함수들은 src/ui/utils.py 혹은 services/utils.py로 옮겨 일관되게 사용합니다. _effective_persist_dir, _mark_ready 등 Persist 경로와 파일 생성 관련 함수는 services/index.py로 이동하여, 서비스 계층에서 관리하도록 합니다
GitHub
. _is_admin_view는 admin_panel.is_admin()으로, _set_brain_status는 services.index._set_brain_status로 대체하는 식입니다. 단, 이러한 함수 이동 시 기존 호출부를 모두 따라 수정하고, import 경로도 변경해야 하는 점을 주의합니다. 이동 후에는 린터를 돌려 사용되지 않거나 중복 정의된 함수가 남지 않도록 정리합니다.
Streamlit 실행 진입점 유지: app.py 최하단의 if __name__ == "__main__": main() 부분은 그대로 두어 어플리케이션 시작 진입점으로 이용합니다. 다만 main 함수 내부는 st.session_state 초기화나 한 번만 실행할 부팅 훅 처리 후 _render_body()를 호출하는 수준으로 단순화합니다. 기존 _boot_auto_restore_index()와 _boot_autoflow_hook() 호출부([10], [11] 구획)는 main 함수 진입 시 한 번 실행하도록 유지하되, 이들도 services/index.restore_or_attach() 등을 활용하도록 변경합니다. 예를 들어, services.index.restore_or_attach()는 GitHub 릴리스에서 인덱스 zip을 받아 복원하는 로직을 포함하며, 내부에서 성공 시 _set_brain_status("READY", ...)를 호출해 줍니다
GitHub
GitHub
. 따라서 main에서 restore_or_attach()를 호출하고 반환값에 따라 추가 조치를 할 수 있습니다. 이러한 부팅 시퀀스를 한 곳에 모아두면, 자동 복원이나 초기 자동 Q&A 실행(autoflow) 등의 동작을 추후 손쉽게 변경할 수 있습니다.
위 계획에 따라 app.py를 분할하면, 본래 [01]~[18]로 이어지던 구획들이 각 파일로 흩어지게 됩니다. 다음 섹션에서는 새로운 구획 번호 부여 및 중복 코드 제거 방안을 다룹니다.
숫자 구획 재정렬 및 중복 코드 제거
MAIC 프로젝트에서는 코드 블록을 [번호] ... START/END 주석으로 구획화하여 관리하고 있습니다. 코드 구조를 재편함에 따라 이 번호 체계도 재정렬할 것을 제안합니다:
파일별 독립 구획 번호: 리팩토링 후에는 하나의 거대한 app.py 대신 다수의 모듈이 생기므로, 각 파일 내에서 구획 번호를 새로 매깁니다. 예컨대 src/ui/header.py 파일의 경우 [01] 헤더 및 로그인, [02] 관리자 로그인 폼, [03] 로그아웃 처리 등의 식으로 해당 모듈 내 논리 단위를 번호 붙입니다. src/ui/chat_panel.py는 [01] 채팅 말풍선 CSS, [02] 말풍선 출력 함수, [03] 채팅 패널 렌더, [04] 입력폼 렌더 등으로 나눌 수 있습니다. 이렇게 하면 각 파일이 자체적인 1번부터의 번호 체계를 가져가며, 구획 번호의 충돌 없이 관리됩니다.
번호 순서 및 의미 부여: 새로운 구획 번호는 최대한 논리 흐름에 따라 오름차순으로 부여합니다. 특히 이전에 임시로 삽입되어 어색했던 [12C] 같은 표기는 모두 제거하고 정수 번호로 정리합니다. 예를 들어, 진단 패널 관련 코드가 이제 diagnostic_panel.py에 모이면, 거기서는 [01] Orchestrator Header, [02] Ready Probe처럼 1, 2로 깨끗하게 정의합니다. app.py 본문은 크게 줄어들기 때문에 [01]부터 [05] 정도까지만 필요한 상황이며, 예컨대 [01] imports, [02] page config, [03] main entry 등으로 매우 단순해질 것입니다.
중복 코드 제거: 구획 재정렬 과정에서 삭제 혹은 병합되는 코드 블록에는 번호를 재사용하지 않도록 합니다. 예를 들어 PERSIST_DIR 정의가 한쪽으로 통합된다면, 다른 쪽 파일의 해당 구획([03] Persist Resolver 등)은 제거됩니다. 제거된 코드의 번호는 전체에서 빠지게 되므로, 이후 구획 번호를 재조정합니다. 불필요한 import나 중복된 _header() 내 세션 초기화 같은 블록들도 제거하며, 이러한 부분이 별도 구획으로 되어 있었다면 통째로 삭제 (START~END 포함)하고 다음 번호들을 앞으로 당깁니다. 최종적으로 각 파일 내에서 [01]~[NN]까지 빈틈없이 연속적인 번호가 매겨지도록 하며, 이를 통해 코드 리뷰나 패치 시 혼동을 줄입니다.
예시 – 구획 번호 재편:
기존 app.py의 [12C] Ready Probe 부분은 이제 diagnostic_panel.py의 [02] 구획으로 변경
기존 [13] ADMIN: Index Panel 구획은 admin_panel.py의 [02] 구획으로, [14] Indexed Sources Panel은 [03] 구획으로 재배치
새로운 services/index.py에서는 [01] ~ [10] 등의 구획 번호를 사용하되 (이미 해당 파일에 일부 번호 주석이 있음), 프로젝트 표준에 맞게 START/END 주석을 추가하고 설명을 붙입니다.
이러한 구획 재정렬 작업은 **전체 코드 교체 작업(whole segment replacement)**을 수월하게 합니다. 리팩토링 후 처음 한 번은 번호 대응이 많이 바뀌겠지만, 일단 정돈된 이후에는 각 모듈의 변경이 해당 파일 안에서 관리되므로 patch 단위를 명확히 지정할 수 있습니다. 또한 번호 재정렬 과정에서 드러나는 중복 코드는 철저히 제거 또는 병합하여, 같은 기능을 가진 구획이 두 곳에 존재하지 않게 합니다. 예를 들어, 과거 Orchestrator와 관리자 패널에 각각 있었던 “인덱스 빌드” 구획을 하나로 합치고, Orchestrator 쪽에서는 그 구획 자체를 없애거나 Admin 구획을 재사용하게 함으로써, 이제 인덱싱 관련 코드는 오직 한 구획(한 모듈)에만 존재하게 됩니다.
중복 기능의 서비스화 및 헬퍼 추출 설계
앞서 분석한 중복된 기능들을 단일 서비스 또는 헬퍼 함수로 추출하는 구체적인 구조를 설계하면 다음과 같습니다:
인덱싱 기능 통합: 인덱싱 로직은 src/services/index.py의 reindex() 함수로 일원화합니다. 이 함수는 내부에서 src.rag.index_build.rebuild_index (또는 필요시 다른 가용한 인덱싱 함수를 _pick_reindex_fn으로 탐색)만 호출하며, 인덱싱 성공 여부를 boolean으로 리턴합니다
GitHub
GitHub
. 관리자 패널의 HQ 재인덱싱 버튼이나 자동 재인덱싱 시나리오에서는 모두 services.index.reindex()를 호출하도록 변경합니다. 이렇게 하면 향후 인덱싱 방법이 변경돼도 UI 측 코드는 수정할 필요 없이 이 서비스 함수만 바꾸면 됩니다. 또한 reindex() 내부에서 .ready 파일 생성이나 index 결과 검증을 책임지도록 구현하면, UI에서는 별도로 _mark_ready() 등을 호출할 필요가 없어집니다. 실제 코드에서는 reindex() 이후 services.index.index_status()나 _local_ready()를 호출해 최종 상태를 확인하고, 바로 _set_brain_status("READY", "...")를 세션에 반영하게 할 수 있습니다
GitHub
GitHub
.
인덱스 상태 관리 일원화: 분산되어 있던 인덱스 상태 확인 및 배지 업데이트 로직을 services/index.py의 헬퍼들로 모읍니다. 예를 들어 index_status(p) 함수는 주어진 Persist 디렉터리에 대해 .ready 존재 여부, chunks 파일 크기 등을 검사하여 status 딕셔너리를 반환합니다
GitHub
. 이 함수는 기존 src/rag/index_status.get_index_summary와 유사한 역할을 하므로, 그 구현을 대체하거나 index_status에서 해당 함수를 호출하도록 조정할 수 있습니다. 그리고 UI 헤더 배지 업데이트는 이제 어디서든 services.index._set_brain_status(code, msg, source, attached) 함수를 호출하면 세션 상태에 일관된 필드(brain_status_code, brain_status_msg 등)가 설정되도록 합니다
GitHub
. 기존 _set_brain_status가 app.py에 있었다면 이 구현을 옮기고, app.py 및 UI 모듈들은 모두 이 서비스를 사용하게 변경합니다. 또한 .ready 신호파일 생성도 서비스 레이어에서 자동 처리하게 합니다. 예컨데 인덱싱 후 services.index._ensure_ready_signal()를 호출하면 chunks.jsonl이 존재하는지 확인하여 .ready를 멱등적으로 생성해줍니다
GitHub
. 이를 통해 과거 관리자 패널에서 누락되었던 _mark_ready() 호출 문제도 자연스럽게 해결됩니다.
인덱싱 복원 및 백업 통합: 자동 인덱스 복원 (GitHub 릴리스에서 index.zip 받기)과 수동 백업 업로드 기능 역시 서비스화합니다. services/index.py에 이미 제공된 restore_or_attach() 함수는 .ready 파일이 없을 때 GitHub 최신 릴리스에서 인덱스를 복원하고 상태를 세션에 반영하는 논리를 담고 있습니다
GitHub
GitHub
. 현재 app.py의 _boot_auto_restore_index()가 이 역할을 하던 것을 대체하여, main에서 services.index.restore_or_attach()만 호출하면 자동 복원이 이뤄지도록 개선합니다. 또한 관리자 패널의 “ZIP/Release 업로드” 기능(현재 app.py에서 GH_TOKEN 확인 후 릴리스 생성)은 추후 services.index.backup_to_github() (가칭)으로 빼서 구현할 수 있습니다. 이렇게 하면 네트워크 연동 로직과 UI 코드가 분리되어 테스트도 용이해집니다. Orchestrator 패널에서 복원 함수를 따로 호출하던 부분도 서비스의 restore_or_attach()로 통일하여, 복원 경로 역시 하나로 합칩니다.
prepared 파일 처리 통합: prepared 디렉토리의 새 파일 체크 및 소비 기능은 src/services/prepared.py (또는 services.index 내)로 분리합니다. 예를 들어 services.prepared.list_files()는 현재 app.py 두 군데에서 _load_prepared_lister()로 구현된 모듈 탐색 로직을 포함하고, GDrive 연동과 로컬 prepared 모듈을 순서대로 시도하여 파일 목록을 리턴합니다. 마찬가지로 check_new_files() 함수는 check_prepared_updates()를 호출해 새 파일 리스트를 얻고, 그 결과를 리턴하거나 .ready 없는 경우 바로 인덱싱 필요 신호로 활용할 수 있습니다. 또한 mark_files_consumed() 함수로 mark_prepared_consumed()를 추상화하여, 인덱싱 완료 후 한 번만 호출하도록 일원화합니다. 현재는 스캔 패널과 인덱싱 패널이 각자 check_prepared_updates와 mark_prepared_consumed를 호출하는데, 전자를 services.prepared.check_new_files()로, 후자를 인덱싱 서비스 내 로직으로 합쳐 한 곳에서 처리하도록 바꿉니다. 결과적으로 prepared 관련 모듈(prepared.py나 gdrive.py) 변경 시에도 UI 코드 수정을 최소화할 수 있습니다.
UI 컴포넌트 중복 제거: UI 측면에서는 Orchestrator와 관리자 패널의 기능 중복이 제거됩니다. 현재 개선된 코드에서는 Orchestrator 패널이 인덱싱 기능을 직접 수행하지 않고 단순 모니터링 역할만 하도록 변경되었으며, “인덱싱은 관리자 패널에서 하라”는 안내를 표시하고 있습니다. 이러한 방식이 유지되면 Orchestrator와 Admin 패널 간 로직 충돌은 사라집니다. 혹은 반대로, Orchestrator 패널에서도 services.index.reindex()를 호출하는 버튼을 제공할 수 있지만, 그러면 UI가 두 군데로 늘어나는 것이므로 현행처럼 한쪽(UI 관리자 패널)으로 모으는 것이 좋아 보입니다. 두 경우 모두 내부 구현은 동일한 서비스 함수를 쓰게 하여 버튼 위치만 다르고 동작은 같다는 목표를 달성합니다. 또, 채팅창 UI의 말풍선 렌더 문제를 개선하기 위해 _emit_bubble 출력 구조를 조정할 때도, 해당 기능을 한 곳에서만 변경하도록 구조를 단순화합니다. 예컨대 현재 여러 st.empty().markdown으로 나뉘어 출력되는 것을 단일 컨테이너로 출력하도록 개선하면, 이 로직은 chat_panel.py 내 한 구획에서 관리되고 app.py 등 다른 곳에는 없게 됩니다. 이를 통해 UI 일관성과 중복 제거를 동시에 도모합니다.
정리하면, 서비스/헬퍼로 추출된 함수들은 UI에 비해 변경이 적게 일어나는 안정된 로직을 담으며, 중복되었던 인덱싱/복원/상태관리 코드들을 한 곳으로 모아줍니다. UI 모듈은 이러한 서비스를 호출만 하므로 코드가 단순해지고, 비즈니스 로직 수정 시에도 서비스 레이어만 수정하면 되어 버그 발생 가능성이 줄어듭니다. 또한 이러한 추출된 함수들에 대해 별도 단위 테스트 작성도 용이해져, 인덱싱이나 복원 기능을 Streamlit 없이도 검증할 수 있습니다.
코드 품질(린트, 타입체크, 테스트) 준수를 위한 점검
마지막으로, 제안된 구조가 Ruff 린터, Mypy 타입체크, Pytest 테스트를 통과할 수 있도록 사전 검토합니다:
린트(Ruff): 모듈 분리 후 불필요해진 import와 변수들은 제거하거나 통합합니다. 예를 들어 app.py에서 분리된 모듈들은 필요한 곳에서 다시 import해야 하는데, 사용되지 않는 import가 남지 않도록 신경씁니다. 코드 리뷰에서 지적된 부분처럼 중복 import를 정리하고, forward reference 주석 등을 활용해 F401(사용 안 함)이나 F821(정의 안 됨) 오류를 해결합니다. 실제로 index_build.py에서도 Ruff 에러를 피하려고 주석 처리한 부분이 있었는데, 이제는 타입 힌트를 적절히 넣고 불필요 코드를 삭제하여 깨끗이 통과하도록 합니다. 또한 각 모듈 파일의 길이가 줄어들어 린터가 권고하는 복잡도/길이 제한도 자연스럽게 만족될 것입니다.
타입체크(Mypy): 함수 사이에 명확한 인터페이스를 정의하고 타입 힌트를 꼼꼼히 작성합니다. 기존 코드에서도 from __future__ import annotations를 통해 forward reference를 허용하고 타입을 맞추려 노력했으며
GitHub
, 서비스 모듈에서도 제네릭한 Dict[str, Any] 등을 사용하고 있습니다. 리팩토링 시 순환 참조에 유의하여 import 구조를 잡고, 필요한 경우 Lazy import (importlib.import_module) 기법을 서비스 레이어에서 활용합니다
GitHub
. 예컨대 Streamlit을 필요로 하지만 타입 체크 시점엔 없을 수 있는 경우 if TYPE_CHECKING: 블록을 써서 가짜 import를 하거나, 함수 내부에서 import하는 방식으로 Mypy 오류를 피합니다. 또한 UI 모듈들이 서비스 함수를 사용할 때 리턴 타입에 따라 분기하는 논리가 있다면, 해당 서비스 함수의 타입 힌트를 정확히 명시해 일치시키겠습니다. 이러한 타입 엄격화는 버그를 사전에 잡는 데 도움이 되고, CI의 mypy 단계에서 오류가 없도록 해줄 것입니다.
테스트(Pytest): 핵심 로직을 서비스와 코어 모듈에 위임함으로써 테스트 가능성이 높아집니다. 이미 존재하는 tests/test_rag_search.py, tests/test_label_rag.py 등은 src/rag 모듈이 변경되지 않으므로 그대로 통과해야 합니다. 추가로, 새로 만든 services/index.py 등에 대해서는 별도의 테스트를 작성할 수 있습니다. 예를 들어 test_services_index.py를 만들어 reindex() 호출이 인덱스 파일을 만들어 .ready를 생성하는지, restore_or_attach()가 로컬에 index가 없을 때 원격 복원 후 READY 상태가 되는지 등을 시뮬레이션합니다 (필요시 작은 샘플 데이터로 index_build 동작을 시험하거나, src/rag/index_build.py를 모킹하여 빠르게 확인). UI 코드 자체는 Streamlit 환경 의존적이어서 직접 테스트가 어렵지만, 서비스 계층이 잘 동작하면 UI는 그 결과를 표시하기만 하므로 간접적으로 검증된다고 볼 수 있습니다. CI 파이프라인에서 린트→타입체크→테스트 순으로 돌렸을 때, 리팩토링된 구조도 모두 녹색 표시가 나오도록 각 단계별로 점검을 완료하겠습니다. 특히, 세션 상태 키나 환경변수 의존 로직은 테스트에서 예측 가능하게 다뤄져야 하므로, 함수에 주입하거나 Override할 수 있게 설계합니다. (예: services.index.reindex(dest_dir=tempdir) 형태로 경로를 지정 가능하게 해 테스트상 tmp 경로에 인덱싱해보는 등
GitHub
GitHub
)
문서와 주석 업데이트: 린트/타입체크 통과 외에도, 코드 개편에 따라 README나 주석의 구획 번호, 함수 위치 언급 등을 모두 업데이트해야 합니다. 마스터플랜 문서나 주석에 적힌 [13] 등의 번호도 새 구조에 맞게 수정하여 혼동을 방지합니다. 추후 개발자들이 최신 구조를 이해하는 데 도움이 되도록 폴더 구조도(위에 제시한 내용을 바탕으로) README에 포함하고, 주요 진입점(app.py -> ui/ -> services/ -> rag/)을 설명합니다.
유지보수 관점을 고려한 모듈별 가이드
마지막으로, 재구성 후 코드베이스에서 어떤 기능을 수정하거나 확인하고자 할 때 어느 모듈을 먼저 참고해야 하는지에 대한 가이드를 정리합니다:
UI/프론트 문제 발생 시: src/ui/ 내부 모듈들을 확인합니다. 예를 들어 채팅 화면 표시 오류나 말풍선 스타일 문제는 ui/chat_panel.py를 살펴보고, 헤더나 로그인 관련 이슈는 ui/header.py에서 원인을 찾을 수 있습니다. Streamlit 레이아웃이나 위젯 동작이 예상과 다르면 해당 UI 모듈의 함수를 수정하면 됩니다. UI 변경은 서비스나 코어에 영향 없이 독립적입니다.
인덱싱 및 RAG 동작 수정 시: src/services/index.py와 src/rag/ 패키지를 확인합니다. 예컨대 인덱싱 성능을 높이거나 버그를 수정하려면 services/index.reindex()와 호출하는 rag/index_build.py의 rebuild_index()를 함께 수정합니다. 출처 라벨링을 변경하고 싶다면 src/rag/label.py의 decide_label() 로직을 변경하면 되고, 채팅 응답에 반영되는지는 ui/chat_panel.py에서 이 함수를 호출하는 부분을 보면 됩니다. 인덱스 경로 변경이나 Persist 전략 변경이 필요하면 src/config.py의 PERSIST_DIR 설정과 services/index.py의 경로 관련 함수들을 수정하면 됩니다.
LLM 응답 및 에이전트 논리 수정 시: src/agents/와 src/llm/ 모듈을 참고합니다. 피티쌤/미나쌤의 답변 스타일이나 프롬프트를 바꾸려면 agents/responder.py와 agents/evaluator.py를 편집합니다. OpenAI나 Gemini 등 LLM API 키, 모델명 변경은 src/llm/providers.py의 설정을 변경하거나 환경변수를 조정하면 됩니다. 스트리밍 방식(예: 문장별 스트리밍 구현)은 src/llm/streaming.py에서 옵션 (BufferOptions)을 조정하여 실험할 수 있습니다.
관리자 기능 동작 점검 시: 관리자 패널의 로직은 src/ui/admin_panel.py에, 그와 연동되는 서비스는 src/services/index.py에 있습니다. **“인덱싱해도 배지가 안 바뀐다”**와 같은 문제가 생기면 services.index._set_brain_status 호출 누락 여부를 확인합니다 (예전에는 _mark_ready() 호출 누락이 이슈였음). 드라이브 prepared 연동 문제는 services/prepared.py (가정)와 src/integrations/gdrive.py 쪽을 함께 살펴봅니다. 이처럼 관리자 모드 관련 이슈는 주로 서비스 레이어와 UI 레이어의 상호작용에서 발생하므로 두 부분을 모두 살펴보면 됩니다.
전반적인 설정/환경 문제 시: src/config.py (있다면)와 .streamlit/secrets.toml 등을 확인합니다. 예를 들어 환경변수 또는 시크릿 불러오기 이슈는 _bootstrap_env() 구현이나 config.py의 설정을 점검하고, CI/CD 구성 문제는 GitHub Actions 워크플로 (.github/workflows/)와 린트/타입 설정(ruff.toml, mypy.ini)을 살펴 조정합니다.
이러한 구조에서는 새로운 기여자가 특정 기능을 개선하거나 버그를 찾고자 할 때 관계된 모듈 하나 혹은 적은 범위만 집중하면 되도록 의도되었습니다. 결과적으로 코드베이스가 훨씬 모듈화되고 이해하기 쉬워져, MAIC 프로젝트의 향후 유지보수 및 확장에 큰 도움이 될 것으로 기대됩니다. 각 기능 영역별로 위 가이드라인을 따라 관련 모듈을 먼저 열람하면 문제 파악과 해결이 한결 수월해질 것입니다.
