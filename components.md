# Linear 컴포넌트 시스템 - Cursor 규칙

## 🎨 **UI 컴포넌트 사용 규칙**

### **MUST USE - Linear 컴포넌트만 사용**
이 프로젝트에서는 **반드시** Linear 컴포넌트 시스템을 사용해야 합니다. Streamlit 기본 컴포넌트 대신 Linear 컴포넌트를 사용하세요.

#### **✅ 허용되는 컴포넌트:**
```python
# 기본 컴포넌트
from src.ui.components.linear_components import (
    linear_button,     # 버튼 (st.button 대신)
    linear_card,       # 카드 (st.container 대신)
    linear_badge,      # 배지/태그
    linear_input,      # 입력 필드
    linear_alert,      # 알림/경고
    linear_divider,    # 구분선
    linear_carousel,   # 캐러셀
    linear_card_with_image,  # 이미지 카드
    linear_navbar      # 네비게이션 바
)

# 레이아웃 컴포넌트
from src.ui.components.linear_layout_components import (
    linear_footer,     # 푸터
    linear_hero        # 히어로 섹션
)

# 테마 시스템
from src.ui.components.linear_theme import apply_theme
```

#### **❌ 금지되는 사용법:**
```python
# 절대 사용하지 마세요
st.button()           # ❌ linear_button() 사용
st.container()        # ❌ linear_card() 사용
st.success()          # ❌ linear_alert() 사용
st.warning()          # ❌ linear_alert() 사용
st.error()            # ❌ linear_alert() 사용
st.info()             # ❌ linear_alert() 사용
st.markdown("---")    # ❌ linear_divider() 사용
```

### **🎯 컴포넌트 사용 가이드**

#### **1. 버튼 컴포넌트**
```python
# ✅ 올바른 사용법
if linear_button("클릭하세요", variant="primary", size="medium"):
    # 액션 처리
    pass

# 버튼 변형: primary, secondary, success, danger
# 버튼 크기: small, medium, large
```

#### **2. 카드 컴포넌트**
```python
# ✅ 올바른 사용법
linear_card(
    title="카드 제목",
    content=st.markdown("카드 내용"),
    variant="elevated",  # default, elevated, outlined
    padding="large"      # small, medium, large, xlarge
)

# 이미지가 포함된 카드
linear_card_with_image(
    title="이미지 카드",
    content="카드 내용",
    image_url="이미지_URL",
    image_position="top",  # top, left, right, bottom
    action_button="버튼"
)
```

#### **3. 알림 컴포넌트**
```python
# ✅ 올바른 사용법
linear_alert("성공 메시지", variant="success")
linear_alert("경고 메시지", variant="warning")
linear_alert("오류 메시지", variant="danger")
linear_alert("정보 메시지", variant="info")
```

#### **4. 네비게이션 바**
```python
# ✅ 올바른 사용법 (전체 너비)
linear_navbar(
    brand_name="앱 이름",
    nav_items=[
        {"label": "홈", "href": "/", "active": True},
        {"label": "서비스", "href": "/services", "active": False}
    ],
    user_menu={"name": "사용자", "avatar": "아바타_URL"},
    sticky=True
)
```

#### **5. 히어로 섹션**
```python
# ✅ 올바른 사용법 (전체 너비)
linear_hero(
    title="메인 제목",
    subtitle="부제목",
    background_image="배경_이미지_URL",
    cta_button={"text": "시작하기", "variant": "primary"},
    features=["특징 1", "특징 2"],
    variant="centered"
)
```

#### **6. 캐러셀**
```python
# ✅ 올바른 사용법
carousel_items = [
    {
        "title": "슬라이드 제목",
        "content": "슬라이드 내용",
        "image": "이미지_URL",
        "action": "버튼 텍스트"
    }
]

linear_carousel(
    items=carousel_items,
    title="캐러셀 제목",
    show_dots=True,
    show_arrows=True
)
```

### **🎨 테마 시스템**

#### **반드시 적용해야 할 테마:**
```python
# 모든 페이지 상단에 반드시 추가
from src.ui.components.linear_theme import apply_theme

def main():
    # 테마 적용 (최우선)
    apply_theme()
    
    # 나머지 코드...
```

### **📱 반응형 디자인 원칙**

1. **모바일 우선**: 모든 컴포넌트는 모바일에서 먼저 테스트
2. **전체 너비**: Navbar, Hero, Footer는 반드시 전체 너비 사용
3. **Linear 스타일**: iOS Human Interface Guidelines 준수
4. **다크 테마**: Linear 다크 테마만 사용

### **🔧 개발 규칙**

#### **새 페이지 생성 시:**
1. `apply_theme()` 호출 (최우선)
2. Linear 컴포넌트만 사용
3. 전체 너비 컴포넌트 (Navbar, Hero, Footer) 적절히 배치
4. 모바일 반응형 테스트

#### **컴포넌트 수정 시:**
1. `src/ui/components/linear_components.py` 수정
2. `src/ui/components/linear_layout_components.py` 수정
3. `pages/20_components.py` 데모 업데이트
4. 모든 페이지에서 일관성 확인

### **📋 체크리스트**

페이지 생성/수정 시 다음을 확인하세요:

- [ ] `apply_theme()` 호출했는가?
- [ ] `st.button()` 대신 `linear_button()` 사용했는가?
- [ ] `st.success/warning/error/info()` 대신 `linear_alert()` 사용했는가?
- [ ] `st.container()` 대신 `linear_card()` 사용했는가?
- [ ] Navbar, Hero, Footer가 전체 너비를 차지하는가?
- [ ] 모바일에서 테스트했는가?
- [ ] Linear 다크 테마가 적용되었는가?

### **🚨 중요 알림**

이 규칙을 위반하면 코드 리뷰에서 **거부**됩니다. 
Linear 컴포넌트 시스템을 사용하지 않은 모든 코드는 수정이 필요합니다.

**목표**: Linear.app 수준의 일관되고 세련된 UI/UX 제공
**원칙**: 컴포넌트 재사용성과 유지보수성 최우선
