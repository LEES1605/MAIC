# Linear 컴포넌트 라이브러리 데모 페이지
from __future__ import annotations

import streamlit as st

# Linear 테마 및 컴포넌트 import
try:
    from src.ui.components.linear_theme import apply_theme
    from src.ui.components.linear_components import (
        linear_button, linear_card, linear_badge, 
        linear_input, linear_alert, linear_divider,
        linear_carousel, linear_card_with_image, linear_navbar
    )
    from src.ui.components.linear_layout_components import (
        linear_footer, linear_hero
    )
    from src.ui.utils.sider import render_sidebar
except Exception as e:
    st.error(f"컴포넌트 로드 오류: {e}")
    st.stop()


def main() -> None:
    """Linear 컴포넌트 라이브러리 데모 페이지"""
    
    # 사이드바 렌더링
    render_sidebar()
    
    # Linear 테마 적용
    apply_theme()
    
    # 페이지 헤더
    st.markdown("# 🎨 Linear 컴포넌트 라이브러리")
    st.markdown("Linear.app에서 영감을 받은 모던하고 재사용 가능한 UI 컴포넌트들입니다.")
    
    linear_divider()
    
    # 1. 버튼 컴포넌트 데모
    st.markdown("## 🔘 버튼 (Button)")
    st.markdown("다양한 스타일과 크기의 버튼 컴포넌트입니다.")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("**Primary 버튼**")
        if linear_button("Primary", variant="primary"):
            st.success("Primary 버튼이 클릭되었습니다!")
    
    with col2:
        st.markdown("**Secondary 버튼**")
        if linear_button("Secondary", variant="secondary"):
            st.info("Secondary 버튼이 클릭되었습니다!")
    
    with col3:
        st.markdown("**Success 버튼**")
        if linear_button("Success", variant="success"):
            st.success("Success 버튼이 클릭되었습니다!")
    
    with col4:
        st.markdown("**Danger 버튼**")
        if linear_button("Danger", variant="danger"):
            st.error("Danger 버튼이 클릭되었습니다!")
    
    # 버튼 크기 데모
    st.markdown("**버튼 크기**")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        linear_button("Small", variant="primary", size="small")
    with col2:
        linear_button("Medium", variant="primary", size="medium")
    with col3:
        linear_button("Large", variant="primary", size="large")
    
    linear_divider()
    
    # 2. 카드 컴포넌트 데모
    st.markdown("## 📦 카드 (Card)")
    st.markdown("내용을 그룹화하고 시각적으로 구분하는 카드 컴포넌트입니다.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        linear_card(
            title="기본 카드",
            content=st.markdown("""
            이것은 기본 카드입니다. 
            
            - 내용을 체계적으로 정리
            - 시각적 구분 제공
            - 반응형 레이아웃 지원
            """),
            variant="default"
        )
    
    with col2:
        linear_card(
            title="강조 카드",
            content=st.markdown("""
            이것은 강조된 카드입니다.
            
            - 더 강한 그림자 효과
            - 시각적 계층 구조
            - 중요한 내용 강조
            """),
            variant="elevated"
        )
    
    # 카드 없이도 사용 가능
    with st.container():
        st.markdown("**카드 없이 컨텐츠만**")
        linear_card(
            content=st.markdown("카드 제목 없이 내용만 표시할 수도 있습니다."),
            variant="outlined"
        )
    
    linear_divider()
    
    # 3. 배지 컴포넌트 데모
    st.markdown("## 🏷️ 배지 (Badge)")
    st.markdown("상태, 카테고리, 라벨 등을 표시하는 작은 컴포넌트입니다.")
    
    st.markdown("**배지 종류**")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        linear_badge("Default", variant="default")
    with col2:
        linear_badge("Success", variant="success")
    with col3:
        linear_badge("Warning", variant="warning")
    with col4:
        linear_badge("Danger", variant="danger")
    with col5:
        linear_badge("Info", variant="info")
    
    st.markdown("**배지 크기**")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        linear_badge("Small", variant="success", size="small")
    with col2:
        linear_badge("Medium", variant="success", size="medium")
    with col3:
        linear_badge("Large", variant="success", size="large")
    
    linear_divider()
    
    # 4. 입력 컴포넌트 데모
    st.markdown("## 📝 입력 (Input)")
    st.markdown("Linear 스타일의 입력 필드 컴포넌트입니다.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**텍스트 입력**")
        name = linear_input("이름", placeholder="이름을 입력하세요")
        if name:
            st.info(f"입력된 이름: {name}")
    
    with col2:
        st.markdown("**비밀번호 입력**")
        password = linear_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")
        if password:
            st.info("비밀번호가 입력되었습니다.")
    
    # 숫자 입력
    st.markdown("**숫자 입력**")
    col1, col2 = st.columns(2)
    
    with col1:
        age = linear_input("나이", type="number", placeholder="나이를 입력하세요")
        if age:
            st.info(f"입력된 나이: {age}")
    
    with col2:
        linear_input("비활성화된 입력", disabled=True, placeholder="비활성화됨")
    
    linear_divider()
    
    # 5. 알림 컴포넌트 데모
    st.markdown("## 🔔 알림 (Alert)")
    st.markdown("사용자에게 중요한 정보나 상태를 알리는 알림 컴포넌트입니다.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        linear_alert("정보 알림입니다. 중요한 정보를 전달합니다.", variant="info")
        linear_alert("성공! 작업이 완료되었습니다.", variant="success")
    
    with col2:
        linear_alert("경고! 확인이 필요한 항목이 있습니다.", variant="warning")
        linear_alert("오류가 발생했습니다. 다시 시도해주세요.", variant="danger")
    
    linear_divider()
    
    # 6. 구분선 컴포넌트 데모
    st.markdown("## ➖ 구분선 (Divider)")
    st.markdown("내용을 시각적으로 구분하는 구분선 컴포넌트입니다.")
    
    st.markdown("위 내용")
    linear_divider()
    st.markdown("아래 내용")
    
    st.markdown("라벨이 있는 구분선")
    linear_divider("섹션 구분")
    st.markdown("구분선 아래 내용")
    
    linear_divider()
    
    # 7. 네비게이션 바 컴포넌트 데모
    st.markdown("## 🧭 네비게이션 바 (Navbar)")
    st.markdown("전체 너비를 차지하는 Linear 스타일 네비게이션 바입니다.")
    
    # 네비게이션 아이템 데이터
    nav_items = [
        {"label": "홈", "href": "/", "active": True},
        {"label": "컴포넌트", "href": "/components", "active": False},
        {"label": "문서", "href": "/docs", "active": False},
        {"label": "소개", "href": "/about", "active": False}
    ]
    
    # 사용자 메뉴 데이터
    user_menu = {
        "name": "사용자",
        "avatar": "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=32&h=32&fit=crop&crop=face"
    }
    
    linear_navbar(
        brand_name="Linear App",
        nav_items=nav_items,
        user_menu=user_menu,
        sticky=True,
        key="demo_navbar"
    )
    
    # 8. 히어로 컴포넌트 데모
    st.markdown("## 🦸 히어로 섹션 (Hero)")
    st.markdown("전체 너비를 차지하는 임팩트 있는 히어로 섹션입니다.")
    
    # 히어로 특징들
    hero_features = [
        "모던한 디자인",
        "반응형 레이아웃", 
        "Linear 스타일",
        "다크 테마"
    ]
    
    # CTA 버튼 데이터
    cta_button = {
        "text": "시작하기",
        "variant": "primary"
    }
    
    linear_hero(
        title="Linear 스타일 컴포넌트",
        subtitle="Linear.app에서 영감을 받은 모던하고 재사용 가능한 UI 컴포넌트 라이브러리입니다. 다크 테마와 세련된 디자인으로 사용자 경험을 향상시킵니다.",
        background_image="https://images.unsplash.com/photo-1558618047-3c8c76ca7d13?w=1200&h=400&fit=crop",
        cta_button=cta_button,
        features=hero_features,
        variant="centered",
        key="demo_hero"
    )
    
    # 9. 캐러셀 컴포넌트 데모
    st.markdown("## 🎠 캐러셀 (Carousel)")
    st.markdown("이미지와 텍스트를 포함한 인터랙티브 캐러셀 컴포넌트입니다.")
    
    # 캐러셀 아이템 데이터
    carousel_items = [
        {
            "title": "첫 번째 슬라이드",
            "content": "Linear 스타일의 첫 번째 캐러셀 아이템입니다. 세련된 디자인과 부드러운 애니메이션을 제공합니다.",
            "image": "https://images.unsplash.com/photo-1558618047-3c8c76ca7d13?w=400",
            "action": "자세히 보기"
        },
        {
            "title": "두 번째 슬라이드", 
            "content": "이미지와 텍스트가 조화롭게 배치된 두 번째 슬라이드입니다. 모바일 친화적인 레이아웃을 지원합니다.",
            "image": "https://images.unsplash.com/photo-1558618047-3c8c76ca7d13?w=400",
            "action": "시작하기"
        },
        {
            "title": "세 번째 슬라이드",
            "content": "마지막 슬라이드입니다. 모든 기능이 완벽하게 작동하며 사용자 경험을 향상시킵니다.",
            "image": "https://images.unsplash.com/photo-1558618047-3c8c76ca7d13?w=400",
            "action": "완료"
        }
    ]
    
    linear_carousel(
        items=carousel_items,
        title="Linear 캐러셀 데모",
        show_dots=True,
        show_arrows=True,
        key="demo_carousel"
    )
    
    # 8. 이미지 카드 컴포넌트 데모
    st.markdown("## 🖼️ 이미지 카드 (Card with Image)")
    st.markdown("이미지가 포함된 다양한 레이아웃의 카드 컴포넌트입니다.")
    
    # 이미지 위치별 데모
    st.write("**이미지 위쪽 배치:**")
    linear_card_with_image(
        title="Linear 스타일 이미지 카드",
        content="이미지가 카드 상단에 배치된 예제입니다. 제목과 내용이 이미지 아래에 표시됩니다.",
        image_url="https://images.unsplash.com/photo-1558618047-3c8c76ca7d13?w=400",
        image_alt="Linear 스타일 이미지",
        variant="elevated",
        image_position="top",
        action_button="자세히 보기"
    )
    
    st.write("**이미지 왼쪽 배치:**")
    linear_card_with_image(
        title="좌측 이미지 레이아웃",
        content="이미지가 왼쪽에, 텍스트가 오른쪽에 배치된 레이아웃입니다. 더 많은 텍스트를 표시할 수 있습니다.",
        image_url="https://images.unsplash.com/photo-1558618047-3c8c76ca7d13?w=300",
        image_alt="좌측 이미지",
        variant="default",
        image_position="left",
        action_button="읽기"
    )
    
    st.write("**이미지 오른쪽 배치:**")
    linear_card_with_image(
        title="우측 이미지 레이아웃",
        content="텍스트가 왼쪽에, 이미지가 오른쪽에 배치된 레이아웃입니다.",
        image_url="https://images.unsplash.com/photo-1558618047-3c8c76ca7d13?w=300",
        image_alt="우측 이미지",
        variant="outlined",
        image_position="right",
        action_button="보기"
    )
    
    linear_divider()
    
    # 9. 사용법 예제
    st.markdown("## 💻 사용법 예제")
    st.markdown("컴포넌트 사용법과 코드 예제입니다.")
    
    with st.expander("버튼 사용법", expanded=False):
        st.code("""
from src.ui.components.linear_components import linear_button

# 기본 버튼
if linear_button("클릭하세요"):
    st.success("버튼이 클릭되었습니다!")

# 다양한 스타일
linear_button("Primary", variant="primary")
linear_button("Secondary", variant="secondary") 
linear_button("Success", variant="success")
linear_button("Danger", variant="danger")

# 다양한 크기
linear_button("Small", size="small")
linear_button("Medium", size="medium")
linear_button("Large", size="large")
        """, language="python")
    
    with st.expander("카드 사용법", expanded=False):
        st.code("""
from src.ui.components.linear_components import linear_card

# 기본 카드
linear_card(
    title="카드 제목",
    content=st.markdown("카드 내용"),
    variant="default"
)

# 강조 카드
linear_card(
    content=st.markdown("강조된 내용"),
    variant="elevated"
)
        """, language="python")
    
    with st.expander("배지 사용법", expanded=False):
        st.code("""
from src.ui.components.linear_components import linear_badge

# 다양한 배지
linear_badge("Default", variant="default")
linear_badge("Success", variant="success")
linear_badge("Warning", variant="warning")
linear_badge("Danger", variant="danger")
linear_badge("Info", variant="info")

# 다양한 크기
linear_badge("Small", size="small")
linear_badge("Medium", size="medium")
linear_badge("Large", size="large")
        """, language="python")
    
    with st.expander("캐러셀 사용법", expanded=False):
        st.code("""
from src.ui.components.linear_components import linear_carousel

# 캐러셀 아이템 데이터
carousel_items = [
    {
        "title": "슬라이드 제목",
        "content": "슬라이드 내용",
        "image": "이미지_URL",
        "action": "버튼 텍스트"
    },
    # ... 더 많은 아이템
]

# 캐러셀 렌더링
linear_carousel(
    items=carousel_items,
    title="캐러셀 제목",
    show_dots=True,
    show_arrows=True,
    key="my_carousel"
)
        """, language="python")
    
    with st.expander("이미지 카드 사용법", expanded=False):
        st.code("""
from src.ui.components.linear_components import linear_card_with_image

# 이미지가 위쪽에 배치된 카드
linear_card_with_image(
    title="카드 제목",
    content="카드 내용",
    image_url="이미지_URL",
    image_alt="이미지 설명",
    variant="elevated",
    image_position="top",
    action_button="버튼 텍스트"
)

# 이미지가 왼쪽에 배치된 카드
linear_card_with_image(
    title="카드 제목",
    content="카드 내용",
    image_url="이미지_URL",
    variant="default",
    image_position="left",
    action_button="버튼 텍스트"
)

# 이미지가 오른쪽에 배치된 카드
linear_card_with_image(
    title="카드 제목", 
    content="카드 내용",
    image_url="이미지_URL",
    variant="outlined",
    image_position="right",
    action_button="버튼 텍스트"
)
        """, language="python")
    
    # 11. 푸터 컴포넌트 데모
    st.markdown("## 🔽 푸터 (Footer)")
    st.markdown("전체 너비를 차지하는 Linear 스타일 푸터입니다.")
    
    # 푸터 링크 데이터
    footer_links = [
        {"label": "개인정보처리방침", "href": "/privacy"},
        {"label": "이용약관", "href": "/terms"},
        {"label": "문의하기", "href": "/contact"}
    ]
    
    # 소셜 링크 데이터
    social_links = [
        {"label": "GitHub", "href": "https://github.com", "icon": "🐙"},
        {"label": "Twitter", "href": "https://twitter.com", "icon": "🐦"},
        {"label": "LinkedIn", "href": "https://linkedin.com", "icon": "💼"}
    ]
    
    linear_footer(
        copyright_text="© 2025 Linear App. All rights reserved.",
        links=footer_links,
        social_links=social_links,
        variant="default",
        key="demo_footer"
    )
    
    # 12. 사용법 예제 추가
    with st.expander("네비게이션 바 사용법", expanded=False):
        st.code("""
from src.ui.components.linear_components import linear_navbar

# 네비게이션 아이템
nav_items = [
    {"label": "홈", "href": "/", "active": True},
    {"label": "서비스", "href": "/services", "active": False},
    {"label": "문서", "href": "/docs", "active": False}
]

# 사용자 메뉴
user_menu = {
    "name": "사용자명",
    "avatar": "아바타_URL"
}

# 네비게이션 바 렌더링
linear_navbar(
    brand_name="My App",
    nav_items=nav_items,
    user_menu=user_menu,
    sticky=True
)
        """, language="python")
    
    with st.expander("히어로 섹션 사용법", expanded=False):
        st.code("""
from src.ui.components.linear_layout_components import linear_hero

# 특징 리스트
features = ["특징 1", "특징 2", "특징 3"]

# CTA 버튼
cta_button = {
    "text": "시작하기",
    "variant": "primary"
}

# 히어로 섹션 렌더링
linear_hero(
    title="메인 제목",
    subtitle="부제목이나 설명",
    background_image="배경_이미지_URL",
    cta_button=cta_button,
    features=features,
    variant="centered"
)
        """, language="python")
    
    with st.expander("푸터 사용법", expanded=False):
        st.code("""
from src.ui.components.linear_layout_components import linear_footer

# 링크들
links = [
    {"label": "개인정보처리방침", "href": "/privacy"},
    {"label": "이용약관", "href": "/terms"}
]

# 소셜 링크들
social_links = [
    {"label": "GitHub", "href": "https://github.com", "icon": "🐙"},
    {"label": "Twitter", "href": "https://twitter.com", "icon": "🐦"}
]

# 푸터 렌더링
linear_footer(
    copyright_text="© 2025 My App. All rights reserved.",
    links=links,
    social_links=social_links
)
        """, language="python")
    
    # 13. 테마 정보
    linear_divider()
    st.markdown("## 🎨 테마 정보")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**주요 색상**")
        st.markdown("- **브랜드**: `#5e6ad2`")
        st.markdown("- **배경**: `#08090a`, `#1c1c1f`, `#232326`")
        st.markdown("- **텍스트**: `#f7f8f8`, `#d0d6e0`, `#8a8f98`")
        st.markdown("- **의미론적**: `#4ea7fc`, `#eb5757`, `#4cb782`")
    
    with col2:
        st.markdown("**타이포그래피**")
        st.markdown("- **폰트**: Inter Variable")
        st.markdown("- **가중치**: 300, 400, 510, 590, 680")
        st.markdown("- **크기**: 0.6875rem ~ 2.25rem")
        st.markdown("- **간격**: 4px ~ 24px")
    
    st.markdown("**Linear.app에서 영감을 받은 모던한 디자인 시스템으로, 일관성 있고 재사용 가능한 컴포넌트를 제공합니다.**")


if __name__ == "__main__":
    main()
