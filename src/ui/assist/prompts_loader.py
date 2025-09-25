# =============================== [01] imports — START =================================
from __future__ import annotations

import base64
import importlib
from typing import Any, Dict, Iterable, Optional, Tuple

yaml = importlib.import_module("yaml")
req = importlib.import_module("requests")
st = importlib.import_module("streamlit")
# =============================== [01] imports — END ===================================


# =============================== [02] helpers — START =================================
_KEY_ALIASES = {
    "grammar": {"grammar", "문법", "pt", "피티", "피티쌤"},
    "sentence": {"sentence", "문장", "mn", "미나", "미나쌤"},
    "passage": {"passage", "지문", "reading", "독해"},
}
# 값 후보(국문 포함)
_VAL_FIELDS = (
    "prompt", "instruction", "instructions", "rules", "guidelines",
    "text", "content", "template", "value",
    "system", "assistant",
    # 한국어 동의어
    "지시", "지침", "규칙", "가이드", "가이드라인", "설명", "본문", "프롬프트", "템플릿",
    # 리스트형 후보
    "lines", "bullets", "items",
)

def _canon_key(k: str) -> Optional[str]:
    k = (k or "").strip().lower()
    for canon, aliases in _KEY_ALIASES.items():
        if k in aliases or k == canon:
            return canon
    return None

def _split_repo(repo_full: str) -> Tuple[str, str]:
    if repo_full and "/" in repo_full:
        o, r = repo_full.split("/", 1)
        return o, r
    return "", ""

def _http_get_json(url: str, token: Optional[str] = None, timeout: int = 12) -> Any:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = req.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()

def _http_get_text(url: str, token: Optional[str] = None, timeout: int = 20, accept: Optional[str] = None) -> str:
    headers = {}
    if accept:
        headers["Accept"] = accept
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

def _join_list(val: Any) -> str:
    if isinstance(val, list):
        parts = [_norm(x) for x in val if isinstance(x, str)]
        if parts:
            return "\n".join(parts)
    return ""

def _pick(*candidates: Any) -> str:
    for c in candidates:
        s = _norm(c)
        if s:
            return s
    return ""

def _extract_text(val: Any) -> str:
    """dict/list/str 어디서든 '글'을 최대한 뽑아낸다."""
    if isinstance(val, str):
        return _norm(val)
    if isinstance(val, dict):
        # 우선 순위 필드
        s = _pick(*(val.get(k) for k in _VAL_FIELDS if k in val))
        if not s:
            # 리스트형 필드 결합
            s = _join_list(val.get("lines") or val.get("bullets") or val.get("items"))
        if s:
            return s
        # Chat messages 형식 지원
        msgs = val.get("messages") or val.get("chat")
        if isinstance(msgs, list):
            sys = [m for m in msgs if (m.get("role") or "").lower() == "system"]
            if sys and sys[0].get("content"):
                return _norm(sys[0]["content"])
            return _norm("\n".join(_norm(m.get("content")) for m in msgs if m.get("content")))
    if isinstance(val, list):
        return _join_list(val)
    return ""
# =============================== [02] helpers — END ===================================


# =============================== [03] parse modes — START ==============================
def _parse_modes_like(data: dict) -> Dict[str, str]:
    """
    다양한 스키마를 관용적으로 파싱하여 grammar/sentence/passage 3개를 반환.
    지원 형태:
      - data["modes"]가 리스트:
          (A) [{key|name|id|mode: "...", prompt|...}]  ← 기존 지원
          (B) [{문법:{...}}, {문장:{...}}, {지문:{...}}] ← ★신규: 중첩 키 스캔
      - data["modes"]가 매핑: {grammar|문법: "..." 또는 {prompt|...}}
      - data["prompts"]가 유사 구조일 때도 동일 처리
    """
    out = {"grammar": "", "sentence": "", "passage": ""}

    def _apply_mapping(m: dict) -> None:
        for raw_k, v in m.items():
            ck = _canon_key(str(raw_k))
            if not ck or ck not in out:
                continue
            out[ck] = _extract_text(v)

    modes = data.get("modes")

    # 1) 리스트: (A) key/name/id/mode... or (B) {문법:{...}} 한 항목=한 모드
    if isinstance(modes, list):
        for item in modes:
            if not isinstance(item, dict):
                continue
            raw_k = item.get("key") or item.get("name") or item.get("id") or item.get("mode")
            ck = _canon_key(str(raw_k)) if raw_k else None
            if ck and ck in out:
                out[ck] = _extract_text(item)
                continue
            # (B) {문법:{...}} 형태 처리
            for k2, v2 in item.items():
                ck2 = _canon_key(str(k2))
                if ck2 and ck2 in out:
                    out[ck2] = _extract_text(v2)
        # 루트 보정은 아래에서 공통 처리
    elif isinstance(modes, dict):
        _apply_mapping(modes)

    # 2) prompts (대체 키)
    prompts = data.get("prompts")
    if isinstance(prompts, dict):
        _apply_mapping(prompts)

    # 3) 루트 대체 키
    out["grammar"]  = out["grammar"]  or _norm(data.get("grammar"))
    out["sentence"] = out["sentence"] or _norm(data.get("sentence"))
    out["passage"]  = out["passage"]  or _norm(data.get("passage"))

    # 4) 상호 보정(한쪽만 있으면 복사)
    if not out["passage"] and out["sentence"]:
        out["passage"] = out["sentence"]
    if not out["sentence"] and out["passage"]:
        out["sentence"] = out["passage"]

    return out

