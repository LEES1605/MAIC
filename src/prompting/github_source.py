import base64, json, urllib.request
from typing import Optional
from .types import PromptParts

def fetch_yaml_text(token: str, repo: str, path: str, branch: str = "main") -> Optional[str]:
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
    req = urllib.request.Request(url, headers={"Authorization": f"token {token}", "User-Agent": "maic-app"})
    with urllib.request.urlopen(req, timeout=10) as r:  # timeout 추가
        meta = json.loads(r.read().decode("utf-8"))
        return base64.b64decode((meta.get("content") or "").encode()).decode("utf-8")

def build_from_github(yaml_text: str, mode_token: str, q: str, ev1: str, ev2: str) -> Optional[PromptParts]:
    try:
        import yaml
    except Exception:
        return None
    try:
        data = yaml.safe_load(yaml_text) or {}
        node = (data.get("modes") or {}).get(mode_token)
        if not node: return None
        sys_p = node.get("system") if isinstance(node, dict) else ""
        usr_p = node.get("user")   if isinstance(node, dict) else (node if isinstance(node, str) else "")
        if not usr_p: return None
        usr_p = (usr_p.replace("{QUESTION}", q)
                      .replace("{EVIDENCE_CLASS_NOTES}", ev1 or "")
                      .replace("{EVIDENCE_GRAMMAR_BOOKS}", ev2 or ""))
        return PromptParts(system=sys_p or "", user=usr_p, source="GitHub")
    except Exception:
        return None
