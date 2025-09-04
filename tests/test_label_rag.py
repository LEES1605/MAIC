# ============================ [01] TEST: RAG LABEL — START ============================
from __future__ import annotations

from pathlib import Path

from src.rag.search import build_index
from src.rag.label import decide_label, search_hits


def test_label_decision_iyu(tmp_path: Path) -> None:
    # 코퍼스 구성: 이유문법 힌트가 있는 파일명/경로
    base = tmp_path / "prepared" / "iyu"
    base.mkdir(parents=True)
    (base / "이유문법_분사구문.md").write_text("분사구문 요약.", encoding="utf-8")

    hits = search_hits("분사구문", dataset_dir=str(tmp_path / "prepared"), top_k=3)
    lab = decide_label(hits, default_if_none="[AI지식]")
    assert lab == "[이유문법]"


def test_label_decision_book(tmp_path: Path) -> None:
    # 코퍼스 구성: 문법책 힌트가 있는 파일명/경로
    base = tmp_path / "prepared" / "book"
    base.mkdir(parents=True)
    (base / "문법책_가정법.md").write_text("가정법 요약.", encoding="utf-8")

    hits = search_hits("가정법", dataset_dir=str(tmp_path / "prepared"), top_k=3)
    lab = decide_label(hits, default_if_none="[AI지식]")
    assert lab == "[문법책]"


def test_label_fallback_ai(tmp_path: Path) -> None:
    # 코퍼스 없음 → 기본 라벨
    (tmp_path / "prepared").mkdir(parents=True)
    hits = search_hits("아무말", dataset_dir=str(tmp_path / "prepared"), top_k=3)
    lab = decide_label(hits, default_if_none="[AI지식]")
    assert lab == "[AI지식]"
# ============================= [01] TEST: RAG LABEL — END =============================
