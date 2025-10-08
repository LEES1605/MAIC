# 🛡️ 개발 워크플로우 가이드

## 🚨 반복 실수 방지 시스템

### ❌ 자주 발생하는 실수들
1. **app.py에 UI 코드 직접 추가** - 절대 금지!
2. **src/ui/ 디렉토리 구조 무시** - 반드시 준수!
3. **코드 수정 후 검증 안 함** - 항상 확인!
4. **일관성 없는 접근 방식** - 통일된 방법 사용!

### ✅ 올바른 개발 워크플로우

#### 1. 코드 수정 전 검증
```python
# 수정 전에 항상 실행
from src.ui.utils.auto_validator import validate_edit, print_validation_report

result = validate_edit("target_file.py", "before")
print_validation_report(result)

if not result["can_proceed"]:
    print("❌ 수정을 중단합니다!")
    return
```

#### 2. 올바른 파일 구조
```
src/ui/
├── components/          # UI 컴포넌트들
│   ├── linear_components.py
│   ├── advanced_css_injector.py
│   └── ...
├── header_component.py  # 헤더 관련
├── chat_panel.py       # 채팅 관련
└── utils/              # 유틸리티
    ├── code_guard.py
    └── auto_validator.py
```

#### 3. 코드 수정 후 검증
```python
# 수정 후에 항상 실행
result = validate_edit("target_file.py", "after")
print_validation_report(result)

if not result["valid"]:
    print("❌ 수정이 필요합니다!")
    # 수정 제안에 따라 코드 수정
```

### 🎯 UI 관련 작업 규칙

#### ✅ 올바른 방법
- **UI 코드**: `src/ui/` 디렉토리에만 작성
- **CSS 주입**: `src/ui/components/advanced_css_injector.py` 사용
- **컴포넌트**: `src/ui/components/` 디렉토리에 모듈화
- **검증**: 수정 전후 반드시 검증 실행

#### ❌ 금지 사항
- **app.py에 UI 코드 추가** - 절대 금지!
- **src/ui/ 외부에서 UI 관련 코드 작성** - 구조 위반!
- **검증 없이 코드 수정** - 실수 유발!
- **일관성 없는 접근** - 혼란 야기!

### 🔧 자동 검증 도구 사용법

#### 1. 전체 검사
```python
from src.ui.utils.code_guard import run_code_guard, print_guard_report

result = run_code_guard()
print_guard_report(result)
```

#### 2. 개별 파일 검증
```python
from src.ui.utils.auto_validator import validate_edit, print_validation_report

# 수정 전
result = validate_edit("app.py", "before")
print_validation_report(result)

# 수정 후
result = validate_edit("src/ui/header_component.py", "after")
print_validation_report(result)
```

### 📋 체크리스트

#### 코드 수정 전
- [ ] 수정할 파일이 올바른 디렉토리에 있는가?
- [ ] app.py에 UI 코드를 추가하려는가? (금지!)
- [ ] src/ui/ 구조를 준수하는가?
- [ ] 자동 검증을 실행했는가?

#### 코드 수정 후
- [ ] 수정 후 검증을 실행했는가?
- [ ] 모든 검증을 통과했는가?
- [ ] 실제 작동을 확인했는가?
- [ ] 일관성 있는 접근 방식을 사용했는가?

### 🚀 성공적인 개발 패턴

#### 1. CSS 스타일링
```python
# ✅ 올바른 방법
# src/ui/components/advanced_css_injector.py에서
def inject_neumorphism_styles():
    # CSS 주입 로직
    pass

# src/ui/header_component.py에서
def _inject_advanced_css(self):
    # CSS 주입 호출
    pass
```

#### 2. 컴포넌트 개발
```python
# ✅ 올바른 방법
# src/ui/components/new_component.py
class NewComponent:
    def render(self):
        # 컴포넌트 로직
        pass

# src/ui/header_component.py에서
from .components.new_component import NewComponent
```

#### 3. 검증 통합
```python
# ✅ 모든 수정에 포함
def safe_edit(file_path: str, edit_function):
    # 수정 전 검증
    before_result = validate_edit(file_path, "before")
    if not before_result["can_proceed"]:
        return False
    
    # 수정 실행
    edit_function()
    
    # 수정 후 검증
    after_result = validate_edit(file_path, "after")
    if not after_result["valid"]:
        # 자동 수정 시도
        return False
    
    return True
```

### 🎯 핵심 원칙

1. **구조 준수**: src/ui/ 디렉토리 구조 반드시 준수
2. **검증 필수**: 모든 수정 전후 검증 실행
3. **일관성 유지**: 통일된 접근 방식 사용
4. **자동화 활용**: 검증 도구 적극 활용

### 📞 문제 발생 시

1. **자동 검증 실행**: `run_code_guard()` 실행
2. **문제 분석**: 리포트에서 문제점 확인
3. **수정 제안 따르기**: 제안된 수정 방법 적용
4. **재검증**: 수정 후 다시 검증 실행

---

**🛡️ 이 가이드를 따르면 반복적인 실수를 방지할 수 있습니다!**




