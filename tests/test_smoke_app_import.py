# ============================ [01] APP ENTRY SMOKE — START ============================
"""
Smoke test for the app entrypoint without importing it.

목표
- 네트워크/Streamlit/외부 의존 없이 문법 오류만 조기 탐지
- 다양한 리포 구조를 지원: src/maic/app.py, maic/app.py, src/app.py, app.py
"""

from pathlib import Path


def _candidate_paths() -> list[Path]:
    """앱 파일의 후보 경로 목록을 반환."""
    return [
        Path("src/maic/app.py"),
        Path("maic/app.py"),
        Path("src/app.py"),
        Path("app.py"),
    ]


def _pick_app_path() -> Path:
    """
    존재하는 첫 경로를 선택.
    없으면 첫 번째 후보를 반환(테스트 본문에서 친절한 에러 메시지 출력).
    """
    for p in _candidate_paths():
        if p.exists():
            return p
    return _candidate_paths()[0]


def test_app_file_exists_and_compiles() -> None:
    """
    app.py가 존재하고, 소스가 Python으로 컴파일 가능한지(문법 오류 없는지) 확인.
    import를 하지 않으므로 사이드 이펙트가 발생하지 않음.
    """
    candidates = _candidate_paths()
    app_path = next((p for p in candidates if p.exists()), candidates[0])

    assert app_path.exists(), (
        "app.py not found. Checked: "
        + ", ".join(str(p) for p in candidates)
    )

    source = app_path.read_text(encoding="utf-8")

    try:
        # 코드 실행은 하지 않고 AST 컴파일만 수행
        compile(source, str(app_path), "exec")
    except SyntaxError as e:  # pragma: no cover - 오류 경로만 상세 메시지
        # 라인 스니펫과 캐럿 표시로 진단성 향상
        lines = source.splitlines()
        lineno = getattr(e, "lineno", None)
        offset = getattr(e, "offset", None)

        snippet = ""
        caret = ""
        if isinstance(lineno, int) and 1 <= lineno <= len(lines):
            snippet = lines[lineno - 1]
            if isinstance(offset, int) and offset >= 1:
                caret = (" " * (offset - 1)) + "^"

        msg = [
            "SyntaxError while compiling app entrypoint",
            f"location: {app_path}:{lineno}:{offset}",
            f"message : {e.msg}",
        ]
        if snippet:
            msg.append(f"code    : {snippet}")
        if caret:
            msg.append(f"pointer : {caret}")

        raise AssertionError("\n".join(msg)) from None
# ============================= [01] APP ENTRY SMOKE — END =============================
