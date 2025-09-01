"""
Common utils for MAIC
- get_secret: st.secrets/env 안전 조회
- logger: 전역 로거
- retry: 지수 백오프 데코레이터
- http_get: timeout + 재시도 HTTP GET
- safe_yaml_load: 안전한 YAML 로드
- now_ms: ms 타임스탬프
(선택) google_drive_client: 서비스계정으로 드라이브 클라이언트 생성
"""
from __future__ import annotations
import os, time, json, logging, contextlib
from functools import wraps
from typing import Optional, Dict, Any

try:
    import streamlit as st  # type: ignore
except Exception:  # 런타임에 따라 없음
    st = None  # type: ignore

# ───────────────────────── Secrets / Logging ─────────────────────────
def get_secret(key: str, default: str = "") -> str:
    """st.secrets → env → default 순서로 조회(로그 노출 금지)."""
    val = None
    if st:
        with contextlib.suppress(Exception):
            v = st.secrets.get(key)  # type: ignore[attr-defined]
            val = v if v is not None else None
    if val is None:
        val = os.getenv(key)
    return str(val) if val is not None else default

_LOGGER: Optional[logging.Logger] = None
def logger() -> logging.Logger:
    global _LOGGER
    if _LOGGER:
        return _LOGGER
    _LOGGER = logging.getLogger("maic")
    if not _LOGGER.handlers:
        h = logging.StreamHandler()
        fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s")
        h.setFormatter(fmt)
        _LOGGER.addHandler(h)
    _LOGGER.setLevel(os.getenv("MAIC_LOGLEVEL", "INFO").upper())
    return _LOGGER

def now_ms() -> int:
    return int(time.time() * 1000)

# ───────────────────────── Retry / HTTP ─────────────────────────
def retry(exceptions, tries: int = 3, delay: float = 0.3, backoff: float = 2.0):
    """지수 백오프 재시도 데코레이터."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            _tries, _delay, last = tries, delay, None
            while _tries > 0:
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:  # type: ignore
                    last = e
                    _tries -= 1
                    if _tries <= 0:
                        break
                    time.sleep(_delay)
                    _delay *= backoff
            if last:
                raise last
        return wrapper
    return deco

from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

@retry((URLError, HTTPError, TimeoutError), tries=3, delay=0.4, backoff=2.0)
def http_get(url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 10.0) -> bytes:
    """단순 GET: timeout + 재시도 + 기본 헤더."""
    req = Request(url, headers=headers or {})
    with urlopen(req, timeout=timeout) as r:  # nosec - 외부 URL 통제는 상위에서
        return r.read()

# ───────────────────────── YAML ─────────────────────────
def safe_yaml_load(text: str):
    """yaml.safe_load 래퍼(미존재 시 None)."""
    try:
        import yaml  # lazy import
    except Exception:
        return None
    with contextlib.suppress(Exception):
        return yaml.safe_load(text)
    return None

# ───────────────────────── Google Drive (선택) ─────────────────────────
def google_drive_client():
    """
    서비스계정 JSON(st.secrets['GDRIVE_SA'] 또는 env)로 Drive v3 클라이언트 생성.
    필요 시에만 import 하며, 설정이 없으면 명확한 예외.
    """
    try:
        from googleapiclient.discovery import build  # type: ignore
        from google.oauth2.service_account import Credentials  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("Google API client not available") from e

    creds_json = get_secret("GDRIVE_SA", "")
    if not creds_json:
        raise RuntimeError("Missing secret 'GDRIVE_SA' for Google Drive client")
    info = json.loads(creds_json)
    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return build("drive", "v3", credentials=creds, cache_discovery=False)
