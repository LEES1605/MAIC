import base64, json
from typing import Optional
from .types import PromptParts
from src.common.utils import http_get, safe_yaml_load

def fetch_yaml_text(token: str, repo: str, path: str, branch: str = "main") -> Optional[str]:
    """GitHub에서 prompts.yaml 텍스트 로드(타임아웃+재시도)."""
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
    headers = {"Authorization": f"token {token}", "User-Agent": "maic-app"}
    try:
        raw = http_get(url, headers=headers, timeout=10.0)
        meta = json.loads(raw.decode("utf-8"))
        return base64.b64decode((meta.get("content") or "").encode()).decode("utf-8")
    except Exception:
        return None

def build_from_github(yaml_text: str, mode_token: str, q: str, ev1: str, ev2: str) -> Optional[PromptParts]:
    data = safe_yaml_load(yaml_text) or {}
    try:
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
