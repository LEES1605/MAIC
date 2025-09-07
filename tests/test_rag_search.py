# ============================ [01] TEST: SIMPLE RAG SEARCH — START ============================
from __future__ import annotations

from pathlib import Path

from src.rag.search import build_index, search


def test_simple_rag_search(tmp_path: Path) -> None:
    # 샘플 코퍼스 생성
    (tmp_path / "notes").mkdir()
    f1 = tmp_path / "notes" / "분사구문.md"
    f2 = tmp_path / "notes" / "가정법.md"
    f1.write_text("분사구문은 분사의 역할과 부사절 축약과 연관이 있습니다.", encoding="utf-8")
    f2.write_text("가정법은 if절과 가정의 의미를 표현합니다.", encoding="utf-8")

    idx = build_index(str(tmp_path))
    hits = search("분사구문", index=idx, top_k=3)
    assert hits, "검색 결과가 비어서는 안 됩니다."
    assert any("분사구문" in (h.get("title", "") + h.get("snippet", "")) for h in hits)
# ============================= [01] TEST: SIMPLE RAG SEARCH — END =============================
