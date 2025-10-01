#!/usr/bin/env python3
# HTML 렌더링 테스트

import streamlit as st

st.title("HTML 렌더링 테스트")

# 기본 HTML 테스트
st.markdown('<div style="color: red; font-size: 20px;">빨간색 텍스트 테스트</div>', unsafe_allow_html=True)

# 복잡한 HTML 테스트
html_content = """
<div style="background: #f0f0f0; padding: 20px; border-radius: 10px;">
    <h3>HTML 렌더링 테스트</h3>
    <p>이 텍스트가 제대로 표시되면 HTML 렌더링이 작동합니다.</p>
    <button onclick="alert('버튼 클릭!')">테스트 버튼</button>
</div>
"""

st.markdown(html_content, unsafe_allow_html=True)

st.write("위의 HTML이 제대로 렌더링되었나요?")
