"""
Chat UI Styles Module

Contains all chat-related styles:
- Chat pane styles
- Message bubble styles
- Input form styles
- Chip/badge styles
"""

import streamlit as st


def inject_chat_styles():
    """Inject chat-related styles including bubbles, input forms, and chips."""
    if st.session_state.get("_chat_styles_injected"):
        return
    
    st.session_state["_chat_styles_injected"] = True
    
    st.markdown(
        """
        <style>
        /* ▶ 채팅 영역 컨테이너 */
        .chatpane-messages, .chatpane-input{
          position:relative; background:transparent; border:none; border-radius:18px;
          padding:10px; margin-top:12px;
        }
        .chatpane-input div[data-testid="stRadio"]{ background:#EDF4FF; padding:8px 10px 0 10px; margin:0; }
        .chatpane-input div[data-testid="stRadio"] > div[role="radiogroup"]{ display:flex; gap:10px; flex-wrap:wrap; }
        .chatpane-input div[data-testid="stRadio"] [role="radio"]{
          border:2px solid #bcdcff; border-radius:12px; padding:6px 12px; background:#fff; color:#0a2540;
          font-weight:700; font-size:14px; line-height:1;
        }
        .chatpane-input div[data-testid="stRadio"] [role="radio"][aria-checked="true"]{
          background:#eaf6ff; border-color:#9fd1ff; color:#0a2540;
        }
        .chatpane-input div[data-testid="stRadio"] svg{ display:none!important }

        /* 입력 폼/버튼은 입력 컨테이너 하위로만 적용 */
        .chatpane-input form[data-testid="stForm"] { position:relative; margin:0; }
        .chatpane-input form[data-testid="stForm"] [data-testid="stTextInput"] input{
          background:#FFF8CC !important; border:1px solid #F2E4A2 !important;
          border-radius:999px !important; color:#333 !important; height:46px; padding-right:56px;
        }
        .chatpane-input form[data-testid="stForm"] ::placeholder{ color:#8A7F4A !important; }
        .chatpane-input form[data-testid="stForm"] .stButton,
        .chatpane-input form[data-testid="stForm"] .row-widget.stButton{
          position:absolute; right:14px; top:50%; transform:translateY(-50%);
          z-index:2; margin:0!important; padding:0!important;
        }
        .chatpane-input form[data-testid="stForm"] .stButton > button,
        .chatpane-input form[data-testid="stForm"] .row-widget.stButton > button{
          width:38px; height:38px; border-radius:50%; border:0; background:#0a2540; color:#fff;
          font-size:18px; line-height:1; cursor:pointer; box-shadow:0 2px 6px rgba(0,0,0,.15);
          padding:0; min-height:0;
        }

        /* ▶ 버블/칩 (글로벌) */
        .msg-row{ display:flex; margin:8px 0; }
        .msg-row.left{ justify-content:flex-start; }
        .msg-row.right{ justify-content:flex-end; }
        .bubble{
          max-width:88%; padding:10px 12px; border-radius:16px; line-height:1.6; font-size:15px;
          box-shadow:0 1px 1px rgba(0,0,0,.05); white-space:pre-wrap; position:relative;
        }
        .bubble.user{ border-top-right-radius:8px; border:1px solid #F2E4A2; background:#FFF8CC; color:#333; }
        .bubble.ai  { border-top-left-radius:8px;  border:1px solid #BEE3FF; background:#EAF6FF; color:#0a2540; }

        .chip{
          display:inline-block; margin:-2px 0 6px 0; padding:2px 10px; border-radius:999px;
          font-size:12px; font-weight:700; color:#fff; line-height:1;
        }
        .chip.me{ background:#059669; }
        .chip.pt{ background:#2563eb; }
        .chip.mn{ background:#7c3aed; }
        .chip-src{
          display:inline-block; margin-left:6px; padding:2px 8px; border-radius:10px;
          background:#eef2ff; color:#3730a3; font-size:12px; font-weight:600; line-height:1;
          border:1px solid #c7d2fe; max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
          vertical-align:middle;
        }

        /* ▶ 프롬프트/페르소나 대형 입력영역 */
        .prompt-editor .stTextArea textarea{
          min-height:260px !important; line-height:1.45; font-size:14px;
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
        }
        .prompt-editor .persona-title, .prompt-editor .inst-title{
          font-weight:800; margin:6px 0 4px 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
