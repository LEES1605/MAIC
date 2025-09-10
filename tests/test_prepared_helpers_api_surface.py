import importlib

def test_prepared_helpers_api_surface():
    app = importlib.import_module("app")
    # Ensure helpers are present
    assert hasattr(app, "_load_prepared_lister")
    assert hasattr(app, "_load_prepared_api")
    assert hasattr(app, "_persist_dir_safe")
    # Call them; they should not raise even if integrations are missing
    lister, logs1 = app._load_prepared_lister()
    assert isinstance(logs1, list)
    chk, mark, logs2 = app._load_prepared_api()
    assert isinstance(logs2, list)
    # Shapes are correct; do not enforce that funcs exist in CI
    assert lister is None or callable(lister)
    assert chk is None or callable(chk)
    assert mark is None or callable(mark)
