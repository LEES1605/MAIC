import types
import builtins

def test_boot_restore_calls_ghrestore(monkeypatch, tmp_path):
    # ---- 가짜 streamlit ----
    class _FakeSt:
        def __init__(self):
            self.session_state = {}
        def rerun(self): pass
        def experimental_rerun(self): pass
        class secrets:  # pragma: no cover - simple holder
            GITHUB_REPO = "owner/repo"
            GITHUB_TOKEN = "x"
    fake_st = _FakeSt()

    # app 모듈 import 전에 삽입
    monkeypatch.setitem(builtins.__dict__, "st", fake_st)

    # ---- 가짜 gh_release ----
    called = {"restore": 0, "latest": 0}
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
            class R: tag = "index-latest"; release_id = 123
            return R()
    import sys
    fake_mod = types.SimpleNamespace(GHConfig=GHConfig, GHReleases=GHReleases)
    sys.modules["src.runtime.gh_release"] = fake_mod

    # ---- app import & override persist dir ----
    import importlib
    app = importlib.import_module("app")

    # persist dir를 tmp로 강제
    monkeypatch.setattr(app, "effective_persist_dir", lambda: tmp_path, raising=False)

    # 실행
    app._boot_auto_restore_index()

    # 검증: GH 호출되고, 세션 플래그가 최신으로 설정됨
    assert called["latest"] == 1
    assert called["restore"] == 1
    ss = fake_st.session_state
    assert ss.get("_BOOT_RESTORE_DONE") is True
    assert ss.get("_INDEX_IS_LATEST") is True
    assert ss.get("_INDEX_LOCAL_READY") is True
