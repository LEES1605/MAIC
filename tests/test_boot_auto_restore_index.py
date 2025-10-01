import types
import sys
import importlib

def test_boot_restore_calls_ghrestore(monkeypatch, tmp_path):
    # 1) 가짜 streamlit 모듈을 sys.modules에 주입 (app.py import 전에!)
    fake_st_mod = types.SimpleNamespace(
        session_state={},
        rerun=lambda: None,
        experimental_rerun=lambda: None,
        secrets={"GITHUB_REPO": "owner/repo", "GITHUB_TOKEN": "x"},
        # 디버깅용 streamlit 메서드들 추가
        info=lambda msg: print(f"[ST_INFO] {msg}"),
        success=lambda msg: print(f"[ST_SUCCESS] {msg}"),
        error=lambda msg: print(f"[ST_ERROR] {msg}"),
        warning=lambda msg: print(f"[ST_WARNING] {msg}"),
    )
    sys.modules["streamlit"] = fake_st_mod

    # 2) GH Releases 및 SequentialReleaseManager 더블
    called = {"latest": 0, "restore": 0}

    class GHConfig:  # pragma: no cover
        def __init__(self, owner, repo, token=None):
            assert owner == "owner" and repo == "repo"

    class GHReleases:  # pragma: no cover
        def __init__(self, cfg): pass
        def get_latest_release(self):
            called["latest"] += 1
            return {"tag_name": "index-latest", "id": 123}
        def restore_latest_index(self, **kwargs):
            called["restore"] += 1
            class R:
                tag = "index-latest"
                release_id = 123
                asset_name = "indices.zip"
                detail = "ok"
                used_latest_endpoint = True
            return R()

    class SequentialReleaseManager:  # pragma: no cover
        def __init__(self, gh_client): pass
        def restore_latest_index(self, dest, clean_dest=False):
            called["restore"] += 1
            return {"tag": "index-1", "release_id": 123}

    def create_sequential_manager(owner, repo, token):  # pragma: no cover
        return SequentialReleaseManager(None)

    sys.modules["src.runtime.gh_release"] = types.SimpleNamespace(
        GHConfig=GHConfig, GHReleases=GHReleases
    )
    sys.modules["src.runtime.sequential_release"] = types.SimpleNamespace(
        create_sequential_manager=create_sequential_manager
    )

    # 3) app import 및 persist 경로 덮어쓰기
    app = importlib.import_module("app")
    monkeypatch.setattr(app, "effective_persist_dir", lambda: tmp_path, raising=False)

    # 4) 실행
    app._boot_auto_restore_index()

    # 5) 검증
    assert called["latest"] == 1
    assert called["restore"] == 1
    ss = fake_st_mod.session_state
    assert ss.get("_BOOT_RESTORE_DONE") is True
    assert ss.get("_INDEX_IS_LATEST") is True
    assert ss.get("_INDEX_LOCAL_READY") is True
