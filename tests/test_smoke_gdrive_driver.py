# ============================ [01] GDRIVE DRIVER SMOKE — START ============================
"""
Lightweight smoke tests for src.integrations.gdrive

목표
- 네트워크/구글 라이브러리 없이도 실패-방향이 올바른지 확인
- 동적 임포트 구조가 테스트 환경에서 임포트 오류를 일으키지 않는지 검증
"""

import importlib
import os

import pytest


def test_import_gdrive_module() -> None:
    """
    모듈이 테스트 환경에서 정상적으로 임포트되는지 확인.
    (동적 임포트가 존재하지만, 임포트 자체는 실패하지 않아야 함)
    """
    mod = importlib.import_module("src.integrations.gdrive")
    assert hasattr(mod, "list_prepared_files"), "list_prepared_files() not found"


def test_list_prepared_files_raises_without_folder_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    필수 환경변수(GDRIVE_PREPARED_FOLDER_ID)가 없을 때
    list_prepared_files()가 의도적으로 RuntimeError를 발생시키는지 확인.
    메시지에 키 이름이 포함되어 있어야 진단이 쉬움.
    """
    # 사전 환경 정리
    monkeypatch.delenv("GDRIVE_PREPARED_FOLDER_ID", raising=False)
    monkeypatch.delenv("GDRIVE_SA_JSON", raising=False)

    mod = importlib.import_module("src.integrations.gdrive")

    with pytest.raises(RuntimeError) as excinfo:
        mod.list_prepared_files()

    msg = str(excinfo.value)
    assert "GDRIVE_PREPARED_FOLDER_ID" in msg, f"unexpected error message: {msg}"
# ============================= [01] GDRIVE DRIVER SMOKE — END =============================
