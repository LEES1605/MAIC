# UI 찌꺼기 코드 정리 계획

## 📊 현재 상황 분석

### 발견된 CSS 블록 분포:
- **총 21개 파일**에서 CSS 스타일 블록 발견
- **총 60+ 개의 CSS 블록** 식별
- **주요 중복**: Linear 테마 변수, Streamlit 사이드바 숨김, Linear 컴포넌트 스타일

### 🔍 주요 문제점:

#### 1. 중복된 CSS 블록들:
- **Linear 테마 변수** (`:root` 변수): 4개 파일에서 중복
  - `src/ui/header.py` (라인 211)
  - `src/ui/ops/indexing_panel.py` (라인 40)
  - `src/ui/components/linear_theme.py` (라인 96)
  - `src/ui/components/ios_tabs_simple.py` (라인 39)

- **Streamlit 사이드바 숨김**: 2개 파일에서 중복
  - `app.py` (라인 218)
  - `src/ui/utils/sider.py` (라인 17, 122)

- **Linear 컴포넌트 스타일**: `linear_components.py`에서 12개 블록
  - 버튼, 카드, 뱃지, 입력, 알림, 구분선, 캐러셀, 이미지 카드, 네비게이션 바 등

#### 2. 사용되지 않는 파일들:
- **Demo 파일들**: `demo_components_*.py` (테스트용)
- **Test 파일들**: `test_components_simple.py`, `test_html.py`
- **Legacy 파일들**: `ios_tabs.py`, `ios_tabs_simple.py`

#### 3. 모듈화되지 않은 스타일:
- **새로운 모듈화 시스템**: `src/ui/styles/` 폴더에 있지만 아직 모든 스타일이 이전되지 않음
- **기존 인라인 스타일**: 여전히 많은 파일에서 `st.markdown("<style>")` 사용

## 🎯 정리 우선순위

### 1단계: 중복 제거 (즉시 실행)
- [ ] Linear 테마 변수 통합 (4개 파일 → 1개)
- [ ] Streamlit 사이드바 숨김 통합 (2개 파일 → 1개)
- [ ] 사용되지 않는 demo/test 파일 삭제

### 2단계: 모듈화 완성
- [ ] `linear_components.py`의 12개 CSS 블록을 `src/ui/styles/components.py`로 이동
- [ ] `header.py`의 CSS를 `src/ui/styles/header.py`로 이동
- [ [ ] `indexing_panel.py`의 CSS를 `src/ui/styles/admin.py`로 이동

### 3단계: 최적화
- [ ] 사용되지 않는 CSS 선택자 제거
- [ ] CSS 압축 및 최적화
- [ ] 성능 테스트 및 검증

## 📋 실행 계획

### Phase 1: 중복 제거 (30분)
1. Linear 테마 변수 통합
2. Streamlit 사이드바 숨김 통합
3. 사용되지 않는 파일 삭제

### Phase 2: 모듈화 완성 (60분)
1. Linear 컴포넌트 스타일 모듈화
2. 헤더 스타일 모듈화
3. 관리자 스타일 모듈화

### Phase 3: 최적화 및 테스트 (30분)
1. CSS 최적화
2. 자동 테스트 실행
3. 성능 검증

## 🎯 예상 효과

### 코드 중복 제거:
- **70% 이상의 CSS 중복 제거**
- **파일 크기 30% 감소**
- **유지보수성 대폭 향상**

### 성능 개선:
- **CSS 로딩 시간 단축**
- **메모리 사용량 감소**
- **렌더링 성능 향상**

### 개발 경험 개선:
- **일관된 스타일 시스템**
- **쉬운 테마 변경**
- **모듈화된 구조**
