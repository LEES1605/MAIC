# ===== [01] FILE: src/runtime/sequential_release.py — START =====
"""
순차번호 기반 릴리스 관리 시스템

특징:
- index-1, index-2, index-3, ... (숫자가 클수록 최신)
- prompts-1, prompts-2, prompts-3, ... (동일한 패턴)
- 예측 가능하고 안정적인 버전 관리
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .gh_release import GHConfig, GHReleases, GHError


class SequentialReleaseManager:
    """순차번호 기반 릴리스 관리자"""
    
    def __init__(self, gh_client: GHReleases):
        self.gh = gh_client
    
    def get_next_number(self, prefix: str) -> int:
        """다음 릴리스 번호를 자동으로 계산 (하이브리드: 순차번호 우선)"""
        releases = self.gh.list_releases(per_page=100)
        max_sequential = 0
        max_timestamp = 0
        
        for release in releases:
            tag = release.get('tag_name', '')
            if tag.startswith(f"{prefix}-"):
                try:
                    # prefix-123 형태에서 숫자 추출
                    num_str = tag[len(prefix) + 1:]  # prefix- 제거
                    num = int(num_str)
                    
                    # 순차번호 시스템 (1, 2, 3, ...) 우선
                    if num <= 1000:  # 순차번호로 가정
                        max_sequential = max(max_sequential, num)
                    else:
                        # 타임스탬프 시스템 (1759256021 등)
                        max_timestamp = max(max_timestamp, num)
                except (ValueError, IndexError):
                    continue
        
        # 순차번호가 있으면 순차번호 사용, 없으면 타임스탬프 기반으로 시작
        if max_sequential > 0:
            return max_sequential + 1
        else:
            # 타임스탬프가 있으면 1부터 시작, 없으면 1부터 시작
            return 1
    
    def find_latest_by_number(self, prefix: str) -> Optional[Dict[str, Any]]:
        """숫자 기반으로 최신 릴리스 찾기 (하이브리드: 순차번호 + 타임스탬프)"""
        print(f"[DEBUG] find_latest_by_number called with prefix: '{prefix}'")
        releases = self.gh.list_releases(per_page=100)
        print(f"[DEBUG] Found {len(releases)} releases in find_latest_by_number: {[r.get('tag_name') for r in releases]}")
        
        # 각 릴리스 태그 상세 분석
        for i, release in enumerate(releases):
            tag = release.get('tag_name', '')
            print(f"[DEBUG] Release {i}: tag='{tag}', starts_with_{prefix}-={tag.startswith(f'{prefix}-')}")
        
        latest_num = 0
        latest_release = None
        latest_timestamp = 0
        
        # 릴리스 검색 로직 실행 (항상 실행)
        for release in releases:
            tag = release.get('tag_name', '')
            if tag.startswith(f"{prefix}-"):
                try:
                    num_str = tag[len(prefix) + 1:]
                    num = int(num_str)
                    print(f"[DEBUG] Tag {tag} -> number {num}")
                    
                    if num <= 1000:
                        if num > latest_num:
                            latest_num = num
                            latest_release = release
                            print(f"[DEBUG] New sequential latest: {tag} (num={num})")
                    else:
                        if num > latest_timestamp:
                            latest_timestamp = num
                            if latest_release is None:
                                latest_release = release
                                print(f"[DEBUG] New timestamp latest: {tag} (num={num})")
                except (ValueError, IndexError) as e:
                    print(f"[DEBUG] Failed to parse tag {tag}: {e}")
                    continue
        print(f"[DEBUG] Final result: latest_release={latest_release.get('tag_name') if latest_release else None}")
        return latest_release
    
    def create_index_release(self, zip_path: Path, *, title: Optional[str] = None, notes: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        """인덱스 릴리스 생성"""
        num = self.get_next_number("index")
        tag = f"index-{num}"
        
        title = title or f"Index Release {num}"
        notes = notes or f"Sequential index release #{num}"
        
        release = self.gh.ensure_release(tag, title=title, notes=notes)
        asset = self.gh.upload_asset(tag=tag, file_path=zip_path, asset_name=zip_path.name, clobber=True)
        
        return tag, release
    
    def create_prompts_release(self, yaml_path: Path, *, title: Optional[str] = None, notes: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        """프롬프트 릴리스 생성"""
        num = self.get_next_number("prompts")
        tag = f"prompts-{num}"
        
        title = title or f"Prompts Release {num}"
        notes = notes or f"Sequential prompts release #{num}"
        
        release = self.gh.ensure_release(tag, title=title, notes=notes)
        asset = self.gh.upload_asset(tag=tag, file_path=yaml_path, asset_name=yaml_path.name, clobber=True)
        
        return tag, release
    
    def restore_latest_index(self, dest: Path, *, clean_dest: bool = False) -> Dict[str, Any]:
        """최신 인덱스 복원"""
        latest_release = self.find_latest_by_number("index")
        if not latest_release:
            raise GHError("No index releases found")
        
        tag = latest_release.get('tag_name')
        assets = latest_release.get('assets', [])
        
        if not assets:
            release_id = latest_release.get('id')
            if release_id:
                assets = self.gh._list_assets(int(release_id))
        
        # 디버깅: 사용 가능한 자산들 로그
        print(f"[DEBUG] Available assets in release {tag}: {[a.get('name') for a in assets]}")
        
        # 자산 선택 (index*.tar.gz 우선, 그 다음 .zip)
        chosen_asset = None
        for asset in assets:
            name = asset.get('name', '').lower()
            if name == 'index.tar.gz':
                chosen_asset = asset
                print(f"[DEBUG] Selected exact match: {name}")
                break
            elif name.startswith('index') and name.endswith('.tar.gz') and not chosen_asset:
                chosen_asset = asset
                print(f"[DEBUG] Selected index pattern: {name}")
            elif name.endswith('.zip') and not chosen_asset:
                chosen_asset = asset
                print(f"[DEBUG] Selected zip fallback: {name}")
        
        if not chosen_asset:
            raise GHError(f"No suitable asset found in release {tag}")
        
        # 다운로드 및 압축 해제
        try:
            print(f"[DEBUG] Downloading asset: {chosen_asset.get('name')}")
            data = self.gh._download_asset(chosen_asset.get('browser_download_url'))
            print(f"[DEBUG] Download successful: {len(data)} bytes")
        except Exception as e:
            print(f"[DEBUG] Download failed: {e}")
            raise GHError(f"Failed to download asset: {e}")
        
        # persist 디렉토리 생성 및 권한 확인
        try:
            dest.mkdir(parents=True, exist_ok=True)
            print(f"[DEBUG] Created/verified persist directory: {dest}")
            
            # 권한 확인
            if not os.access(dest, os.W_OK):
                print(f"[DEBUG] WARNING: No write permission to {dest}")
                # 권한 문제 시 다른 경로 시도
                alt_dest = Path.home() / "maic_persist"
                alt_dest.mkdir(parents=True, exist_ok=True)
                if os.access(alt_dest, os.W_OK):
                    print(f"[DEBUG] Using alternative path: {alt_dest}")
                    dest = alt_dest
                else:
                    raise PermissionError(f"Cannot write to {dest} or {alt_dest}")
        except Exception as e:
            print(f"[DEBUG] Directory creation failed: {e}")
            raise
        
        if clean_dest:
            self._clean_destination(dest)
        
        try:
            print(f"[DEBUG] Extracting {chosen_asset.get('name')} to {dest}")
            self.gh._extract_bytes_to(dest, chosen_asset.get('name'), data)
            print(f"[DEBUG] Extraction completed")
        except Exception as e:
            print(f"[DEBUG] Extraction failed: {e}")
            raise GHError(f"Failed to extract asset: {e}")
        
        # 복원 후 파일 존재 확인
        chunks_file = dest / 'chunks.jsonl'
        if chunks_file.exists():
            print(f"[DEBUG] chunks.jsonl created successfully: {chunks_file.stat().st_size} bytes")
        else:
            print(f"[DEBUG] WARNING: chunks.jsonl not found after extraction")
            # 디렉토리 내용 확인
            try:
                files = list(dest.rglob('*'))
                print(f"[DEBUG] Files in destination: {[f.name for f in files]}")
            except Exception as e:
                print(f"[DEBUG] Failed to list files: {e}")
        
        # 복원 후 검증
        self._verify_restoration(dest, chosen_asset.get('name'))
        
        # 최종 검증
        final_chunks = dest / 'chunks.jsonl'
        if not final_chunks.exists():
            print(f"[DEBUG] FINAL WARNING: chunks.jsonl still not found at {final_chunks}")
            # 절대 경로로 다시 확인
            abs_chunks = Path(final_chunks).resolve()
            if abs_chunks.exists():
                print(f"[DEBUG] Found chunks.jsonl at absolute path: {abs_chunks}")
            else:
                print(f"[DEBUG] chunks.jsonl not found at absolute path either")
        
        return {
            'tag': tag,
            'release_id': latest_release.get('id'),
            'asset_name': chosen_asset.get('name'),
            'detail': f"restored {tag} to {dest}",
            'final_path': str(dest.resolve()),
            'chunks_exists': final_chunks.exists()
        }
    
    def restore_latest_prompts(self, dest: Path) -> Dict[str, Any]:
        """최신 프롬프트 복원"""
        latest_release = self.find_latest_by_number("prompts")
        if not latest_release:
            raise GHError("No prompts releases found")
        
        tag = latest_release.get('tag_name')
        assets = latest_release.get('assets', [])
        
        if not assets:
            release_id = latest_release.get('id')
            if release_id:
                assets = self.gh._list_assets(int(release_id))
        
        # 프롬프트 파일 선택 (.yaml 우선, 그 다음 .json)
        chosen_asset = None
        for asset in assets:
            name = asset.get('name', '').lower()
            if name.endswith('.yaml') or name.endswith('.yml'):
                chosen_asset = asset
                break
            elif name.endswith('.json') and not chosen_asset:
                chosen_asset = asset
        
        if not chosen_asset:
            raise GHError(f"No suitable prompts asset found in release {tag}")
        
        # 다운로드
        data = self.gh._download_asset(chosen_asset.get('browser_download_url'))
        dest.mkdir(parents=True, exist_ok=True)
        (dest / chosen_asset.get('name')).write_bytes(data)
        
        return {
            'tag': tag,
            'release_id': latest_release.get('id'),
            'asset_name': chosen_asset.get('name'),
            'detail': f"restored {tag} to {dest}"
        }
    
    def _clean_destination(self, dest: Path) -> None:
        """대상 디렉터리 정리"""
        import shutil
        try:
            dest.mkdir(parents=True, exist_ok=True)
            for child in list(dest.iterdir()):
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
        except FileNotFoundError:
            dest.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            raise GHError(f"failed to clean destination '{dest}': permission denied: {e}") from e
        except Exception as e:
            raise GHError(f"failed to clean destination '{dest}': {e}") from e
    
    def _verify_restoration(self, dest: Path, asset_name: str) -> None:
        """복원 후 검증"""
        chunks_file = dest / "chunks.jsonl"
        if not chunks_file.exists() or chunks_file.stat().st_size == 0:
            # 하위 디렉터리에서 찾기
            found_chunks = None
            for subdir in dest.iterdir():
                if subdir.is_dir():
                    candidate = subdir / "chunks.jsonl"
                    if candidate.exists() and candidate.stat().st_size > 0:
                        found_chunks = candidate
                        break
            
            if found_chunks:
                # 하위 디렉터리의 파일들을 상위로 이동
                import shutil
                shutil.move(str(found_chunks), str(chunks_file))
                for item in found_chunks.parent.iterdir():
                    if item != found_chunks:
                        target = dest / item.name
                        if item.is_file():
                            shutil.move(str(item), str(target))
                        elif item.is_dir() and not target.exists():
                            shutil.move(str(item), str(target))
            else:
                raise GHError(f"복원 후 chunks.jsonl 파일을 찾을 수 없습니다. 압축 파일 구조를 확인하세요: {asset_name}")


def create_sequential_manager(owner: str, repo: str, token: str) -> SequentialReleaseManager:
    """순차번호 릴리스 관리자 생성"""
    gh = GHReleases(GHConfig(owner=owner, repo=repo, token=token))
    return SequentialReleaseManager(gh)


# ===== [01] FILE: src/runtime/sequential_release.py — END =====
