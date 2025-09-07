# ============================ [01] imports — START ============================
from __future__ import annotations

from pathlib import Path
import json
import time

import pytest

# 대상 모듈: 리팩터 A안 1단계에서 추가된 순수 모듈
from src.core.index_probe import (
    probe_index_health,
    is_brain_ready,
    mark_ready,
    get_brain_status,
)
# ============================ [01] imports — END ==============================


# ========================= [02] helpers — START ===============================
def _write_chunks_jsonl(persist: Path, lines: list[dict | str]) -> Path:
    """테스트 전용: chunks.jsonl 생성 (dict는 JSON 직렬화, str은 그대로 기록)"""
    chunks = persist / "chunks.jsonl"
    with chunks.open("w", encoding="utf-8") as f:
        for item in lines:
            if isinstance(item, dict):
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
            else:
                f.write(str(item).rstrip("\n") + "\n")
    return chunks
# ========================= [02] helpers — END =================================


# ========================= [03] tests — START =================================
def test_status_flow_missing_to_ready(tmp_path: Path) -> None:
    """MISSING → READY 전이 및 기본 메트릭 확인"""

    # 초기 상태: 아무것도 없음
    h0 = probe_index_health(persist=tmp_path)
    assert h0.ready_exists is False
    assert h0.chunks_exists is False
    assert is_brain_ready(persist=tmp_path) is False
    assert get_brain_status(persist=tmp_path)["code"] == "MISSING"

    # chunks.jsonl만 작성 → 아직 READY가 아님
    _write_chunks_jsonl(
        tmp_path,
        lines=[
            {"id": 1, "text": "hello"},
            {"id": 2, "text": "world"},
        ],
    )
    h1 = probe_index_health(persist=tmp_path)
    assert h1.chunks_exists is True
    assert h1.chunks_size > 0
    assert is_brain_ready(persist=tmp_path) is False
    assert get_brain_status(persist=tmp_path)["code"] == "MISSING"

    # .ready 생성 → 이제 READY
    mark_ready(persist=tmp_path)
    # 파일시스템 타임스탬프 안정화(간헐적 flake 방지)
    time.sleep(0.01)

    h2 = probe_index_health(persist=tmp_path)
    assert h2.ready_exists is True
    assert is_brain_ready(persist=tmp_path) is True
    assert get_brain_status(persist=tmp_path)["code"] == "READY"


def test_jsonl_sampling_and_malformed_count(tmp_path: Path) -> None:
    """JSON 샘플 검증: 일부 라인 불량 시 json_malformed가 증가해야 한다."""
    # 2개 정상 + 1개 불량 라인
    _write_chunks_jsonl(
        tmp_path,
        lines=[
            {"id": 1, "text": "alpha"},
            "not-a-json-line",  # 고의 불량
            {"id": 2, "text": "beta"},
        ],
    )
    mark_ready(persist=tmp_path)

    h = probe_index_health(persist=tmp_path, sample_lines=200)
    # 총 3개 라인 중 1개 불량
    assert h.json_sample >= 3  # 플랫폼별 개행 차이에 유연히 대응
    assert h.json_malformed >= 1
    assert is_brain_ready(persist=tmp_path) is True
# ========================= [03] tests — END ===================================
