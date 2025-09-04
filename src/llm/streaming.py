# ============================ [01] LLM STREAMING WRAPPER — START ============================
"""
스트리밍 응답을 안전하게 처리하기 위한 공용 유틸.

목표
- ChatGPT, Gemini 등 서로 다른 SDK의 스트리밍을 '토큰 문자열 이터레이터'로 정규화
- 스트리밍 도중 취소/타임아웃/예외에 대비
- Streamlit의 write_stream 유무에 따라 자동 폴백
"""

from __future__ import annotations

from typing import Callable, Iterable, Iterator, Optional, Union


class StreamCancelled(Exception):
    """사용자 취소 등으로 스트리밍을 중단할 때 사용하는 예외."""
    pass


# E501 방지: 타입 별칭을 여러 줄로 분리
TokenSource = Union[
    str,
    Iterable[str],
    Iterator[str],
    Callable[[], Union[str, Iterable[str], Iterator[str]]],
]


def normalize_to_token_iter(source: TokenSource) -> Iterator[str]:
    """
    다양한 입력을 '토큰 문자열 이터레이터'로 정규화.
    - str           ->  한 번만 yield
    - iterable/iter ->  그대로 yield
    - callable      ->  호출 결과를 다시 정규화
    """
    if callable(source):
        return normalize_to_token_iter(source())

    # 문자열 1회성
    if isinstance(source, str):
        def _once() -> Iterator[str]:
            yield source
        return _once()

    # 이터러블/이터레이터
    try:
        iterator = iter(source)
    except Exception:
        # 예외 객체를 쓰지 않음: F821(e 미정의) 원천 차단
        def _err() -> Iterator[str]:
            yield "[streaming-normalize-error]"
        return _err()

    def _tokens() -> Iterator[str]:
        for chunk in iterator:
            # 안전 장치: None/비문자 타입이 오면 문자열로 강제
            if chunk is None:
                continue
            yield str(chunk)
    return _tokens()


# E501 방지: 함수 시그니처를 여러 줄로 분리
def stream_with_cancellation(
    tokens: Iterator[str],
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> Iterator[str]:
    """
    취소 신호를 주기적으로 확인하며 토큰을 흘려보냄.
    is_cancelled()가 True를 반환하면 StreamCancelled 발생.
    """
    for t in tokens:
        if is_cancelled is not None:
            try:
                if is_cancelled():
                    raise StreamCancelled("stream cancelled by user")
            except Exception:
                # 취소 콜백 오류는 무시하고 계속
                pass
        yield t


def render_stream_safely(st_mod, token_iter: Iterator[str]) -> str:
    """
    Streamlit 유틸: write_stream이 있으면 사용, 없으면 placeholder로 폴백.
    반환값은 누적된 전체 텍스트.
    """
    if st_mod is None:
        # Streamlit이 없으면 그냥 모두 이어붙여서 반환
        buf: list[str] = []
        for t in token_iter:
            buf.append(t)
        return "".join(buf)

    # 1) 최신 API가 있으면 그대로 사용
    try:
        if hasattr(st_mod, "write_stream"):
            return st_mod.write_stream(token_iter)
    except Exception:
        pass

    # 2) 구버전 폴백: placeholder를 이용해 점진 렌더
    try:
        ph = st_mod.empty()
        acc: list[str] = []
        for t in token_iter:
            acc.append(t)
            ph.markdown("".join(acc))
        return "".join(acc)
    except Exception:
        # 마지막 폴백: 그냥 전부 모아서 한 번에 출력
        acc2: list[str] = []
        for t in token_iter:
            acc2.append(t)
        st_mod.markdown("".join(acc2))
        return "".join(acc2)
# ============================= [01] LLM STREAMING WRAPPER — END =============================
