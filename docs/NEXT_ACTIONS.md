# Next Actions
## AI가 수행해야 할 다음 작업

### 🚀 1단계: UI 코드 통합 (최우선)

#### 1.1 UI 파일 분석 및 정리
```bash
# 현재 루트의 UI 파일들 확인
- working_neumorphism.py
- maic_simple_neumorphism.py  
- simple_neumorphism.py
- ultimate_neumorphism.py
- neumorphism_elements.py
- neumorphism_app.html
- maic_neumorphism_app.html
```

#### 1.2 올바른 UI 파일 식별
- **목표**: `neumorphism_app.html`이 올바른 UI임을 확인
- **검증**: 로컬에서 HTML UI 정상 작동 확인
- **기능**: 관리자 로그인(`admin123`), 모드 선택, 채팅

#### 1.3 UI 파일 이동 및 통합
```bash
# 이동할 파일
neumorphism_app.html → src/ui/neumorphism_app.html

# 삭제할 중복 파일들
working_neumorphism.py
maic_simple_neumorphism.py
simple_neumorphism.py
ultimate_neumorphism.py
neumorphism_elements.py
maic_neumorphism_app.html
```

#### 1.4 app.py 단순화
```python
# 현재 app.py (복잡함)
# 목표: 단순한 진입점으로 변경
import streamlit as st
from src.ui.neumorphism_app import render_neumorphism_ui

def main():
    render_neumorphism_ui()

if __name__ == "__main__":
    main()
```

### 🔧 2단계: 자동 검증 시스템 강화

#### 2.1 UI 파일 생성 차단 로직 추가
```python
# tools/universal_validator.py에 추가
def _check_ui_file_creation(self, search_term):
    """UI 파일이 루트에 생성되는지 확인"""
    if "ui" in search_term.lower() or "neumorphism" in search_term.lower():
        return "UI 파일은 src/ui/ 디렉토리에만 생성하세요"
    return None
```

#### 2.2 중복 파일 감지 강화
```python
# 기존 중복 파일들 자동 감지
DUPLICATE_UI_FILES = [
    "working_neumorphism.py",
    "maic_simple_neumorphism.py",
    "simple_neumorphism.py",
    "ultimate_neumorphism.py",
    "neumorphism_elements.py"
]
```

### 📁 3단계: 프로젝트 구조 최적화

#### 3.1 legacy/ 디렉토리 생성
```bash
mkdir legacy/
# 혼란스러운 파일들을 legacy/로 이동
```

#### 3.2 루트 정리
```bash
# 루트에 남을 파일들
app.py
src/
docs/
tools/
tests/
assets/
legacy/
README.md
requirements.txt
pyproject.toml
```

### 🎯 4단계: HTML UI Streamlit 통합

#### 4.1 HTML UI 렌더링 해결
```python
# src/ui/neumorphism_app.py 생성
import streamlit as st
import streamlit.components.v1 as components

def render_neumorphism_ui():
    with open('src/ui/neumorphism_app.html', 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    components.html(html_content, height=800, scrolling=True)
```

#### 4.2 테스트 및 검증
- 로컬에서 HTML UI 정상 렌더링 확인
- 온라인 배포에서 정상 작동 확인
- 모든 기능 (로그인, 모드 선택, 채팅) 테스트

### 📋 실행 체크리스트

#### UI 코드 통합
- [ ] 루트 UI 파일들 분석
- [ ] 올바른 UI 파일 식별
- [ ] 중복 파일들 삭제
- [ ] UI 파일을 `src/ui/`로 이동
- [ ] `app.py` 단순화

#### 자동 검증 강화
- [ ] UI 파일 생성 차단 로직 추가
- [ ] 중복 파일 감지 강화
- [ ] 검증 시스템 테스트

#### 구조 최적화
- [ ] `legacy/` 디렉토리 생성
- [ ] 혼란스러운 파일들 이동
- [ ] 루트 정리

#### HTML UI 통합
- [ ] HTML UI 렌더링 해결
- [ ] 로컬 테스트
- [ ] 온라인 배포 테스트

### ⚠️ 주의사항
1. **사용자 승인 필수**: 모든 파일 삭제/이동 전 승인 받기
2. **백업 생성**: 중요한 파일들 백업
3. **단계별 실행**: 한 번에 하나씩 실행
4. **테스트 필수**: 각 단계마다 테스트

---
## 관련 문서
- [AI_RULES.md](AI_RULES.md) - AI 규칙
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - 프로젝트 구조
- [CURRENT_STATUS.md](CURRENT_STATUS.md) - 현재 상태
- [DEVELOPMENT_HISTORY.md](DEVELOPMENT_HISTORY.md) - 개발 과정 기록
- [MASTERPLAN.md](MASTERPLAN.md) - 전체 계획

