# UI 코드 전수 조사 보고서

## 📊 조사 개요
- **조사 일시**: 2025-10-06
- **조사 범위**: `app.py`, `src/ui/` 전체
- **조사 목적**: UI 코드 통합을 위한 현재 상태 파악

## 🔍 발견된 UI 코드 분포

### 1. **app.py** - 메인 애플리케이션
**총 2개의 CSS 블록 발견**

#### 1-1. 기본 스타일 블록 (라인 207-221)
```css
/* Streamlit 기본 네비게이션 및 사이드바 숨김 */
nav[data-testid='stSidebarNav']{display:none!important;}
div[data-testid='stSidebarNav']{display:none!important;}
section[data-testid='stSidebar']{display:none!important;}
section[data-testid='stSidebar'] [data-testid='stSidebarNav']{display:none!important;}
section[data-testid='stSidebar'] ul[role='list']{display:none!important;}

/* Linear 네비게이션 바 가로 레이아웃 강제 적용 */
.linear-navbar-container{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;align-items:center!important;justify-content:space-between!important;}
.linear-navbar-container > *{display:inline-block!important;vertical-align:middle!important;}
.linear-navbar-nav{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;align-items:center!important;list-style:none!important;margin:0!important;padding:0!important;}
.linear-navbar-nav li{display:inline-block!important;margin:0!important;padding:0!important;}
.linear-navbar-nav-item{display:inline-block!important;vertical-align:middle!important;}
```

#### 1-2. 채팅 스타일 블록 (라인 1093-1189)
```css
/* 채팅 영역 컨테이너 */
.chatpane-messages, .chatpane-input{...}
.chatpane-input div[data-testid="stRadio"]{...}
.chatpane-input form[data-testid="stForm"]{...}

/* 버블/칩 (글로벌) */
.msg-row{...}
.bubble{...}
.chip{...}
.chip-src{...}

/* 프롬프트/페르소나 대형 입력영역 */
.prompt-editor .stTextArea textarea{...}

/* 모바일 반응형 스타일 */
@media (max-width:480px){...}
```

### 2. **src/ui/ops/indexing_panel.py** - 인덱싱 패널
**1개의 CSS 블록 발견**
- Linear 테마 변수 정의
- 인덱싱 관련 UI 스타일

### 3. **src/ui/header.py** - 헤더 컴포넌트
**2개의 CSS 블록 발견**
- 관리자 네비게이션바 CSS
- Linear 테마 색상 변수

### 4. **src/ui/utils/sider.py** - 사이드바 유틸리티
**2개의 CSS 블록 발견**
- Streamlit 사이드바 숨김 스타일
- 사이드바 완전 제거 스타일

### 5. **src/ui/components/linear_layout_components.py** - 레이아웃 컴포넌트
**2개의 CSS 블록 발견**
- 푸터 CSS
- 히어로 CSS

### 6. **src/ui/components/linear_components.py** - Linear 컴포넌트
**8개의 CSS 블록 발견**
- 버튼 CSS
- 카드 CSS
- 배지 CSS
- 입력 필드 CSS
- 알림 CSS
- 구분선 CSS
- 캐러셀 CSS
- 이미지 카드 CSS
- 네비게이션 바 CSS

### 7. **src/ui/components/ios_tabs_simple.py** - iOS 탭
**1개의 CSS 블록 발견**
- Linear 테마 변수 및 탭 스타일

### 8. **src/ui/components/linear_theme.py** - 테마 시스템
**1개의 CSS 블록 발견**
- Linear 테마 색상 변수 정의

### 9. **src/ui/admin_prompt.py** - 관리자 프롬프트
**1개의 CSS 블록 발견**
- 상태 버튼 스타일

### 10. **src/ui/components/ios_tabs.py** - iOS 탭 (고급)
**1개의 CSS 블록 발견**
- iOS 스타일 탭 CSS

## 📈 통계 요약

### CSS 블록 분포
- **총 CSS 블록 수**: 23개
- **app.py**: 2개 (8.7%)
- **src/ui/**: 21개 (91.3%)

### 파일별 CSS 블록 수
1. `linear_components.py`: 8개 (34.8%)
2. `app.py`: 2개 (8.7%)
3. `header.py`: 2개 (8.7%)
4. `sider.py`: 2개 (8.7%)
5. `linear_layout_components.py`: 2개 (8.7%)
6. 기타 5개 파일: 각 1개씩 (21.7%)

### 스타일 카테고리 분류
1. **기본/레이아웃**: 4개 블록
   - Streamlit 숨김, 네비게이션 레이아웃
2. **컴포넌트**: 12개 블록
   - 버튼, 카드, 배지, 입력, 알림, 구분선, 캐러셀, 이미지카드, 네비게이션
3. **채팅**: 1개 블록
   - 채팅 영역, 버블, 칩
4. **테마**: 3개 블록
   - Linear 테마 변수
5. **관리자**: 2개 블록
   - 관리자 네비게이션, 상태 버튼
6. **반응형**: 1개 블록
   - 모바일 미디어 쿼리

## 🔍 중복 및 문제점 분석

### 1. **중복 코드**
- **Linear 테마 변수**: 4개 파일에서 중복 정의
  - `indexing_panel.py`, `header.py`, `ios_tabs_simple.py`, `linear_theme.py`
- **사이드바 숨김**: 2개 파일에서 중복 정의
  - `app.py`, `sider.py`

### 2. **일관성 문제**
- **색상 변수**: 파일마다 다른 값 사용
- **네이밍**: 일관되지 않은 CSS 클래스명
- **구조**: 비슷한 스타일이 여러 곳에 분산

### 3. **유지보수성 문제**
- **하드코딩**: 색상값이 여러 곳에 하드코딩
- **의존성**: 스타일 간 의존성 불명확
- **테스트**: 개별 스타일 테스트 어려움

## 🎯 통합 우선순위

### 높은 우선순위 (즉시 통합 필요)
1. **Linear 테마 변수** - 4개 파일에서 중복
2. **사이드바 숨김 스타일** - 2개 파일에서 중복
3. **기본 레이아웃 스타일** - `app.py`의 기본 스타일

### 중간 우선순위 (단계적 통합)
1. **컴포넌트 스타일** - `linear_components.py`의 8개 블록
2. **채팅 스타일** - `app.py`의 채팅 관련 스타일
3. **관리자 스타일** - 관리자 관련 UI

### 낮은 우선순위 (나중에 통합)
1. **iOS 탭 스타일** - 특수 용도
2. **반응형 스타일** - 모바일 최적화

## 📋 다음 단계 권장사항

### 1단계: 기본 구조 생성
- `src/ui/styles/` 폴더 생성
- 기본 스타일 모듈 생성

### 2단계: 중복 제거
- Linear 테마 변수 통합
- 사이드바 숨김 스타일 통합

### 3단계: 컴포넌트 통합
- Linear 컴포넌트 스타일 통합
- 채팅 스타일 분리

### 4단계: 테스트 및 검증
- UI 렌더링 테스트
- 스타일 적용 확인

---
**작성일**: 2025-10-06  
**작성자**: AI Assistant  
**상태**: 조사 완료, 통합 준비
