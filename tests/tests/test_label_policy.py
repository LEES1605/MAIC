# [01] START: tests/test_label_policy.py (NEW FILE)
from typing import Dict
from rag.label import decide_label, classify_hit  # src.rag.label is on sys.path via conftest


def test_decide_label_priority() -> None:
    hit_reason: Dict[str, str] = {
        "title": "이유문법 - 관사",
        "source": "/prepared/이유문법/관사.pdf",
        "path": "/repo/prepared/이유문법/관사.pdf",
    }
    hit_book: Dict[str, str] = {
        "title": "Oxford English Grammar",
        "source": "/books/grammar/Oxford.pdf",
        "path": "/books/grammar/Oxford.pdf",
    }
    hit_other: Dict[str, str] = {
        "title": "블로그 글", 
        "source": "/web/blog.html", 
        "path": "/web/blog.html"}

    # 이유문법이 하나라도 있으면 최우선
    assert decide_label([hit_book, hit_reason, hit_other]) == "[이유문법]"
    # 문법서 힌트만 있으면 [문법서적]
    assert decide_label([hit_book, hit_other]) == "[문법서적]"
    # 없으면 기본값
    assert decide_label([]) == "[AI지식]"

    # 분류기 자체 검증(보수적으로 시작)
    assert classify_hit(hit_reason) == "reason"
    assert classify_hit(hit_book) in ("book", "other")
# [01] END: tests/test_label_policy.py
