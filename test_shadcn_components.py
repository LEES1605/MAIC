"""
streamlit-shadcn-ui 컴포넌트 테스트 및 탐색
"""
import streamlit as st
from streamlit_shadcn_ui import button, card, input, alert_dialog, badges, avatar

# 페이지 설정
st.set_page_config(
    page_title="shadcn-ui 컴포넌트 테스트",
    page_icon="🎨",
    layout="wide"
)

st.title("🎨 streamlit-shadcn-ui 컴포넌트 테스트")

# 1. 버튼 컴포넌트 테스트
st.header("1. 버튼 컴포넌트")
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("기본 버튼")
    if button("기본 버튼", key="btn1"):
        st.success("기본 버튼 클릭됨!")

with col2:
    st.subheader("변형 버튼")
    if button("변형 버튼", variant="destructive", key="btn2"):
        st.error("변형 버튼 클릭됨!")

with col3:
    st.subheader("아웃라인 버튼")
    if button("아웃라인 버튼", variant="outline", key="btn3"):
        st.info("아웃라인 버튼 클릭됨!")

# 2. 카드 컴포넌트 테스트
st.header("2. 카드 컴포넌트")
col1, col2 = st.columns(2)

with col1:
    st.subheader("기본 카드")
    with card(key="card1"):
        st.write("이것은 기본 카드입니다.")
        st.write("여러 줄의 내용을 포함할 수 있습니다.")

with col2:
    st.subheader("제목이 있는 카드")
    with card(key="card2", title="카드 제목"):
        st.write("제목이 있는 카드입니다.")
        if button("카드 내 버튼", key="btn4"):
            st.success("카드 내 버튼 클릭됨!")

# 3. 입력 컴포넌트 테스트
st.header("3. 입력 컴포넌트")
col1, col2 = st.columns(2)

with col1:
    st.subheader("기본 입력")
    text_value = input("텍스트 입력", key="input1")
    if text_value:
        st.write(f"입력된 값: {text_value}")

with col2:
    st.subheader("비밀번호 입력")
    password_value = input("비밀번호", type="password", key="input2")
    if password_value:
        st.write("비밀번호가 입력되었습니다.")

# 4. 알림 다이얼로그 컴포넌트 테스트
st.header("4. 알림 다이얼로그 컴포넌트")
col1, col2 = st.columns(2)

with col1:
    st.subheader("알림 다이얼로그")
    if button("알림 다이얼로그 열기", key="alert_btn"):
        alert_dialog(
            title="알림",
            description="이것은 shadcn-ui 알림 다이얼로그입니다.",
            confirm_label="확인",
            cancel_label="취소"
        )

with col2:
    st.subheader("커스텀 알림")
    if button("커스텀 알림", key="custom_alert_btn"):
        alert_dialog(
            title="커스텀 알림",
            description="사용자 정의 메시지입니다.",
            confirm_label="좋아요",
            cancel_label="싫어요"
        )

# 5. 배지 컴포넌트 테스트
st.header("5. 배지 컴포넌트")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.subheader("기본 배지")
    badges([("기본 배지", "default")])

with col2:
    st.subheader("성공 배지")
    badges([("성공 배지", "default")])

with col3:
    st.subheader("경고 배지")
    badges([("경고 배지", "destructive")])

with col4:
    st.subheader("정보 배지")
    badges([("정보 배지", "default")])

# 6. 아바타 컴포넌트 테스트
st.header("6. 아바타 컴포넌트")
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("기본 아바타")
    avatar("사용자", fallback="U")

with col2:
    st.subheader("이미지 아바타")
    avatar("이미지", fallback="I", image="https://via.placeholder.com/40")

with col3:
    st.subheader("크기 조정")
    avatar("큰 아바타", fallback="L", size="lg")

# 7. 구분선 컴포넌트 테스트 (Streamlit 기본 사용)
st.header("7. 구분선 컴포넌트")
st.write("위쪽 내용")
st.divider()
st.write("아래쪽 내용")

# 8. Neumorphism 스타일 적용 가능성 테스트
st.header("8. Neumorphism 스타일 적용 가능성")
st.write("shadcn-ui 컴포넌트에 Neumorphism 스타일을 적용해보겠습니다.")

# CSS 주입으로 Neumorphism 스타일 적용
st.markdown("""
<style>
/* Neumorphism 배경 */
[data-testid="stApp"] {
    background: linear-gradient(135deg, #2c2f48 0%, #1a1d2e 100%) !important;
    color: #c1c3e0 !important;
    font-family: 'Poppins', sans-serif !important;
}

/* shadcn-ui 버튼에 Neumorphism 스타일 적용 */
button[data-testid="baseButton-secondary"] {
    background: rgba(44, 47, 72, 0.8) !important;
    border: none !important;
    border-radius: 15px !important;
    color: #c1c3e0 !important;
    box-shadow: 
        8px 8px 16px rgba(0, 0, 0, 0.3),
        -8px -8px 16px rgba(255, 255, 255, 0.1) !important;
    transition: all 0.3s ease !important;
}

button[data-testid="baseButton-secondary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 
        12px 12px 24px rgba(0, 0, 0, 0.4),
        -12px -12px 24px rgba(255, 255, 255, 0.15) !important;
}

/* shadcn-ui 카드에 Neumorphism 스타일 적용 */
div[data-testid="stCard"] {
    background: rgba(44, 47, 72, 0.9) !important;
    border-radius: 20px !important;
    box-shadow: 
        8px 8px 16px rgba(0, 0, 0, 0.3),
        -8px -8px 16px rgba(255, 255, 255, 0.1) !important;
    border: none !important;
}

/* shadcn-ui 입력 필드에 Neumorphism 스타일 적용 */
input[data-testid="stTextInput"] {
    background: rgba(44, 47, 72, 0.8) !important;
    border-radius: 15px !important;
    color: #c1c3e0 !important;
    border: none !important;
    box-shadow: 
        inset 8px 8px 16px rgba(0, 0, 0, 0.3),
        inset -8px -8px 16px rgba(255, 255, 255, 0.1) !important;
}
</style>
""", unsafe_allow_html=True)

st.success("🎉 shadcn-ui 컴포넌트 테스트 완료!")
st.info("Neumorphism 스타일이 적용된 shadcn-ui 컴포넌트들을 확인해보세요!")
