# ===== [01] PURPOSE ==========================================================
# 통합 GitHub API 클라이언트 - GitHub API 호출을 단일 클라이언트로 통합
# 인증 관리 통합, 에러 처리 표준화, 레이트 리미팅 처리

# ===== [02] IMPORTS ==========================================================
from __future__ import annotations

import time
import json
from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from src.core.http_client import get_http_client, HttpClient, HttpError

# ===== [03] CONFIGURATION ====================================================
@dataclass
class GitHubConfig:
    """GitHub API 설정"""
    api_base: str = "https://api.github.com"
    accept_header: str = "application/vnd.github+json"
    user_agent: str = "MAIC-GitHubClient/1.0"
    
    # 레이트 리미팅 설정
    rate_limit_enabled: bool = True
    rate_limit_retry_delay: float = 1.0
    rate_limit_max_retries: int = 3
    
    # 타임아웃 설정
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    backoff_factor: float = 2.0

class GitHubError(Exception):
    """GitHub API 에러"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data

class RateLimitError(GitHubError):
    """레이트 리미트 에러"""
    def __init__(self, message: str, reset_time: Optional[int] = None):
        super().__init__(message)
        self.reset_time = reset_time

# ===== [04] RATE LIMIT MANAGER ===============================================
class RateLimitManager:
    """레이트 리미트 관리자"""
    
    def __init__(self, config: GitHubConfig):
        self.config = config
        self._rate_limit_info: Dict[str, Any] = {}
        self._last_check = 0
    
    def _get_rate_limit_info(self, http_client: HttpClient, token: Optional[str] = None) -> Dict[str, Any]:
        """레이트 리미트 정보 조회"""
        try:
            headers = {"Accept": self.config.accept_header}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            
            status_code, response_headers, response_text = http_client.get(
                f"{self.config.api_base}/rate_limit",
                headers=headers,
                timeout=self.config.timeout
            )
            
            if status_code == 200:
                return json.loads(response_text)
            else:
                return {}
        except Exception:
            return {}
    
    def check_rate_limit(self, http_client: HttpClient, token: Optional[str] = None) -> bool:
        """레이트 리미트 확인"""
        if not self.config.rate_limit_enabled:
            return True
        
        current_time = time.time()
        
        # 캐시된 정보가 있으면 사용 (1분간 유효)
        if current_time - self._last_check < 60 and self._rate_limit_info:
            return self._is_rate_limit_ok()
        
        # 새로운 정보 조회
        self._rate_limit_info = self._get_rate_limit_info(http_client, token)
        self._last_check = current_time
        
        return self._is_rate_limit_ok()
    
    def _is_rate_limit_ok(self) -> bool:
        """레이트 리미트 상태 확인"""
        if not self._rate_limit_info:
            return True
        
        core_info = self._rate_limit_info.get("resources", {}).get("core", {})
        remaining = core_info.get("remaining", 0)
        reset_time = core_info.get("reset", 0)
        
        # 남은 요청이 있으면 OK
        if remaining > 0:
            return True
        
        # 리셋 시간이 지났으면 OK
        if reset_time > 0 and time.time() >= reset_time:
            return True
        
        return False
    
    def wait_for_rate_limit_reset(self, http_client: HttpClient, token: Optional[str] = None) -> None:
        """레이트 리미트 리셋까지 대기"""
        if not self.config.rate_limit_enabled:
            return
        
        # 최신 정보 조회
        self._rate_limit_info = self._get_rate_limit_info(http_client, token)
        
        core_info = self._rate_limit_info.get("resources", {}).get("core", {})
        reset_time = core_info.get("reset", 0)
        
        if reset_time > 0:
            wait_time = reset_time - time.time()
            if wait_time > 0:
                time.sleep(wait_time + 1)  # 1초 여유

# ===== [05] GITHUB CLIENT CLASS ==============================================
class GitHubClient:
    """통합 GitHub API 클라이언트"""
    
    def __init__(self, config: Optional[GitHubConfig] = None, http_client: Optional[HttpClient] = None):
        self.config = config or GitHubConfig()
        self.http_client = http_client or get_http_client()
        self.rate_limit_manager = RateLimitManager(self.config)
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        token: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        retries: Optional[int] = None
    ) -> Dict[str, Any]:
        """GitHub API 요청 실행"""
        url = f"{self.config.api_base}{endpoint}"
        max_retries = retries or self.config.max_retries
        
        # 헤더 준비
        headers = {
            "Accept": self.config.accept_header,
            "User-Agent": self.config.user_agent
        }
        
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        # 레이트 리미트 확인
        if not self.rate_limit_manager.check_rate_limit(self.http_client, token):
            self.rate_limit_manager.wait_for_rate_limit_reset(self.http_client, token)
        
        # 재시도 로직
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                if method.upper() == "GET":
                    response = self.http_client.get_json(url, headers=headers, params=params, timeout=self.config.timeout)
                elif method.upper() == "POST":
                    response = self.http_client.post_json(url, data or {}, headers=headers, timeout=self.config.timeout)
                elif method.upper() == "PUT":
                    response = self.http_client.put(url, json_data=data, headers=headers, timeout=self.config.timeout)
                elif method.upper() == "DELETE":
                    response = self.http_client.delete(url, headers=headers, timeout=self.config.timeout)
                else:
                    raise GitHubError(f"지원하지 않는 HTTP 메서드: {method}")
                
                return response
                
            except HttpError as e:
                last_exception = e
                
                # 레이트 리미트 에러 처리
                if e.status_code == 403 and "rate limit" in str(e).lower():
                    if attempt < max_retries:
                        self.rate_limit_manager.wait_for_rate_limit_reset(self.http_client, token)
                        continue
                    else:
                        raise RateLimitError(f"레이트 리미트 초과: {e}")
                
                # 404 에러는 재시도하지 않음
                if e.status_code == 404:
                    raise GitHubError(f"리소스를 찾을 수 없습니다: {e}", e.status_code)
                
                # 다른 에러는 재시도
                if attempt < max_retries:
                    delay = self.config.retry_delay * (self.config.backoff_factor ** attempt)
                    time.sleep(delay)
                    continue
                else:
                    raise GitHubError(f"GitHub API 요청 실패: {e}", e.status_code)
            
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    delay = self.config.retry_delay * (self.config.backoff_factor ** attempt)
                    time.sleep(delay)
                    continue
                else:
                    raise GitHubError(f"예상치 못한 오류: {e}")
        
        # 모든 재시도 실패
        raise GitHubError(f"GitHub API 요청이 {max_retries}번 재시도 후 실패했습니다", original_error=last_exception)
    
    # ===== [06] REPOSITORY METHODS ===========================================
    def get_repository(self, owner: str, repo: str, token: Optional[str] = None) -> Dict[str, Any]:
        """리포지토리 정보 조회"""
        endpoint = f"/repos/{owner}/{repo}"
        return self._make_request("GET", endpoint, token)
    
    def list_repositories(self, owner: str, token: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """리포지토리 목록 조회"""
        endpoint = f"/users/{owner}/repos"
        params = {
            "type": kwargs.get("type", "all"),
            "sort": kwargs.get("sort", "updated"),
            "direction": kwargs.get("direction", "desc"),
            "per_page": kwargs.get("per_page", 100)
        }
        return self._make_request("GET", endpoint, token, params=params)
    
    # ===== [07] RELEASES METHODS =============================================
    def get_releases(self, owner: str, repo: str, token: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """릴리스 목록 조회"""
        endpoint = f"/repos/{owner}/{repo}/releases"
        params = {
            "per_page": kwargs.get("per_page", 100),
            "page": kwargs.get("page", 1)
        }
        return self._make_request("GET", endpoint, token, params=params)
    
    def get_latest_release(self, owner: str, repo: str, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """최신 릴리스 조회"""
        endpoint = f"/repos/{owner}/{repo}/releases/latest"
        try:
            return self._make_request("GET", endpoint, token)
        except GitHubError as e:
            if e.status_code == 404:
                return None
            raise
    
    def get_release_by_tag(self, owner: str, repo: str, tag: str, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """태그별 릴리스 조회"""
        endpoint = f"/repos/{owner}/{repo}/releases/tags/{tag}"
        try:
            return self._make_request("GET", endpoint, token)
        except GitHubError as e:
            if e.status_code == 404:
                return None
            raise
    
    def create_release(
        self,
        owner: str,
        repo: str,
        tag_name: str,
        token: str,
        **kwargs
    ) -> Dict[str, Any]:
        """릴리스 생성"""
        endpoint = f"/repos/{owner}/{repo}/releases"
        data = {
            "tag_name": tag_name,
            "name": kwargs.get("name", tag_name),
            "body": kwargs.get("body", ""),
            "draft": kwargs.get("draft", False),
            "prerelease": kwargs.get("prerelease", False)
        }
        return self._make_request("POST", endpoint, token, data=data)
    
    # ===== [08] CONTENTS METHODS =============================================
    def get_file_contents(
        self,
        owner: str,
        repo: str,
        path: str,
        token: Optional[str] = None,
        ref: str = "main"
    ) -> Optional[Dict[str, Any]]:
        """파일 내용 조회"""
        endpoint = f"/repos/{owner}/{repo}/contents/{path}"
        params = {"ref": ref} if ref != "main" else {}
        try:
            return self._make_request("GET", endpoint, token, params=params)
        except GitHubError as e:
            if e.status_code == 404:
                return None
            raise
    
    def create_or_update_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        token: str,
        **kwargs
    ) -> Dict[str, Any]:
        """파일 생성 또는 업데이트"""
        endpoint = f"/repos/{owner}/{repo}/contents/{path}"
        
        # 기존 파일이 있는지 확인
        existing_file = self.get_file_contents(owner, repo, path, token, kwargs.get("branch", "main"))
        
        data = {
            "message": message,
            "content": content,
            "branch": kwargs.get("branch", "main")
        }
        
        if existing_file:
            data["sha"] = existing_file["sha"]
        
        return self._make_request("PUT", endpoint, token, data=data)
    
    def delete_file(
        self,
        owner: str,
        repo: str,
        path: str,
        message: str,
        token: str,
        **kwargs
    ) -> Dict[str, Any]:
        """파일 삭제"""
        endpoint = f"/repos/{owner}/{repo}/contents/{path}"
        
        # 기존 파일 정보 조회
        existing_file = self.get_file_contents(owner, repo, path, token, kwargs.get("branch", "main"))
        if not existing_file:
            raise GitHubError(f"파일을 찾을 수 없습니다: {path}")
        
        data = {
            "message": message,
            "sha": existing_file["sha"],
            "branch": kwargs.get("branch", "main")
        }
        
        return self._make_request("DELETE", endpoint, token, data=data)
    
    # ===== [09] WORKFLOWS METHODS ============================================
    def list_workflows(self, owner: str, repo: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """워크플로우 목록 조회"""
        endpoint = f"/repos/{owner}/{repo}/actions/workflows"
        response = self._make_request("GET", endpoint, token)
        return response.get("workflows", [])
    
    def get_workflow(self, owner: str, repo: str, workflow_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """워크플로우 정보 조회"""
        endpoint = f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}"
        return self._make_request("GET", endpoint, token)
    
    def dispatch_workflow(
        self,
        owner: str,
        repo: str,
        workflow_id: str,
        ref: str,
        inputs: Dict[str, str],
        token: str
    ) -> Dict[str, Any]:
        """워크플로우 디스패치"""
        endpoint = f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches"
        data = {
            "ref": ref,
            "inputs": inputs
        }
        return self._make_request("POST", endpoint, token, data=data)
    
    def repository_dispatch(
        self,
        owner: str,
        repo: str,
        event_type: str,
        client_payload: Dict[str, Any],
        token: str
    ) -> Dict[str, Any]:
        """리포지토리 디스패치"""
        endpoint = f"/repos/{owner}/{repo}/dispatches"
        data = {
            "event_type": event_type,
            "client_payload": client_payload
        }
        return self._make_request("POST", endpoint, token, data=data)
    
    # ===== [10] ASSETS METHODS ===============================================
    def download_asset(
        self,
        owner: str,
        repo: str,
        release_id: int,
        asset_id: int,
        token: Optional[str] = None
    ) -> bytes:
        """릴리스 자산 다운로드"""
        endpoint = f"/repos/{owner}/{repo}/releases/assets/{asset_id}"
        
        headers = {
            "Accept": "application/octet-stream",
            "User-Agent": self.config.user_agent
        }
        
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        url = f"{self.config.api_base}{endpoint}"
        status_code, response_headers, response_text = self.http_client.get(url, headers=headers, timeout=self.config.timeout)
        
        if status_code == 200:
            return response_text.encode("utf-8")
        else:
            raise GitHubError(f"자산 다운로드 실패: HTTP {status_code}", status_code)
    
    def upload_asset(
        self,
        owner: str,
        repo: str,
        release_id: int,
        asset_path: Union[str, Path],
        asset_name: str,
        token: str
    ) -> Dict[str, Any]:
        """릴리스 자산 업로드"""
        # 자산 업로드 URL 조회
        release = self._make_request("GET", f"/repos/{owner}/{repo}/releases/{release_id}", token)
        upload_url = release.get("upload_url", "").replace("{?name,label}", "")
        
        if not upload_url:
            raise GitHubError("업로드 URL을 찾을 수 없습니다")
        
        # 파일 읽기
        asset_path = Path(asset_path)
        if not asset_path.exists():
            raise GitHubError(f"자산 파일이 존재하지 않습니다: {asset_path}")
        
        file_content = asset_path.read_bytes()
        
        # 업로드
        headers = {
            "Content-Type": "application/octet-stream",
            "Authorization": f"Bearer {token}"
        }
        
        params = {"name": asset_name}
        
        try:
            status_code, response_headers, response_text = self.http_client.post(
                upload_url,
                data=file_content,
                headers=headers,
                params=params,
                timeout=self.config.timeout
            )
            
            if status_code == 201:
                return json.loads(response_text)
            else:
                raise GitHubError(f"자산 업로드 실패: HTTP {status_code}", status_code)
        except HttpError as e:
            raise GitHubError(f"자산 업로드 실패: {e}", e.status_code)
    
    # ===== [11] UTILITY METHODS ==============================================
    def get_rate_limit(self, token: Optional[str] = None) -> Dict[str, Any]:
        """레이트 리미트 정보 조회"""
        endpoint = "/rate_limit"
        return self._make_request("GET", endpoint, token)
    
    def search_repositories(self, query: str, token: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """리포지토리 검색"""
        endpoint = "/search/repositories"
        params = {
            "q": query,
            "sort": kwargs.get("sort", "stars"),
            "order": kwargs.get("order", "desc"),
            "per_page": kwargs.get("per_page", 30),
            "page": kwargs.get("page", 1)
        }
        return self._make_request("GET", endpoint, token, params=params)
    
    def get_user(self, username: str, token: Optional[str] = None) -> Dict[str, Any]:
        """사용자 정보 조회"""
        endpoint = f"/users/{username}"
        return self._make_request("GET", endpoint, token)
    
    def get_authenticated_user(self, token: str) -> Dict[str, Any]:
        """인증된 사용자 정보 조회"""
        endpoint = "/user"
        return self._make_request("GET", endpoint, token)

# ===== [12] SINGLETON PATTERN ================================================
_github_client_instance: Optional[GitHubClient] = None

def get_github_client() -> GitHubClient:
    """GitHub 클라이언트 싱글톤 인스턴스 반환"""
    global _github_client_instance
    if _github_client_instance is None:
        _github_client_instance = GitHubClient()
    return _github_client_instance

# ===== [13] CONVENIENCE FUNCTIONS ============================================
def github_get_releases(owner: str, repo: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
    """릴리스 목록 조회 편의 함수"""
    return get_github_client().get_releases(owner, repo, token)

def github_get_latest_release(owner: str, repo: str, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """최신 릴리스 조회 편의 함수"""
    return get_github_client().get_latest_release(owner, repo, token)

def github_get_file_contents(owner: str, repo: str, path: str, token: Optional[str] = None, ref: str = "main") -> Optional[Dict[str, Any]]:
    """파일 내용 조회 편의 함수"""
    return get_github_client().get_file_contents(owner, repo, path, token, ref)

def github_dispatch_workflow(owner: str, repo: str, workflow_id: str, ref: str, inputs: Dict[str, str], token: str) -> Dict[str, Any]:
    """워크플로우 디스패치 편의 함수"""
    return get_github_client().dispatch_workflow(owner, repo, workflow_id, ref, inputs, token)

def github_repository_dispatch(owner: str, repo: str, event_type: str, client_payload: Dict[str, Any], token: str) -> Dict[str, Any]:
    """리포지토리 디스패치 편의 함수"""
    return get_github_client().repository_dispatch(owner, repo, event_type, client_payload, token)

# ===== [14] END ==============================================================
