# Project Structure
## AI가 알아야 할 프로젝트 구조

### 📁 디렉토리 구조
```
MAIC/
├── app.py                           ← 메인 진입점 (단순하게 유지)
├── src/                            ← 모든 실제 구현
│   ├── ui/                         ← UI 컴포넌트
│   │   ├── components/             ← 재사용 가능한 컴포넌트
│   │   ├── layouts/                ← 레이아웃 구성요소
│   │   ├── styles/                 ← 스타일 정의
│   │   ├── utils/                  ← UI 유틸리티
│   │   └── widgets/                ← 특수 위젯
│   ├── application/                ← 비즈니스 로직
│   ├── domain/                     ← 도메인 모델
│   ├── infrastructure/             ← 인프라 코드
│   ├── services/                   ← 서비스 레이어
│   └── shared/                     ← 공유 유틸리티
├── docs/                           ← 문서
│   ├── AI_RULES.md                 ← AI 규칙
│   ├── PROJECT_STRUCTURE.md        ← 이 파일
│   ├── CURRENT_STATUS.md           ← 현재 상태
│   ├── NEXT_ACTIONS.md             ← 다음 작업
│   ├── DEVELOPMENT_HISTORY.md      ← 개발 과정
│   └── _archive/                   ← 구버전 문서
├── tools/                          ← 개발 도구
├── tests/                          ← 테스트 코드
├── legacy/                         ← 건드리지 마세요
└── assets/                         ← 정적 자원
```

### 🎯 각 디렉토리의 역할

#### `src/ui/` - UI 컴포넌트
- **목적**: 모든 사용자 인터페이스 관련 코드
- **구조**:
  - `components/`: 재사용 가능한 UI 컴포넌트
  - `layouts/`: 페이지 레이아웃
  - `styles/`: CSS/스타일 정의
  - `utils/`: UI 관련 유틸리티
  - `widgets/`: 특수 위젯

#### `src/application/` - 비즈니스 로직
- **목적**: 애플리케이션의 핵심 비즈니스 로직
- **예시**: 사용자 관리, 프롬프트 처리, 채팅 로직

#### `src/domain/` - 도메인 모델
- **목적**: 도메인 객체와 비즈니스 규칙
- **예시**: 사용자 엔티티, 프롬프트 엔티티

#### `src/infrastructure/` - 인프라 코드
- **목적**: 외부 시스템과의 연동
- **예시**: 데이터베이스 연결, API 클라이언트

### 🚫 금지된 위치
- **루트 디렉토리**: `app.py` 외의 새 파일 생성 금지
- **legacy/**: 절대 건드리지 마세요
- **venv/**: 가상환경 파일 (자동 생성)

### 🔍 현재 UI 파일 분산 문제
루트에 흩어진 UI 관련 파일들:
```
루트/
├── working_neumorphism.py          ← 확인 필요
├── maic_simple_neumorphism.py     ← 확인 필요
├── simple_neumorphism.py          ← 확인 필요
├── ultimate_neumorphism.py        ← 확인 필요
├── neumorphism_elements.py        ← 확인 필요
├── neumorphism_app.html           ← 확인 필요
└── maic_neumorphism_app.html      ← 확인 필요
```

**해결 방안**: 이 파일들을 `src/ui/` 로 통합하고 중복 삭제

### 📋 파일 생성 규칙
1. **Python 파일**: `src/` 내부에만 생성
2. **UI 파일**: `src/ui/` 에만 생성
3. **테스트 파일**: `tests/` 에만 생성
4. **문서 파일**: `docs/` 에만 생성
5. **도구 파일**: `tools/` 에만 생성

### 🎯 명명 규칙
- **Python 파일**: `snake_case.py`
- **클래스**: `PascalCase`
- **함수/변수**: `snake_case`
- **상수**: `UPPER_CASE`

---
## 관련 문서
- [AI_RULES.md](AI_RULES.md) - AI 규칙
- [CURRENT_STATUS.md](CURRENT_STATUS.md) - 현재 상태
- [NEXT_ACTIONS.md](NEXT_ACTIONS.md) - 다음 작업
- [DEVELOPMENT_HISTORY.md](DEVELOPMENT_HISTORY.md) - 개발 과정 기록
- [MASTERPLAN.md](MASTERPLAN.md) - 전체 계획

