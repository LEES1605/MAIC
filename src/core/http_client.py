# ===== [01] PURPOSE ==========================================================
# 통합 HTTP 클라이언트 - 모든 HTTP 요청을 단일 클라이언트로 통합
# 표준화된 에러 처리, 타임아웃, 재시도 로직, GitHub API 전용 메서드 제공

# ===== [02] IMPORTS ==========================================================
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import urllib.request
import urllib.error
import urllib.parse

try:
    import requests as req
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    req = None

# ===== [03] CONFIGURATION ====================================================
@dataclass
class HttpClientConfig:
    """HTTP 클라이언트 설정"""
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    backoff_factor: float = 2.0
    user_agent: str = "MAIC-HttpClient/1.0"
    
    # GitHub API 설정
    github_api_base: str = "https://api.github.com"
    github_accept_header: str = "application/vnd.github+json"
    
    # Google Drive API 설정
    gdrive_api_base: str = "https://www.googleapis.com/drive/v3"

class HttpMethod(Enum):
    """HTTP 메서드"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"

class HttpError(Exception):
    """HTTP 에러"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_text: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text

# ===== [04] HTTP CLIENT CLASS ================================================
class HttpClient:
    """통합 HTTP 클라이언트"""
    
    def __init__(self, config: Optional[HttpClientConfig] = None):
        self.config = config or HttpClientConfig()
        self._session = None
        if REQUESTS_AVAILABLE:
            self._init_session()
    
    def _init_session(self) -> None:
        """requests 세션 초기화"""
        if not REQUESTS_AVAILABLE:
            return
        
        self._session = req.Session()
        self._session.headers.update({
            "User-Agent": self.config.user_agent,
            "Accept": "application/json",
        })
    
    def _make_request(
        self,
        method: HttpMethod,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Union[str, bytes, Dict[str, Any]]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        retries: Optional[int] = None
    ) -> Tuple[int, Dict[str, Any], str]:
        """
        HTTP 요청 실행
        
        Returns:
            (status_code, response_headers, response_text)
        """
        timeout = timeout or self.config.timeout
        max_retries = retries or self.config.max_retries
        
        # 요청 데이터 준비
        if json_data is not None:
            if isinstance(data, dict):
                data = json.dumps(data)
            headers = headers or {}
            headers["Content-Type"] = "application/json"
        
        # 재시도 로직
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                if REQUESTS_AVAILABLE and self._session:
                    return self._make_request_requests(
                        method, url, headers=headers, data=data, 
                        params=params, timeout=timeout
                    )
                else:
                    return self._make_request_urllib(
                        method, url, headers=headers, data=data, 
                        timeout=timeout
                    )
            except (HttpError, req.RequestException, urllib.error.URLError) as e:
                last_exception = e
                if attempt < max_retries:
                    delay = self.config.retry_delay * (self.config.backoff_factor ** attempt)
                    time.sleep(delay)
                    continue
                break
        
        # 모든 재시도 실패
        if isinstance(last_exception, HttpError):
            raise last_exception
        else:
            raise HttpError(f"HTTP request failed after {max_retries} retries: {last_exception}")
    
    def _make_request_requests(
        self,
        method: HttpMethod,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Union[str, bytes, Dict[str, Any]]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: int
    ) -> Tuple[int, Dict[str, Any], str]:
        """requests를 사용한 HTTP 요청"""
        if not REQUESTS_AVAILABLE or not self._session:
            raise HttpError("requests library not available")
        
        try:
            response = self._session.request(
                method.value,
                url,
                headers=headers,
                data=data,
                params=params,
                timeout=timeout
            )
            
            response.raise_for_status()
            return response.status_code, dict(response.headers), response.text
            
        except req.HTTPError as e:
            raise HttpError(
                f"HTTP {e.response.status_code}: {e.response.text}",
                status_code=e.response.status_code,
                response_text=e.response.text
            )
        except req.RequestException as e:
            raise HttpError(f"Request failed: {e}")
    
    def _make_request_urllib(
        self,
        method: HttpMethod,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Union[str, bytes]] = None,
        timeout: int
    ) -> Tuple[int, Dict[str, Any], str]:
        """urllib를 사용한 HTTP 요청"""
        # URL 파라미터 처리
        if "?" in url:
            url_parts = urllib.parse.urlparse(url)
            query_params = urllib.parse.parse_qs(url_parts.query)
            url = urllib.parse.urlunparse(url_parts._replace(query=""))
        
        # 요청 헤더 준비
        request_headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)
        
        # 요청 데이터 준비
        request_data = None
        if data:
            if isinstance(data, str):
                request_data = data.encode("utf-8")
            else:
                request_data = data
        
        # 요청 생성
        request = urllib.request.Request(url, data=request_data, headers=request_headers, method=method.value)
        
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response_text = response.read().decode("utf-8")
                response_headers = dict(response.headers)
                return response.status, response_headers, response_text
                
        except urllib.error.HTTPError as e:
            response_text = e.read().decode("utf-8") if e.fp else ""
            raise HttpError(
                f"HTTP {e.code}: {response_text}",
                status_code=e.code,
                response_text=response_text
            )
        except urllib.error.URLError as e:
            raise HttpError(f"URL error: {e.reason}")
    
    # ===== [05] CONVENIENCE METHODS ==========================================
    def get(self, url: str, **kwargs) -> Tuple[int, Dict[str, Any], str]:
        """GET 요청"""
        return self._make_request(HttpMethod.GET, url, **kwargs)
    
    def post(self, url: str, **kwargs) -> Tuple[int, Dict[str, Any], str]:
        """POST 요청"""
        return self._make_request(HttpMethod.POST, url, **kwargs)
    
    def put(self, url: str, **kwargs) -> Tuple[int, Dict[str, Any], str]:
        """PUT 요청"""
        return self._make_request(HttpMethod.PUT, url, **kwargs)
    
    def delete(self, url: str, **kwargs) -> Tuple[int, Dict[str, Any], str]:
        """DELETE 요청"""
        return self._make_request(HttpMethod.DELETE, url, **kwargs)
    
    def get_json(self, url: str, **kwargs) -> Dict[str, Any]:
        """JSON 응답을 받는 GET 요청"""
        status_code, headers, text = self.get(url, **kwargs)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise HttpError(f"Invalid JSON response: {e}")
    
    def post_json(self, url: str, json_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """JSON 데이터를 보내는 POST 요청"""
        status_code, headers, text = self.post(url, json_data=json_data, **kwargs)
        try:
            return json.loads(text) if text else {}
        except json.JSONDecodeError as e:
            raise HttpError(f"Invalid JSON response: {e}")
    
    # ===== [06] GITHUB API METHODS ===========================================
    def github_get(self, endpoint: str, token: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """GitHub API GET 요청"""
        url = f"{self.config.github_api_base}{endpoint}"
        headers = kwargs.get("headers", {})
        headers["Accept"] = self.config.github_accept_header
        
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        return self.get_json(url, headers=headers, **kwargs)
    
    def github_post(self, endpoint: str, data: Dict[str, Any], token: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """GitHub API POST 요청"""
        url = f"{self.config.github_api_base}{endpoint}"
        headers = kwargs.get("headers", {})
        headers["Accept"] = self.config.github_accept_header
        
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        return self.post_json(url, data, headers=headers, **kwargs)
    
    def github_get_file(self, owner: str, repo: str, path: str, token: Optional[str] = None, ref: str = "main") -> Optional[Dict[str, Any]]:
        """GitHub 파일 내용 조회"""
        endpoint = f"/repos/{owner}/{repo}/contents/{path}"
        params = {"ref": ref} if ref != "main" else {}
        
        try:
            return self.github_get(endpoint, token=token, params=params)
        except HttpError as e:
            if e.status_code == 404:
                return None
            raise
    
    def github_get_releases(self, owner: str, repo: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """GitHub 릴리스 목록 조회"""
        endpoint = f"/repos/{owner}/{repo}/releases"
        return self.github_get(endpoint, token=token)
    
    def github_get_latest_release(self, owner: str, repo: str, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """GitHub 최신 릴리스 조회"""
        endpoint = f"/repos/{owner}/{repo}/releases/latest"
        try:
            return self.github_get(endpoint, token=token)
        except HttpError as e:
            if e.status_code == 404:
                return None
            raise
    
    def github_get_release_by_tag(self, owner: str, repo: str, tag: str, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """GitHub 태그별 릴리스 조회"""
        endpoint = f"/repos/{owner}/{repo}/releases/tags/{tag}"
        try:
            return self.github_get(endpoint, token=token)
        except HttpError as e:
            if e.status_code == 404:
                return None
            raise
    
    def github_dispatch_workflow(self, owner: str, repo: str, workflow: str, ref: str, inputs: Dict[str, str], token: str) -> Dict[str, Any]:
        """GitHub 워크플로우 디스패치"""
        endpoint = f"/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
        data = {
            "ref": ref,
            "inputs": inputs
        }
        return self.github_post(endpoint, data, token=token)
    
    def github_repository_dispatch(self, owner: str, repo: str, event_type: str, client_payload: Dict[str, Any], token: str) -> Dict[str, Any]:
        """GitHub 리포지토리 디스패치"""
        endpoint = f"/repos/{owner}/{repo}/dispatches"
        data = {
            "event_type": event_type,
            "client_payload": client_payload
        }
        return self.github_post(endpoint, data, token=token)
    
    # ===== [07] GOOGLE DRIVE API METHODS =====================================
    def gdrive_get(self, endpoint: str, token: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Google Drive API GET 요청"""
        url = f"{self.config.gdrive_api_base}{endpoint}"
        headers = kwargs.get("headers", {})
        
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        return self.get_json(url, headers=headers, **kwargs)
    
    def gdrive_list_files(self, folder_id: str, token: str, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Google Drive 폴더 내 파일 목록 조회"""
        params = {"q": f"'{folder_id}' in parents"}
        if query:
            params["q"] += f" and {query}"
        
        response = self.gdrive_get("/files", token=token, params=params)
        return response.get("files", [])
    
    def gdrive_download_file(self, file_id: str, token: str) -> bytes:
        """Google Drive 파일 다운로드"""
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        headers = {"Authorization": f"Bearer {token}"}
        
        status_code, response_headers, response_text = self.get(url, headers=headers)
        return response_text.encode("utf-8")

# ===== [08] SINGLETON PATTERN ================================================
_http_client_instance: Optional[HttpClient] = None

def get_http_client() -> HttpClient:
    """HTTP 클라이언트 싱글톤 인스턴스 반환"""
    global _http_client_instance
    if _http_client_instance is None:
        _http_client_instance = HttpClient()
    return _http_client_instance

# ===== [09] CONVENIENCE FUNCTIONS ============================================
def http_get(url: str, **kwargs) -> Tuple[int, Dict[str, Any], str]:
    """GET 요청 편의 함수"""
    return get_http_client().get(url, **kwargs)

def http_post(url: str, **kwargs) -> Tuple[int, Dict[str, Any], str]:
    """POST 요청 편의 함수"""
    return get_http_client().post(url, **kwargs)

def http_get_json(url: str, **kwargs) -> Dict[str, Any]:
    """JSON GET 요청 편의 함수"""
    return get_http_client().get_json(url, **kwargs)

def http_post_json(url: str, json_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """JSON POST 요청 편의 함수"""
    return get_http_client().post_json(url, json_data, **kwargs)

# ===== [10] END ==============================================================
