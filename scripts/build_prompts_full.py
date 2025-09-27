#!/usr/bin/env python3
# .github/scripts/build_prompts_full.py
from __future__ import annotations
from pathlib import Path
import json, yaml

def _coerce_txt(v):
    if v is None: return ""
    if isinstance(v, str): return v
    if isinstance(v, dict):
        for k in ("prompt", "text", "full", "system", "value", "content"):
            s = v.get(k)
            if isinstance(s, str) and s.strip():
                return s
        return json.dumps(v, ensure_ascii=False, indent=2)
    if isinstance(v, (list, tuple)):
        return "\n".join(str(x) for x in v)
    return str(v)

def _pick(y, key):
    # 우선순위: modes(dict) → modes(list) → top-level
    if isinstance(y.get("modes"), dict):
        return _coerce_txt(y["modes"].get(key))
    if isinstance(y.get("modes"), list):
        for e in y["modes"]:
            if str(e.get("key","")).lower() == key:
                return _coerce_txt(e.get("prompt") or e.get("text") or e.get("full") or e.get("system") or e)
    return _coerce_txt(y.get(key))

def _join(persona, body):
    persona, body = (persona or "").strip(), (body or "").strip()
    if persona and body:
        return (persona + "\n\n" + body).strip()
    return (persona or body).strip()

y = yaml.safe_load(Path("prompts.yaml").read_text(encoding="utf-8")) or {}
persona = (y.get("persona") or y.get("common") or "").strip()

g = _pick(y, "grammar")
s = _pick(y, "sentence")
p = _pick(y, "passage")

out = Path("prompts_full"); out.mkdir(exist_ok=True)
(out/"grammar.full.txt").write_text(_join(persona, g), encoding="utf-8")
(out/"sentence.full.txt").write_text(_join(persona, s), encoding="utf-8")
(out/"passage.full.txt").write_text(_join(persona, p), encoding="utf-8")
print("Built:", [pp.name for pp in out.iterdir()])
