import streamlit as st

# 직접 CSS 주입 테스트
st.markdown("""
<style>
/* 숫자 입력 필드 테스트 */
.stNumberInput > div > div > input {
    border: 3px solid red !important;
    background: yellow !important;
}

/* 히어로 섹션 테스트 */
.test-hero {
    border-top: 5px solid blue !important;
    border-bottom: 5px solid blue !important;
    background: green !important;
    padding: 20px !important;
    margin: 10px 0 !important;
}
</style>
""", unsafe_allow_html=True)

st.title("컴포넌트 테스트")

# 숫자 입력 테스트
st.subheader("나이 입력 테스트")
age = st.number_input("나이", min_value=0, max_value=100, value=25)
st.write(f"입력된 나이: {age}")

# 히어로 섹션 테스트
st.subheader("히어로 섹션 테스트")
st.markdown("""
<div class="test-hero">
    <h2>테스트 히어로 섹션</h2>
    <p>이 섹션이 파란색 테두리와 초록색 배경으로 보여야 합니다.</p>
</div>
""", unsafe_allow_html=True)

# 네비게이션 바 테스트
st.subheader("네비게이션 바 테스트")
st.markdown("""
<div style="background: black; color: white; padding: 10px; display: flex; justify-content: space-between;">
    <div>브랜드</div>
    <div style="display: flex; gap: 20px;">
        <span>메뉴1</span>
        <span>메뉴2</span>
        <span>메뉴3</span>
    </div>
    <div>사용자</div>
</div>
""", unsafe_allow_html=True)

st.write("위의 요소들이 스타일이 적용되어 보이나요?")

