# MAIC 에러 추적 및 자동 수정 시스템

## 📋 개요

MAIC 프로젝트의 에러 추적 및 자동 수정 시스템은 반복되는 에러를 자동으로 감지하고, 3회 이상 발생하는 에러를 `DEVELOPMENT_HISTORY.md`에 자동으로 기록하며, 자동 수정 기능을 제공합니다.

## 🏗️ 시스템 구조

### 1. 핵심 컴포넌트

```
tools/
├── error_tracker.py      # 에러 추적 및 로깅 시스템
├── error_monitor.py      # 에러 모니터링 통합 모듈
├── auto_error_fixer.py   # 자동 에러 수정 시스템
└── test_error_tracker.py # 테스트 스크립트
```

### 2. 에러 타입 분류

- **import_error**: Import 경로 및 모듈 관련 에러
- **cache_error**: Python/Streamlit 캐시 관련 에러
- **streamlit_error**: Streamlit 컴포넌트 및 세션 관련 에러
- **ui_error**: UI 컴포넌트 및 CSS 관련 에러

## 🚀 사용법

### 1. 자동 에러 추적 (app.py에 이미 통합됨)

```python
# app.py 상단에 자동으로 포함됨
from tools.error_monitor import setup_global_error_tracking, setup_streamlit_error_tracking
setup_global_error_tracking()
setup_streamlit_error_tracking()
```

### 2. 수동 에러 로그 기록

```python
from tools.error_tracker import ErrorTracker

tracker = ErrorTracker()
error_id = tracker.log_error("에러 메시지", {"context": "추가 정보"})
```

### 3. 함수 모니터링 데코레이터

```python
from tools.error_monitor import monitor_function

@monitor_function(max_retries=3, auto_retry=True)
def risky_function():
    # 자동으로 에러 추적 및 재시도
    pass
```

### 4. Import 모니터링

```python
from tools.error_monitor import monitor_imports

with monitor_imports():
    # Import 에러가 자동으로 추적됨
    import some_module
```

### 5. 자동 에러 수정

```bash
# 모든 반복 에러 자동 수정
python tools/auto_error_fixer.py --fix

# 특정 에러 타입만 수정
python tools/auto_error_fixer.py --fix --type import_error

# 수정 보고서 생성
python tools/auto_error_fixer.py --report
```

## 📊 에러 추적 기능

### 1. 자동 에러 감지

- **패턴 매칭**: 정규식을 사용한 에러 타입 자동 분류
- **중복 감지**: 동일한 에러의 반복 발생 추적
- **컨텍스트 저장**: 에러 발생 시점의 상세 정보 저장

### 2. 반복 에러 자동 문서화

3회 이상 발생하는 에러는 자동으로 `DEVELOPMENT_HISTORY.md`에 기록됩니다:

```markdown
### 🔴 반복 에러 감지: Import Path Issues

**발생 횟수**: 3회  
**에러 타입**: import_error  
**발생 시간**: 2025-01-06 19:00:00

**에러 메시지**:
```
ModuleNotFoundError: No module named 'src.agents'
```

**시도한 해결책**:
1. Python __pycache__ 삭제 - ❌ 실패
2. Import 경로 수정 - ✅ 성공

**권장 해결책**:
1. Python __pycache__ 삭제
2. Import 경로 수정
3. 모듈 구조 확인

**자동화 제안**:
- 이 에러의 자동 해결 스크립트 개발 필요
- 예방 조치 구현 필요
- 모니터링 시스템 강화 필요
```

### 3. 자동 수정 기능

#### Import 에러 수정
- `__pycache__` 폴더 삭제
- Import 경로 자동 수정 (`src.agents` → `src.application.agents`)
- 모듈 구조 검증

#### 캐시 에러 수정
- Python 캐시 삭제
- Streamlit 캐시 삭제
- 임시 파일 정리

#### Streamlit 에러 수정
- 세션 상태 초기화
- 중복 키 해결
- Streamlit 재시작

#### UI 에러 수정
- Linear 컴포넌트 사용 확인
- CSS 충돌 해결
- 컴포넌트 키 중복 해결

## 📈 통계 및 보고서

### 1. 에러 요약

```python
from tools.error_tracker import ErrorTracker

tracker = ErrorTracker()
summary = tracker.get_error_summary()

print(f"총 에러 수: {summary['total_errors']}")
print(f"미해결 에러: {summary['unresolved_errors']}")
print(f"반복 에러: {summary['recurring_errors']}")
```

### 2. 수정 보고서 생성

```bash
python tools/auto_error_fixer.py --report
```

`tools/error_fix_report.md` 파일이 생성됩니다.

## 🔧 설정 및 커스터마이징

### 1. 에러 패턴 추가

`tools/error_tracker.py`의 `_load_error_patterns()` 메서드에서 새로운 에러 패턴을 추가할 수 있습니다:

```python
"new_error_type": {
    "patterns": [
        r"NewError: .*",
    ],
    "category": "New Error Category",
    "common_solutions": [
        "해결책 1",
        "해결책 2"
    ]
}
```

### 2. 자동 수정 함수 추가

`tools/auto_error_fixer.py`의 `_initialize_fixers()` 메서드에서 새로운 수정 함수를 추가할 수 있습니다:

```python
def _fix_new_error_type(self) -> bool:
    """새로운 에러 타입 수정"""
    print("🔧 새로운 에러 수정 중...")
    # 수정 로직 구현
    return True
```

## 🚨 주의사항

### 1. 자동 수정의 한계

- 자동 수정은 **안전한 작업**만 수행합니다
- 복잡한 로직 에러는 수동 개입이 필요할 수 있습니다
- 자동 수정 후에는 **반드시 테스트**를 수행하세요

### 2. 에러 로그 관리

- 에러 로그는 `tools/error_log.json`에 저장됩니다
- 정기적으로 로그를 정리하는 것을 권장합니다
- 민감한 정보는 로그에 기록되지 않도록 주의하세요

### 3. 성능 고려사항

- 에러 추적은 최소한의 오버헤드만 발생시킵니다
- 프로덕션 환경에서는 필요에 따라 비활성화할 수 있습니다

## 📚 관련 파일

- `tools/error_tracker.py` - 핵심 에러 추적 시스템
- `tools/error_monitor.py` - 통합 모니터링 모듈
- `tools/auto_error_fixer.py` - 자동 수정 시스템
- `tools/test_error_tracker.py` - 테스트 스크립트
- `docs/DEVELOPMENT_HISTORY.md` - 자동 생성되는 에러 기록
- `tools/error_log.json` - 에러 로그 데이터
- `tools/error_stats.json` - 에러 통계 데이터

## 🎯 향후 개선 계획

1. **머신러닝 기반 에러 예측**: 과거 에러 패턴을 분석하여 미래 에러 예측
2. **실시간 알림 시스템**: 중요한 에러 발생 시 즉시 알림
3. **에러 우선순위 시스템**: 에러의 심각도에 따른 우선순위 관리
4. **자동 테스트 생성**: 에러 발생 시 자동으로 테스트 케이스 생성
5. **성능 모니터링 통합**: 에러와 성능 지표의 연관성 분석

---

**이 시스템을 통해 MAIC 프로젝트의 안정성과 유지보수성이 크게 향상될 것입니다!** 🚀

