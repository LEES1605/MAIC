# ============================== [01] Streaming Buffer — START ==============================
"""
Sentence-level streaming buffer.

목적
- 모델이 토큰/청크 단위로 내보내는 문자열을 '읽기 좋은' 단위로 모아 방출합니다.
- 플러시 트리거: 문장부호(EN/KO), 개행, 최대 지연 시간, 최소 문자 수.

사용 예시
---------
from src.llm.streaming import BufferOptions, SentenceBuffer

buf = SentenceBuffer(on_emit=print, opts=BufferOptions())
for piece in provider_stream():  # 토큰 또는 청크
    buf.feed(piece)
buf.flush(force=True)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple, Iterable
import time
import re


# 문장 경계 후보 문자(영/한 + 일반적 구두점)
_PUNCTS = set(
    list(".,?!:;)]}") + ["...", "。", "、", "！", "？", "”", "’", "·", "—", "–"]
)

# 문장 종료로 **강하게** 취급할 문자
_STRONG_END = set(list(".?!") + ["。", "！", "？", "..."])

# 공백 패턴(연속 공백을 한 번에 인지)
_WS_RE = re.compile(r"\s+")


@dataclass
class BufferOptions:
    """
    스트리밍 버퍼 옵션
    """
    min_emit_chars: int = 28
    # 강한 종료부호가 없더라도 이 길이를 넘으면 가벼운 플러시를 허용
    soft_emit_chars: int = 64
    # 최장 지연(ms): 마지막 방출 이후 이 시간이 지나면 보수적으로 플러시
    max_latency_ms: int = 350
    # 강한 종료부호가 들어오면 바로 플러시(단, 최소 글자수는 만족해야 함)
    flush_on_strong_punct: bool = True
    # 개행이 들어오면 줄 단위로 플러시
    flush_on_newline: bool = True


class SentenceBuffer:
    """
    토큰/청크 스트림을 문장 단위로 변환하는 버퍼.
    - feed(piece): 입력(토큰/청크) 수신
    - flush(force): 버퍼를 방출(강제/조건부)
    """

    def __init__(
        self,
        on_emit: Callable[[str], None],
        opts: Optional[BufferOptions] = None,
    ) -> None:
        self.on_emit = on_emit
        self.opts = opts or BufferOptions()
        self._buf: list[str] = []
        self._last_emit_at: float = time.monotonic()

    # 내부 유틸
    def _now_ms(self) -> int:
        return int((time.monotonic() - self._last_emit_at) * 1000)

    def _buffer_text(self) -> str:
        return "".join(self._buf)

    def _emit(self, text: str) -> None:
        txt = text
        if not txt:
            return
        self.on_emit(txt)
        self._last_emit_at = time.monotonic()

    def _try_flush_by_rules(self) -> None:
        """
        규칙 기반 플러시:
        - 강한 종결부호(. ? ! ... 등) 등장 + 최소 글자수 충족
        - 줄바꿈
        - soft 길이 초과
        - 최대 지연 경과
        """
        s = self._buffer_text()
        if not s:
            return

        # 1) 줄바꿈 기준
        if self.opts.flush_on_newline and "\n" in s:
            parts = s.splitlines(keepends=True)
            keep_tail = ""
            for p in parts:
                if p.endswith("\n"):
                    self._emit(p)
                else:
                    keep_tail = p
            self._buf = [keep_tail]
            return

        # 2) 강한 종결부호 기준
        if self.opts.flush_on_strong_punct and any(ch in _STRONG_END for ch in s):
            if len(s) >= self.opts.min_emit_chars:
                self._emit(s)
                self._buf = []
                return

        # 3) soft 길이 초과 시(단어 경계 고려)
        if len(s) >= self.opts.soft_emit_chars:
            cut = self._cut_at_last_boundary(s)
            if cut:
                self._emit(cut)
                rest = s[len(cut) :]
                self._buf = [rest]
                return

        # 4) 최대 지연
        if self._now_ms() >= self.opts.max_latency_ms:
            cut = self._cut_at_last_boundary(s)
            if not cut:
                cut = s
            self._emit(cut)
            rest = s[len(cut) :]
            self._buf = [rest]

    @staticmethod
    def _cut_at_last_boundary(s: str) -> str:
        """
        '단어 경계/구두점'을 우선 고려해 자르는 헬퍼.
        - 마지막 구두점 또는 공백 위치를 찾아 거기까지만 방출.
        """
        last_ws = -1
        last_p = -1
        for i, ch in enumerate(s):
            if _WS_RE.match(ch):
                last_ws = i
            if ch in _PUNCTS:
                last_p = i
        # 구두점이 더 좋고, 없으면 공백, 그것도 없으면 빈 문자열
        idx = max(last_p, last_ws)
        return s[: idx + 1] if idx >= 0 else ""

    # 외부 API
    def feed(self, piece: str) -> None:
        """
        토큰/청크를 버퍼에 추가하고, 규칙에 따라 필요 시 방출.
        """
        if not piece:
            return
        self._buf.append(piece)
        self._try_flush_by_rules()

    def flush(self, force: bool = False) -> None:
        """
        남은 내용을 방출.
        - force=False: 남은 내용 그대로 한 번 방출
        - force=True : 남은 내용 전부를 반드시 방출
        """
        s = self._buffer_text()
        if not s:
            return
        if force:
            self._emit(s)
            self._buf = []
            return
        # non-force: 가능한 경계까지 자르고 방출
        cut = self._cut_at_last_boundary(s)
        if cut:
            self._emit(cut)
            rest = s[len(cut) :]
            self._buf = [rest]
        else:
            # 경계가 없으면 전부 방출
            self._emit(s)
            self._buf = []


def make_stream_handler(
    on_emit: Callable[[str], None],
    opts: Optional[BufferOptions] = None,
) -> Tuple[Callable[[str], None], Callable[[], None]]:
    """
    간편 핸들러 생성기.
    - 반환값: (on_piece, on_close)
    - on_piece(text): 토막 입력
    - on_close(): 마무리(강제 플러시)
    """
    buf = SentenceBuffer(on_emit=on_emit, opts=opts)

    def on_piece(text: str) -> None:
        buf.feed(text)

    def on_close() -> None:
        buf.flush(force=True)

    return on_piece, on_close
# =============================== [01] Streaming Buffer — END ===============================
