# ===== [01] FILE: src/ui/assist/prompts_loader.py — START =====
# -*- coding: utf-8 -*-
"""
Prompts loader (release → persona + 3 mode prompts)
- 릴리스의 prompts.yaml 스키마 변종을 관용적으로 파싱해 4개 텍스트를 반환/주입.
- 목표: '최신 프롬프트 불러오기' 클릭 시 페르소나 + 문법/문장/지문이 모두 채워지지 않던 문제 해결.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import importlib

yaml = importlib.import_module("yaml")
req = importlib.import_module("requests")
st = importlib.import_module("streamlit")


# ---------- helpers ----------
def _split_repo(repo_full: str) -> Tuple[str, str]:
    if repo_full and "/" in repo_full:
        o, r = repo_full.split("/", 1)
        return o, r
    return "", ""


def _http_get_json(url: str, token: Optional[str] = None, timeout: int = 12) -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = req.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _http_get_text(url: str, token: Optional[str] = None, timeout: int = 20) -> str:
    headers = {"Accept": "text/plain"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = req.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text


def _norm(x: Any) -> str:
    if x is None:
        return ""
    s = str(x)
    return s.replace("\r\n", "\n").strip()


def _pick(*candidates: Any) -> str:
    for c in candidates:
        s = _norm(c)
        if s:
            return s
    return ""


def _parse_modes(data: dict) -> Dict[str, str]:
    """
    modes 관용 파서:
      - 리스트: [{key|name, prompt|instruction|rules|text}]
      - 매핑:   {grammar|sentence|passage: str or {prompt|instruction|rules|text}}
    """
    out = {"grammar": "", "sentence": "", "passage": ""}

    modes = data.get("modes")
    if modes is None:
        return out

    # 1) 리스트형
    if isinstance(modes, list):
        for item in modes:
            if not isinstance(item, dict):
                continue
            key = (item.get("key") or item.get("name") or "").strip().lower()
            val = _pick(item.get("prompt"), item.get("instruction"), item.get("rules"), item.get("text"))
            if key in out and val:
                out[key] = val
        return out

    # 2) 매핑형
    if isinstance(modes, dict):
        for key in ("grammar", "sentence", "passage"):
            v = modes.get(key)
            if isinstance(v, dict):
                out[key] = _pick(v.get("prompt"), v.get("instruction"), v.get("rules"), v.get("text"))
            else:
                out[key] = _pick(v)
    return out


# ---------- core ----------
def load_prompts_from_release(
    repo_full: Optional[str] = None,
    token: Optional[str] = None,
    prefer_tag: str = "prompts-latest",
) -> Dict[str, str]:
    """
    최신 릴리스에서 prompts.yaml을 읽어 페르소나+3모드 텍스트로 반환.
    반환 dict keys: persona, grammar, sentence, passage
    """
    repo_full = repo_full or st.secrets.get("GITHUB_REPO", "")
    token = token or st.secrets.get("GITHUB_TOKEN")
    owner, repo = _split_repo(repo_full)
    if not owner or not repo:
        raise RuntimeError("GITHUB_REPO not set or malformed")

    # 1) 릴리스 메타
    try:
        rel = _http_get_json(
            f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{prefer_tag}",
            token=token,
        )
    except Exception:
        rel = _http_get_json(  # fallback
            f"https://api.github.com/repos/{owner}/{repo}/releases/latest",
            token=token,
        )

    # 2) prompts.yaml asset 찾기
    assets = rel.get("assets") or []
    dl = None
    for a in assets:
        name = (a.get("name") or "").lower()
        if name in ("prompts.yaml", "prompts.yml"):
            dl = a.get("browser_download_url")
            break
    if not dl:
        raise RuntimeError("prompts.yaml asset not found in the latest release")

    # 3) YAML 파싱
    ytext = _http_get_text(dl, token=token)
    data = yaml.safe_load(ytext) or {}
    if not isinstance(data, dict):
        raise RuntimeError("prompts.yaml: root must be a mapping")

    persona = _pick(
        data.get("persona"),
        (data.get("persona") or {}).get("common") if isinstance(data.get("persona"), dict) else None,
    )
    modes = _parse_modes(data)

    return {
        "persona": persona,
        "grammar": modes.get("grammar", ""),
        "sentence": modes.get("sentence", ""),
        "passage": modes.get("passage", ""),
    }


def apply_prompts_to_session(
    prompts: Dict[str, str],
    *,
    key_map: Optional[Dict[str, tuple[str, ...]]] = None,
) -> None:
    """
    Streamlit 세션 상태에 관용적으로 주입(관리자 화면 text_area 초기값 채움).
    - key_map 미지정 시 일반적으로 쓰는 여러 키를 탐색해 모두 세팅.
    """
    ss = st.session_state
    key_map = key_map or {
        "persona": ("persona_text", "persona", "_persona_text"),
        "grammar": ("grammar_prompt", "prompt_g", "g_prompt"),
        "sentence": ("sentence_prompt", "prompt_s", "s_prompt"),
        "passage": ("passage_prompt", "prompt_p", "p_prompt"),
    }
    for entry, keys in key_map.items():
        val = prompts.get(entry, "")
        for k in keys:
            ss[k] = val
# ===== [01] FILE: src/ui/assist/prompts_loader.py — END =====
