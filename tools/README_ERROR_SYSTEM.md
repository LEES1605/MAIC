# 🤖 MAIC 에러 추적 시스템 - 빠른 시작 가이드

## 🚀 즉시 사용하기

### 1. 자동 에러 추적 (이미 활성화됨)
```bash
# app.py 실행 시 자동으로 에러 추적이 시작됩니다
streamlit run app.py
```

### 2. 반복 에러 자동 수정
```bash
# 모든 반복 에러 자동 수정
python tools/auto_error_fixer.py --fix

# Import 에러만 수정
python tools/auto_error_fixer.py --fix --type import_error

# 캐시 에러만 수정  
python tools/auto_error_fixer.py --fix --type cache_error
```

### 3. 에러 현황 확인
```bash
# 에러 요약 보기
python tools/error_tracker.py summary

# 수정 보고서 생성
python tools/auto_error_fixer.py --report
```

## 🔧 주요 기능

### ✅ 자동으로 처리되는 것들
- **Import 에러**: `src.agents` → `src.application.agents` 자동 수정
- **캐시 에러**: `__pycache__` 폴더 자동 삭제
- **중복 키**: Streamlit 중복 키 자동 해결
- **반복 에러**: 3회 이상 발생 시 `DEVELOPMENT_HISTORY.md`에 자동 기록

### 📊 자동 생성되는 파일들
- `tools/error_log.json` - 에러 로그 데이터
- `tools/error_stats.json` - 에러 통계
- `tools/error_fix_report.md` - 수정 보고서
- `docs/DEVELOPMENT_HISTORY.md` - 반복 에러 기록

## 🚨 자주 발생하는 에러들

### 1. `ModuleNotFoundError: No module named 'src.agents'`
```bash
# 자동 수정
python tools/auto_error_fixer.py --fix --type import_error
```

### 2. `StreamlitDuplicateElementKey`
```bash
# 자동 수정
python tools/auto_error_fixer.py --fix --type streamlit_error
```

### 3. Python 캐시 관련 에러
```bash
# 자동 수정
python tools/auto_error_fixer.py --fix --type cache_error
```

## 📈 에러 추적 현황

현재 시스템이 추적하는 에러 타입:
- **import_error**: Import 경로 문제
- **cache_error**: 캐시 관련 문제  
- **streamlit_error**: Streamlit 컴포넌트 문제
- **ui_error**: UI 렌더링 문제

## 🎯 사용 팁

1. **정기적인 자동 수정**: 개발 중 주기적으로 `--fix` 명령어 실행
2. **에러 패턴 확인**: `summary` 명령어로 에러 현황 파악
3. **문서 확인**: `DEVELOPMENT_HISTORY.md`에서 반복 에러 이력 확인
4. **보고서 생성**: 중요한 수정 후 `--report`로 결과 문서화

## 🔍 문제 해결

### 시스템이 작동하지 않는 경우
```bash
# 에러 추적 시스템 테스트
python tools/test_error_tracker.py
```

### 수동으로 에러 기록하기
```python
from tools.error_tracker import ErrorTracker

tracker = ErrorTracker()
error_id = tracker.log_error("에러 메시지", {"context": "추가 정보"})
```

---

**이제 에러가 발생해도 걱정하지 마세요! 시스템이 자동으로 감지하고 수정해드립니다.** 🚀
