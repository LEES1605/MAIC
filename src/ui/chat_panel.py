"""
MAIC 채팅 패널 컴포넌트 모듈

app.py에서 분리된 채팅 패널 관련 로직을 담당합니다.
- 채팅 메시지 렌더링
- 스트리밍 응답 처리
- AI 에이전트 통합
"""

import html
import re
import importlib as _imp
from typing import Optional, Callable

from src.application.agents.responder import answer_stream
from src.application.agents.evaluator import evaluate_stream
from src.domain.llm.streaming import BufferOptions, make_stream_handler


class ChatPanelComponent:
    """채팅 패널 컴포넌트 클래스"""
    
    def __init__(self):
        self._st = None
        self._initialize_streamlit()
        self._initialize_rag_modules()
    
    def _initialize_streamlit(self):
        """Streamlit 초기화"""
        try:
            import streamlit as st
            self._st = st
        except ImportError:
            self._st = None
    
    def _initialize_rag_modules(self):
        """RAG 모듈 초기화"""
        try:
            try:
                _label_mod = _imp.import_module("src.rag.label")
            except Exception:
                _label_mod = _imp.import_module("label")
            self._decide_label = getattr(_label_mod, "decide_label", None)
            self._search_hits = getattr(_label_mod, "search_hits", None)
            self._make_chip = getattr(_label_mod, "make_source_chip", None)
        except Exception:
            self._decide_label = None
            self._search_hits = None
            self._make_chip = None
    
    def _resolve_sanitizer(self) -> Callable[[Optional[str]], str]:
        """소스 라벨 정제 함수 해결"""
        try:
            from src.application.modes.types import sanitize_source_label as _san
            return _san
        except Exception:
            try:
                mod = _imp.import_module("modes.types")
                fn = getattr(mod, "sanitize_source_label", None)
                if callable(fn):
                    return fn
            except Exception:
                pass

            def _fallback(label: Optional[str] = None) -> str:
                return "[AI지식]"

            return _fallback
    
    def _esc(self, t: str) -> str:
        """HTML 이스케이프"""
        s = html.escape(t or "").replace("\n", "<br/>")
        return re.sub(r"  ", "&nbsp;&nbsp;", s)
    
    def _chip_html(self, who: str) -> str:
        """사용자 칩 HTML 생성"""
        klass = {"나": "me", "피티쌤": "pt", "미나쌤": "mn"}.get(who, "pt")
        return f'<span class="chip {klass}">{html.escape(who)}</span>'
    
    def _src_html(self, label: Optional[str]) -> str:
        """소스 라벨 HTML 생성"""
        if not label:
            return ""
        return f'<span class="chip-src">{html.escape(label)}</span>'
    
    def _emit_bubble(self, placeholder, who: str, acc_text: str,
                     *, source: Optional[str], align_right: bool) -> None:
        """채팅 버블 렌더링"""
        side_cls = "right" if align_right else "left"
        klass = "user" if align_right else "ai"
        chips = self._chip_html(who) + (self._src_html(source) if not align_right else "")
        html_block = (
            f'<div class="msg-row {side_cls}">'
            f'  <div class="bubble {klass}">{chips}<br/>{self._esc(acc_text)}</div>'
            f"</div>"
        )
        placeholder.markdown(html_block, unsafe_allow_html=True)
    
    def _process_question(self, question: str) -> tuple[str, list, str]:
        """질문 처리 및 라벨 결정"""
        src_label = "[AI지식]"
        hits = []
        
        if callable(self._search_hits):
            try:
                hits = self._search_hits(question, top_k=5)
            except Exception:
                hits = []

        if callable(self._decide_label):
            try:
                src_label = self._decide_label(hits, default_if_none="[AI지식]")
            except Exception:
                src_label = "[AI지식]"

        sanitize_source_label = self._resolve_sanitizer()
        src_label = sanitize_source_label(src_label)

        chip_text = src_label
        if callable(self._make_chip):
            try:
                chip_text = self._make_chip(hits, src_label)
            except Exception:
                chip_text = src_label
        
        return src_label, hits, chip_text
    
    def _render_answer_stream(self, question: str, mode: str, chip_text: str) -> str:
        """답변 스트림 렌더링"""
        ph_ans = self._st.empty()
        acc_ans = ""

        def _on_emit_ans(chunk: str) -> None:
            nonlocal acc_ans
            acc_ans += str(chunk or "")
            self._emit_bubble(ph_ans, "피티쌤", acc_ans, source=chip_text, align_right=False)

        emit_chunk_ans, close_stream_ans = make_stream_handler(
            on_emit=_on_emit_ans,
            opts=BufferOptions(
                min_emit_chars=8, soft_emit_chars=24, max_latency_ms=150,
                flush_on_strong_punct=True, flush_on_newline=True,
            ),
        )
        
        for piece in answer_stream(question=question, mode=mode):
            emit_chunk_ans(str(piece or ""))
        close_stream_ans()
        
        return acc_ans.strip()
    
    def _render_evaluation_stream(self, question: str, mode: str, answer: str, chip_text: str) -> str:
        """평가 스트림 렌더링"""
        ph_eval = self._st.empty()
        acc_eval = ""

        def _on_emit_eval(chunk: str) -> None:
            nonlocal acc_eval
            acc_eval += str(chunk or "")
            self._emit_bubble(ph_eval, "미나쌤", acc_eval, source=chip_text, align_right=False)

        emit_chunk_eval, close_stream_eval = make_stream_handler(
            on_emit=_on_emit_eval,
            opts=BufferOptions(
                min_emit_chars=8, soft_emit_chars=24, max_latency_ms=150,
                flush_on_strong_punct=True, flush_on_newline=True,
            ),
        )
        
        for piece in evaluate_stream(
            question=question, mode=mode, answer=answer, ctx={"answer": answer}
        ):
            emit_chunk_eval(str(piece or ""))
        close_stream_eval()
        
        return acc_eval.strip()
    
    def render(self) -> None:
        """채팅 패널 렌더링"""
        if self._st is None:
            return
        
        ss = self._st.session_state
        question = str(ss.get("inpane_q", "") or "").strip()
        if not question:
            return

        # 질문 처리 및 라벨 결정
        src_label, hits, chip_text = self._process_question(question)

        # 사용자 질문 표시
        ph_user = self._st.empty()
        self._emit_bubble(ph_user, "나", question, source=None, align_right=True)

        # 답변 스트림 렌더링
        full_answer = self._render_answer_stream(question, ss.get("__mode", ""), chip_text)

        # 평가 스트림 렌더링
        self._render_evaluation_stream(question, ss.get("__mode", ""), full_answer, chip_text)

        # 세션 상태 업데이트
        ss["last_q"] = question
        ss["inpane_q"] = ""


# 전역 인스턴스
chat_panel_component = ChatPanelComponent()


# 편의 함수 (기존 app.py와의 호환성을 위해)
def _render_chat_panel() -> None:
    """채팅 패널 렌더링"""
    chat_panel_component.render()
