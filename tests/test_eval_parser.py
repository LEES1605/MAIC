# tests/test_eval_parser.py
from src.agents.eval_parser import parse_eval_block

def test_parse_eval_block_normal():
    text = """
[형식 체크]
- 섹션: OK (모두 충족)
- 괄호규칙: FAIL (라벨 누락 S/V)
- 사실성: WARN (추정 표현 과다)
[피드백]
- 개선점 1
- 개선점 2
[한 줄 총평]
- 핵심은 괄호 라벨을 빠짐없이 적용하는 것입니다.
"""
    p = parse_eval_block(text)
    assert p["sections"]["state"] == "OK"
    assert p["bracket"]["state"] == "FAIL"
    assert p["factual"]["state"] == "WARN"
    assert "핵심은" in p["summary"]

def test_parse_eval_block_missing_lines():
    text = """
[형식 체크]
- 섹션: OK
[피드백]
- 개선점만 있습니다.
"""
    p = parse_eval_block(text)
    assert p["sections"]["state"] == "OK"
    assert p["bracket"]["state"] in ("", None)
    assert p["summary"] in ("", None, "")
