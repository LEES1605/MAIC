"""
MAIC 복원 서비스 모듈

app.py에서 분리된 복원 관련 로직을 담당합니다.
- 자동 복원 로직
- GitHub 릴리스 관리
- 메타데이터 처리
- 순차번호 기반 복원
"""

import os
import time
import importlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.infrastructure.core.persist import effective_persist_dir


class RestoreService:
    """복원 관련 서비스 클래스"""
    
    def __init__(self):
        self._persist_dir = None
    
    @property
    def persist_dir(self) -> Path:
        """안전한 persist 디렉토리 경로"""
        if self._persist_dir is None:
            try:
                self._persist_dir = Path(str(effective_persist_dir())).expanduser()
            except Exception:
                self._persist_dir = Path.home() / ".maic" / "persist"
        return self._persist_dir
    
    def _idx(self, name: str, *args, **kwargs):
        """인덱스 상태 관리 함수 호출"""
        try:
            mod = importlib.import_module("src.services.index_state")
            fn = getattr(mod, name, None)
            if callable(fn):
                return fn(*args, **kwargs)
        except Exception:
            return None
    
    def _safe_load_meta(self, path: Path):
        """안전한 메타데이터 로드"""
        try:
            from src.infrastructure.runtime.local_restore import load_restore_meta
            return load_restore_meta(path)
        except Exception:
            return None
    
    def _safe_meta_tag_matches(self, meta, tag: str) -> bool:
        """안전한 메타 태그 매칭"""
        try:
            from src.infrastructure.runtime.local_restore import meta_matches_tag
            return bool(meta_matches_tag(meta, tag))
        except Exception:
            return False
    
    def _safe_meta_release_id(self, meta) -> Optional[int]:
        """안전한 메타 릴리스 ID 추출"""
        try:
            for k in ("release_id", "releaseId", "id"):
                v = getattr(meta, k, None)
                if v is not None:
                    return int(v)
        except Exception:
            pass
        try:
            if isinstance(meta, dict):
                for k in ("release_id", "releaseId", "id"):
                    v = meta.get(k)
                    if v is not None:
                        return int(v)
        except Exception:
            pass
        return None
    
    def _safe_save_meta(self, path: Path, tag=None, release_id=None):
        """안전한 메타데이터 저장"""
        try:
            from src.infrastructure.runtime.local_restore import save_restore_meta
            return save_restore_meta(path, tag=tag, release_id=release_id)
        except Exception:
            return None
    
    def _get_github_config(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """GitHub 설정 가져오기"""
        repo_full = os.getenv("GITHUB_REPO", "")
        token = os.getenv("GITHUB_TOKEN", None)
        
        try:
            import streamlit as st
            # Streamlit secrets에서 가져오기 (온라인 배포용)
            repo_full = st.secrets.get("GITHUB_REPO", repo_full)
            token = st.secrets.get("GITHUB_TOKEN", token)
            
            # 온라인 환경 디버그 정보
            print(f"[DEBUG] 온라인 환경 감지: st.secrets 사용")
            print(f"[DEBUG] GITHUB_REPO from secrets: {repo_full}")
            print(f"[DEBUG] GITHUB_TOKEN from secrets: {'SET' if token else 'NOT_SET'}")
            
            # 로컬 개발용 디버그 정보
            if st.secrets.get("MAIC_LOCAL_DEV", False):
                print(f"[DEBUG] 로컬 개발 모드: {st.secrets.get('MAIC_DEBUG', False)}")
        except Exception as e:
            print(f"[DEBUG] secrets 접근 실패: {e}")
            pass
        
        if not repo_full or "/" not in str(repo_full):
            return None, None, None
        
        owner, repo = str(repo_full).split("/", 1)
        return owner, repo, token
    
    def _get_ready_functions(self):
        """준비 상태 확인 함수들 가져오기"""
        try:
            from src.infrastructure.core.readiness import is_ready_text, normalize_ready_file
            return is_ready_text, normalize_ready_file
        except Exception:
            def _norm(x: str | bytes | None) -> str:
                if x is None:
                    return ""
                if isinstance(x, bytes):
                    x = x.decode("utf-8", "ignore")
                return x.replace("\ufeff", "").strip().lower()
            
            def is_ready_text(x):
                return _norm(x) in {"ready", "ok", "true", "1", "on", "yes", "y", "green"}
            
            def normalize_ready_file(_):
                try:
                    (self.persist_dir / ".ready").write_text("ready", encoding="utf-8")
                    return True
                except Exception:
                    return False
            
            return is_ready_text, normalize_ready_file
    
    def boot_auto_restore_index(self) -> None:
        """
        최신 릴리스 자동 복원 훅.
        규칙(개선):
          - 로컬 준비 기록(_INDEX_LOCAL_READY)은 그대로 유지
          - 원격 최신과의 일치 판정은 **release_id 우선**, 없을 때만 tag 비교로 폴백
          - 일치하지 않으면 복원 강제
          - 복원 성공 시에만 _INDEX_IS_LATEST=True

        UI 연동(진행표시 훅): 플레이스홀더 생성은 [19]에서만 수행
        """
        # 무한 루프 방지: 세션 상태 체크 강화
        try:
            import streamlit as st
            # 이미 복원이 완료되었으면 스킵
            if st.session_state.get("_BOOT_RESTORE_DONE", False):
                print(f"[DEBUG] Skipping restore - already done: {st.session_state.get('_BOOT_RESTORE_DONE')}")
                return
            
            # 무한 루프 방지: 복원 시도 횟수 제한
            restore_attempts = st.session_state.get("_RESTORE_ATTEMPTS", 0)
            if restore_attempts >= 3:
                print(f"[DEBUG] Too many restore attempts ({restore_attempts}), skipping to prevent infinite loop")
                st.session_state["_BOOT_RESTORE_DONE"] = True
                return
            
            # 복원 시도 횟수 증가
            st.session_state["_RESTORE_ATTEMPTS"] = restore_attempts + 1
            print(f"[DEBUG] Restore attempt {restore_attempts + 1}/3")
        except Exception as e:
            print(f"[DEBUG] Error in restore loop prevention: {e}")
            pass

        self._idx("ensure_index_state")
        self._idx("log", "부팅: 인덱스 복원 준비 중...")
        
        p = self.persist_dir
        print(f"[DEBUG] Starting restore process - persist_dir: {p}")
        cj = p / "chunks.jsonl"
        rf = p / ".ready"

        # --- 공용 판정기 로드 ---
        is_ready_text, normalize_ready_file = self._get_ready_functions()

        # --- 로컬 준비 상태 ---
        self._idx("step_set", 1, "run", "로컬 준비 상태 확인")
        print(f"[DEBUG] Checking local files: cj={cj}, rf={rf}")
        print(f"[DEBUG] cj.exists(): {cj.exists()}")
        if cj.exists():
            print(f"[DEBUG] cj.size(): {cj.stat().st_size}")
        print(f"[DEBUG] rf.exists(): {rf.exists()}")
        
        ready_txt = ""
        try:
            if rf.exists():
                ready_txt = rf.read_text(encoding="utf-8")
                print(f"[DEBUG] ready_txt content: {repr(ready_txt)}")
        except Exception as e:
            print(f"[DEBUG] Error reading ready file: {e}")
            ready_txt = ""
        
        local_ready = cj.exists() and cj.stat().st_size > 0 and is_ready_text(ready_txt)
        print(f"[DEBUG] local_ready calculation: cj.exists()={cj.exists()}, cj.size()={cj.stat().st_size if cj.exists() else 0}, is_ready_text()={is_ready_text(ready_txt)}")
        self._idx("log", f"로컬 준비: {'OK' if local_ready else '미검출'}")

        try:
            import streamlit as st
            st.session_state["_INDEX_LOCAL_READY"] = bool(local_ready)
            st.session_state.setdefault("_INDEX_IS_LATEST", False)
        except Exception:
            pass
        self._idx("step_set", 1, "ok" if local_ready else "wait", "로컬 준비 기록")

        stored_meta = self._safe_load_meta(p)

        # --- 원격 최신 메타 ---
        self._idx("step_set", 2, "run", "원격 릴리스 조회")
        
        owner, repo, token = self._get_github_config()
        if not owner or not repo:
            self._idx("log", "GITHUB_REPO 미설정 → 원격 확인 불가", "warn")
            self._idx("step_set", 2, "wait", "원격 확인 불가")
            try:
                import streamlit as st
                st.session_state["_BOOT_RESTORE_DONE"] = True
                st.session_state.setdefault("_PERSIST_DIR", p.resolve())
            except Exception:
                pass
            return

        try:
            from src.infrastructure.runtime.gh_release import GHConfig, GHReleases
        except Exception:
            self._idx("log", "GH 릴리스 모듈 불가 → 최신 판정 보류", "warn")
            self._idx("step_set", 2, "wait", "원격 확인 불가")
            try:
                import streamlit as st
                st.session_state["_BOOT_RESTORE_DONE"] = True
                st.session_state.setdefault("_PERSIST_DIR", p.resolve())
            except Exception:
                pass
            return

        gh = GHReleases(GHConfig(owner=owner, repo=repo, token=token))

        remote_tag: Optional[str] = None
        remote_release_id: Optional[int] = None
        try:
            latest_rel = gh.get_latest_release()
            remote_tag = str(latest_rel.get("tag_name") or latest_rel.get("name") or "").strip() or None
            raw_id = latest_rel.get("id")
            try:
                remote_release_id = int(raw_id)
            except (TypeError, ValueError):
                remote_release_id = None
            self._idx("log", f"원격 최신 릴리스: tag={remote_tag or '-'} id={remote_release_id or '-'}")
        except Exception:
            remote_tag = None
            remote_release_id = None
            self._idx("log", "원격 최신 릴리스 조회 실패", "warn")
        finally:
            try:
                import streamlit as st
                st.session_state["_LATEST_RELEASE_TAG"] = remote_tag
                st.session_state["_LATEST_RELEASE_ID"] = remote_release_id
                if stored_meta is not None:
                    st.session_state["_LAST_RESTORE_META"] = getattr(stored_meta, "to_dict", lambda: {})()
            except Exception:
                pass

        # --- 일치/불일치 판정 (release_id 우선) ---
        stored_id = self._safe_meta_release_id(stored_meta)
        match_by_id = (remote_release_id is not None) and (stored_id is not None) and (stored_id == remote_release_id)
        match_by_tag = False
        if not match_by_id and remote_tag:
            match_by_tag = self._safe_meta_tag_matches(stored_meta, remote_tag)

        if local_ready and (match_by_id or (remote_release_id is None and match_by_tag)):
            self._idx("log", "메타 일치: 복원 생략 (이미 최신)")
            self._idx("step_set", 2, "ok", "메타 일치")
            try:
                import streamlit as st
                st.session_state["_BOOT_RESTORE_DONE"] = True
                st.session_state.setdefault("_PERSIST_DIR", p.resolve())
                st.session_state["_INDEX_IS_LATEST"] = True
                # 복원 시도 횟수 리셋 (메타 일치 시에도 무한 루프 방지)
                st.session_state["_RESTORE_ATTEMPTS"] = 0
                print(f"[DEBUG] Meta match, restore attempts reset to prevent infinite loop")
            except Exception as e:
                print(f"[DEBUG] Error in meta match handling: {e}")
                pass
            return

        # --- 최신 복원 강제 (순차번호 시스템) ---
        self._idx("step_set", 2, "run", "최신 인덱스 복원 중...")
        self._idx("log", "순차번호 기반 릴리스 복원 시작...")
        try:
            from src.infrastructure.runtime.sequential_release import create_sequential_manager
            
            # 순차번호 관리자 생성
            print(f"[DEBUG] Creating sequential manager for owner={owner}, repo={repo}")
            seq_manager = create_sequential_manager(owner, repo, token)
            print(f"[DEBUG] Sequential manager created successfully")
            
            # GitHub 릴리스 상태 확인
            try:
                print(f"[DEBUG] Checking GitHub releases for {owner}/{repo}")
                
                # 현재 실행 중인 코드 버전 확인
                print(f"[DEBUG] Code version check: Using GHReleases import")
                
                # 릴리스 목록 직접 확인
                from src.infrastructure.runtime.gh_release import GHReleases
                gh = GHReleases(owner=owner, repo=repo, token=token)
                releases = gh.list_releases()
                print(f"[DEBUG] Found {len(releases)} releases: {[r.get('tag_name') for r in releases]}")
                
                if releases:
                    latest_release = releases[0]
                    assets = latest_release.get('assets', [])
                    print(f"[DEBUG] Latest release assets: {[a.get('name') for a in assets]}")
                else:
                    print(f"[DEBUG] No releases found!")
                    
            except Exception as e:
                print(f"[DEBUG] Error checking releases: {e}")
            
            # 최신 인덱스 복원
            print(f"[DEBUG] About to call restore_latest_index with p={p}, clean_dest=True")
            
            try:
                result = seq_manager.restore_latest_index(p, clean_dest=True)
                print(f"[DEBUG] restore_latest_index result: {result}")
            except Exception as e:
                print(f"[DEBUG] restore_latest_index FAILED: {e}")
                import traceback
                traceback_str = traceback.format_exc()
                print(f"[DEBUG] Traceback: {traceback_str}")
                # 예외 발생 시에도 계속 진행
                result = None
            
            # 복원 후 파일 상태 재확인
            print(f"[DEBUG] Post-restore check: cj.exists()={cj.exists()}, rf.exists()={rf.exists()}")
            
            if cj.exists():
                print(f"[DEBUG] Post-restore cj.size(): {cj.stat().st_size}")
            
            # persist 디렉토리 전체 내용 확인
            try:
                persist_files = list(p.iterdir()) if p.exists() else []
                print(f"[DEBUG] Persist directory contents: {[f.name for f in persist_files]}")
            except Exception as e:
                print(f"[DEBUG] Error listing persist directory: {e}")

            # 복원 성공/실패에 따른 일관성 있는 상태 설정
            restore_success = cj.exists() and cj.stat().st_size > 0
            print(f"[DEBUG] Restore success: {restore_success}")
            
            # 세션 상태 업데이트 (일관성 보장) - 무한 루프 방지 강화
            try:
                import streamlit as st
                st.session_state["_INDEX_LOCAL_READY"] = restore_success
                st.session_state["_INDEX_IS_LATEST"] = restore_success
                st.session_state["_BOOT_RESTORE_DONE"] = True
                # 복원 시도 횟수 리셋 (성공 시)
                st.session_state["_RESTORE_ATTEMPTS"] = 0
                print(f"[DEBUG] Session state updated: _INDEX_LOCAL_READY={restore_success}")
                print(f"[DEBUG] Restore attempts reset to 0")
            except Exception as e:
                print(f"[DEBUG] Error updating session state: {e}")

            self._idx("step_set", 3, "run", "메타 저장/정리...")
            normalize_ready_file(p)
            
            saved_meta = self._safe_save_meta(
                p,
                tag=result.get("tag") if result else None,
                release_id=int(result.get("release_id")) if result and result.get("release_id") else None,
            )

            # 중복된 세션 상태 설정 제거 (이미 위에서 설정됨)
            try:
                import streamlit as st
                # 메타 정보만 추가로 저장
                if saved_meta is not None:
                    st.session_state["_LAST_RESTORE_META"] = getattr(saved_meta, "to_dict", lambda: {})()
            except Exception:
                pass

            self._idx("step_set", 2, "ok", "복원 완료")
            self._idx("step_set", 3, "ok", "메타 저장 완료")
            self._idx("step_set", 4, "ok", "마무리 정리")
            self._idx("log", "✅ 최신 인덱스 복원 완료")
        except Exception as e:
            self._idx("step_set", 2, "err", "복원 실패")
            self._idx("log", f"❌ 최신 인덱스 복원 실패: {e}", "err")
            try:
                import streamlit as st
                st.session_state["_BOOT_RESTORE_DONE"] = True
                st.session_state.setdefault("_PERSIST_DIR", p.resolve())
                st.session_state["_INDEX_IS_LATEST"] = False
                # 복원 시도 횟수 리셋 (실패 시에도 무한 루프 방지)
                st.session_state["_RESTORE_ATTEMPTS"] = 0
                print(f"[DEBUG] Restore failed, but attempts reset to prevent infinite loop")
                # UI에서 호출된 경우 오류 메시지 표시
                if st.session_state.get("_FORCE_RESTORE", False):
                    st.error(f"복원 실패: {e}")
                    st.session_state["_FORCE_RESTORE"] = False  # 플래그 리셋
            except Exception as e:
                print(f"[DEBUG] Error in failure handling: {e}")
                pass
            return


# 전역 인스턴스
restore_service = RestoreService()


# 편의 함수 (기존 app.py와의 호환성을 위해)
def _boot_auto_restore_index() -> None:
    """최신 릴리스 자동 복원 훅"""
    restore_service.boot_auto_restore_index()