# =============================== [03] parse modes — END ================================


# =============================== [04] loader core — START =============================
def _download_prompts_yaml_from_release(
    owner: str, repo: str, token: Optional[str], prefer_tag: Optional[str]
) -> Optional[str]:
    """릴리스에서 prompts.yaml(또는 .yml)을 가져온다. 없으면 None."""
    # 1) prefer_tag 우선
    if prefer_tag:
        try:
            rel = _http_get_json(
                f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{prefer_tag}",
                token=token,
            )
            for a in rel.get("assets") or []:
                name = (a.get("name") or "").lower()
            # _download_prompts_yaml_from_release 내부에서
            if name in ("prompts.yaml", "prompts.yml"):
                # 우선: browser_download_url (공개 raw)
                try:
                    return _http_get_text(a.get("browser_download_url"), token=None, accept="application/octet-stream")
                except Exception:
                    pass
    # 폴백: assets/{id} (API)
    try:
        aid = a.get("id")
        if aid:
            api = f"https://api.github.com/repos/{owner}/{repo}/releases/assets/{aid}"
            return _http_get_text(api, token=token, accept="application/octet-stream")
    except Exception:
        pass


    # 2) 최신 릴리스들 페이지네이션 스캔(최대 5페이지)
    for page in range(1, 6):
        rels = _http_get_json(
            f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=20&page={page}",
            token=token,
        )
        if not isinstance(rels, list) or not rels:
            break
        for rel in rels:
            if rel.get("draft") is True:
                continue
            for a in rel.get("assets") or []:
                name = (a.get("name") or "").lower()
                if name in ("prompts.yaml", "prompts.yml"):
                    return _http_get_text(a.get("browser_download_url"), token=token)
        if len(rels) < 20:
            break
    return None


def _download_prompts_yaml_from_repo(
    owner: str, repo: str, token: Optional[str], ref: str = "main",
) -> Optional[str]:
    """
    레포 SSOT 경로에서 prompts.yaml 폴백 로드.
    SSOT: docs/_gpt/ ... (Workspace Pointer 규약)  :contentReference[oaicite:4]{index=4}
    """
    for path in ("docs/_gpt/prompts.yaml", "docs/_gpt/prompts.yml"):
        try:
            u = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={ref}"
            j = _http_get_json(u, token=token)
            if isinstance(j, dict) and j.get("encoding") == "base64":
                return base64.b64decode(j.get("content") or b"").decode("utf-8", "ignore")
        except Exception:
            continue
    return None


def load_prompts_from_release(
    repo_full: Optional[str] = None,
    token: Optional[str] = None,
    prefer_tag: str = "prompts-latest",
) -> Dict[str, str]:
    """
    (1) 릴리스 다건 스캔 → prompts.yaml 탐색
    (2) 실패 시 레포의 docs/_gpt/prompts.yaml 폴백
    어떤 스키마든 관용 파서로 persona + 3모드 텍스트를 뽑아 반환.
    """
    repo_full = repo_full or st.secrets.get("GITHUB_REPO", "")
    token = token or st.secrets.get("GITHUB_TOKEN")
    owner, repo = _split_repo(repo_full)
    if not owner or not repo:
        raise RuntimeError("GITHUB_REPO not set or malformed")

    ytext = _download_prompts_yaml_from_release(owner, repo, token, prefer_tag)
    if not ytext:
        ytext = _download_prompts_yaml_from_repo(owner, repo, token, ref="main")
    if not ytext:
        raise RuntimeError("prompts.yaml not found (release nor repo)")

    data = yaml.safe_load(ytext) or {}
    if not isinstance(data, dict):
        raise RuntimeError("prompts.yaml: root must be a mapping")

    persona = _pick(
        data.get("persona"),
        (data.get("persona") or {}).get("common") if isinstance(data.get("persona"), dict) else None,
    )

    modes = _parse_modes_like(data)

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
# =============================== [04] loader core — END ===============================
