from typing import Optional
from .types import PromptParts

def build_from_drive(mode_token: str, q: str, ev1: str, ev2: str) -> Optional[PromptParts]:
    """src/prompt_modes.build_prompt 사용."""
    try:
        from src import prompt_modes as _mod
    except Exception:
        return None

    fn = getattr(_mod, "build_prompt", None)
    if not callable(fn):
        return None

    try:
        parts = fn(mode_token, q) or {}
        sys_p = parts.get("system") or ""
        usr_p = parts.get("user") or ""
        if usr_p:
            usr_p = (usr_p.replace("{QUESTION}", q)
                          .replace("{EVIDENCE_CLASS_NOTES}", ev1 or "")
                          .replace("{EVIDENCE_GRAMMAR_BOOKS}", ev2 or ""))
        return PromptParts(system=sys_p, user=usr_p, source="Drive")
    except Exception:
        return None
