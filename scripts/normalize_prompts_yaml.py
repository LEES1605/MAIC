#!/usr/bin/env python3
# [WF-NORM] START: .github/scripts/normalize_prompts_yaml.py
from __future__ import annotations
import sys, json
from pathlib import Path
import yaml

def _txt(v):
    if v is None: return ""
    if isinstance(v, str): return v
    if isinstance(v, dict):
        for k in ("prompt","text","full","system","value","content"):
            s = v.get(k)
            if isinstance(s, str) and s.strip(): return s
        return json.dumps(v, ensure_ascii=False, indent=2)
    if isinstance(v, (list, tuple)): return "\n".join(str(x) for x in v)
    return str(v)

def _canon(label: str) -> str:
    t = "".join(ch for ch in (label or "").lower() if ch.isalnum())
    table = {
        "grammar":"grammar", "pt":"grammar", "문법":"grammar", "문법설명":"grammar",
        "sentence":"sentence","sent":"sentence","문장":"sentence","문장구조분석":"sentence",
        "passage":"passage", "para":"passage","지문":"passage","지문분석":"passage",
    }
    return table.get(t, "")

def main(path: str) -> None:
    p = Path(path)
    y = yaml.safe_load(p.read_text(encoding="utf-8")) or {}

    persona = (y.get("persona") or y.get("common") or y.get("system") or "").strip()
    out = {"grammar":"", "sentence":"", "passage":""}

    m = y.get("modes")
    if isinstance(m, dict):
        for k,v in m.items():
            ck = _canon(k)
            if ck: out[ck] = _txt(v)
    elif isinstance(m, list):
        for e in m:
            if not isinstance(e, dict): continue
            k = e.get("key") or e.get("label") or e.get("name") or ""
            ck = _canon(k)
            if ck:
                payload = e.get("prompt") or e.get("text") or e.get("full") or e.get("system") or e
                out[ck] = _txt(payload)

    for k,v in list(y.items()):
        ck = _canon(k)
        if ck and not out[ck]:
            out[ck] = _txt(v)

    doc = {
        "version": str(y.get("version") or "1"),
        "persona": persona,
        "modes": out,
    }
    p.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print("normalized:", p)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: normalize_prompts_yaml.py <prompts.yaml>")
        sys.exit(2)
    main(sys.argv[1])
# [WF-NORM] END
