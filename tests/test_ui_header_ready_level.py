# ===== [NEW] FILE: tests/test_ui_header_ready_level.py — START =====
import importlib
import types

import pytest

# header 모듈을 임포트(경로는 프로젝트 구조에 맞게 조정)
header = importlib.import_module("src.ui.header")

def test_high_when_latest_true():
    ss = {"_INDEX_IS_LATEST": True}
    assert header._compute_ready_level_from_session(ss) == "HIGH"

def test_high_when_ready_and_attached():
    ss = {"brain_status_code": "READY", "brain_attached": True}
    assert header._compute_ready_level_from_session(ss) == "HIGH"

def test_mid_when_ready_but_not_attached():
    ss = {"brain_status_code": "READY", "brain_attached": False}
    assert header._compute_ready_level_from_session(ss) == "MID"

def test_low_when_missing():
    ss = {"brain_status_code": "MISSING", "brain_attached": False}
    assert header._compute_ready_level_from_session(ss) == "LOW"

def test_fallback_mid_when_local_ok():
    assert header._compute_ready_level_from_session({}, fallback_local_ok=True) == "MID"

def test_fallback_low_when_local_not_ok():
    assert header._compute_ready_level_from_session({}, fallback_local_ok=False) == "LOW"
# ===== [NEW] FILE: tests/test_ui_header_ready_level.py — END =====
