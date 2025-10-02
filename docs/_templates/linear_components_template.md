# Linear 컴포넌트 시스템 템플릿

이 템플릿을 사용하여 다른 프로젝트에서도 Linear 스타일 컴포넌트 시스템을 구축할 수 있습니다.

## 🚀 **설치 가이드**

### **1단계: 파일 구조 생성**
```
src/
├── ui/
│   ├── components/
│   │   ├── __init__.py
│   │   ├── linear_theme.py          # 테마 시스템
│   │   ├── linear_components.py     # 기본 컴포넌트
│   │   └── linear_layout_components.py  # 레이아웃 컴포넌트
│   └── utils/
│       └── __init__.py
pages/
└── components_demo.py               # 데모 페이지
.cursorrules                        # Cursor 규칙
```

### **2단계: 의존성 설치**
```bash
pip install streamlit
```

### **3단계: 테마 시스템 설정**
`src/ui/components/linear_theme.py` 파일을 복사하고 프로젝트에 맞게 수정하세요.

### **4단계: 컴포넌트 시스템 설정**
`src/ui/components/linear_components.py`와 `linear_layout_components.py`를 복사하세요.

### **5단계: Cursor 규칙 적용**
`.cursorrules` 파일을 프로젝트 루트에 복사하세요.

## 🎨 **커스터마이징 가이드**

### **색상 테마 변경**
`linear_theme.py`의 `LINEAR_THEME` 딕셔너리를 수정하세요:

```python
LINEAR_THEME = {
    "colors": {
        "primary": {
            "brand": "#your-brand-color",      # 브랜드 색상
            "accent": "#your-accent-color",    # 강조 색상
        },
        "background": {
            "primary": "#your-bg-primary",     # 메인 배경
            "secondary": "#your-bg-secondary", # 보조 배경
        },
        # ... 더 많은 색상
    }
}
```

### **폰트 변경**
```python
"typography": {
    "fontFamily": {
        "primary": '"Your Font", "Fallback Font", sans-serif',
        "monospace": '"Your Mono Font", monospace'
    }
}
```

### **컴포넌트 수정**
각 컴포넌트의 CSS 클래스를 수정하여 프로젝트에 맞게 조정하세요.

## 📱 **모바일 최적화**

### **반응형 브레이크포인트**
```css
@media (max-width: 768px) {
    /* 모바일 스타일 */
}
```

### **터치 타겟 크기**
모든 버튼과 클릭 가능한 요소는 최소 44px 크기를 유지하세요.

## 🔧 **개발 워크플로우**

### **새 컴포넌트 추가**
1. `linear_components.py`에 새 함수 추가
2. CSS 스타일 정의
3. 데모 페이지에 예제 추가
4. `.cursorrules` 업데이트

### **컴포넌트 수정**
1. 기존 컴포넌트 수정
2. 모든 사용처에서 테스트
3. 데모 페이지 업데이트
4. 문서 업데이트

## 📋 **체크리스트**

프로젝트 설정 시 다음을 확인하세요:

- [ ] 테마 파일이 올바르게 설정되었는가?
- [ ] 모든 컴포넌트가 import 가능한가?
- [ ] 데모 페이지가 정상 작동하는가?
- [ ] 모바일에서 테스트했는가?
- [ ] Cursor 규칙이 적용되었는가?
- [ ] 팀원들이 컴포넌트 사용법을 이해하는가?

## 🎯 **사용 예제**

### **기본 페이지 템플릿**
```python
import streamlit as st
from src.ui.components.linear_theme import apply_theme
from src.ui.components.linear_components import (
    linear_button, linear_card, linear_alert
)
from src.ui.components.linear_layout_components import (
    linear_navbar, linear_footer
)

def main():
    # 테마 적용 (필수)
    apply_theme()
    
    # 네비게이션 바
    linear_navbar(
        brand_name="My App",
        nav_items=[{"label": "홈", "href": "/", "active": True}]
    )
    
    # 메인 콘텐츠
    linear_card(
        title="환영합니다",
        content=st.markdown("내용을 입력하세요.")
    )
    
    # 버튼
    if linear_button("클릭하세요", variant="primary"):
        linear_alert("버튼이 클릭되었습니다!", variant="success")
    
    # 푸터
    linear_footer(
        copyright_text="© 2025 My App. All rights reserved."
    )

if __name__ == "__main__":
    main()
```

## 🔄 **업데이트 가이드**

새로운 Linear 컴포넌트가 추가되면:

1. **테마 파일 업데이트**: 새로운 CSS 변수 추가
2. **컴포넌트 파일 업데이트**: 새 컴포넌트 추가
3. **데모 페이지 업데이트**: 사용 예제 추가
4. **문서 업데이트**: 사용법 가이드 추가
5. **Cursor 규칙 업데이트**: 새 컴포넌트 규칙 추가

## 🎨 **디자인 시스템 확장**

### **새로운 컴포넌트 추가**
```python
def linear_new_component(
    title: str,
    variant: str = "default",
    **kwargs
) -> None:
    """
    새로운 Linear 컴포넌트
    
    Args:
        title: 컴포넌트 제목
        variant: 스타일 변형
    """
    if st is None:
        return
    
    # CSS 스타일
    css = f"""
    <style>
    .linear-new-component-{variant} {{
        font-family: var(--linear-font-primary) !important;
        background: var(--linear-bg-secondary) !important;
        border: 1px solid var(--linear-border-primary) !important;
        border-radius: var(--linear-radius-medium) !important;
        padding: var(--linear-padding-medium) !important;
    }}
    </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)
    
    # 컴포넌트 렌더링
    st.markdown(f'<div class="linear-new-component-{variant}">{title}</div>', unsafe_allow_html=True)
```

이 템플릿을 사용하여 어떤 프로젝트에서든 Linear 스타일의 일관된 UI/UX를 구축할 수 있습니다.
