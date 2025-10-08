"""
작업 맥락 관리자 시스템
AI가 이전 작업을 완전히 이해할 수 있도록 맥락을 관리하는 시스템
"""

import json
import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

class WorkContextManager:
    """작업 맥락을 관리하고 AI에게 전달하는 시스템"""
    
    def __init__(self):
        self.context_file = Path("work_context.json")
        self.history_file = Path("docs/DEVELOPMENT_HISTORY.md")
        self.session_log = Path("WORK_SESSION_LOG.md")
        
    def save_work_context(self, current_phase: str, achievements: List[str], 
                         next_tasks: List[str], key_files: List[str]) -> None:
        """현재 작업 맥락을 저장"""
        context = {
            "timestamp": datetime.datetime.now().isoformat(),
            "current_phase": current_phase,
            "achievements": achievements,
            "next_tasks": next_tasks,
            "key_files_modified": key_files,
            "session_info": {
                "last_commit": self._get_last_commit(),
                "active_branch": self._get_active_branch(),
                "mcp_status": self._get_mcp_status(),
                "environment": self._get_environment_info()
            }
        }
        
        with open(self.context_file, 'w', encoding='utf-8') as f:
            json.dump(context, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 작업 맥락 저장 완료: {current_phase}")
    
    def load_work_context(self) -> Optional[Dict[str, Any]]:
        """저장된 작업 맥락을 로드"""
        if not self.context_file.exists():
            return None
        
        try:
            with open(self.context_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ 작업 맥락 로드 실패: {e}")
            return None
    
    def generate_ai_context_summary(self) -> str:
        """AI에게 전달할 완전한 맥락 요약 생성"""
        context = self.load_work_context()
        if not context:
            return self._generate_default_context()
        
        # 개발 히스토리에서 최근 섹션 추출
        recent_history = self._extract_recent_history()
        
        # 세션 로그에서 최근 작업 추출
        recent_sessions = self._extract_recent_sessions()
        
        ai_context = f"""
🔄 MAIC 프로젝트 작업 연속성 복원 완료

📋 현재 작업 단계: {context.get('current_phase', '알 수 없음')}

🎯 최근 성과:
{self._format_list(context.get('achievements', []))}

📝 다음 작업 계획:
{self._format_list(context.get('next_tasks', []))}

📁 최근 수정된 주요 파일:
{self._format_list(context.get('key_files_modified', []))}

🔧 환경 상태:
- Git 브랜치: {context.get('session_info', {}).get('active_branch', '알 수 없음')}
- 마지막 커밋: {context.get('session_info', {}).get('last_commit', '알 수 없음')}
- MCP 상태: {context.get('session_info', {}).get('mcp_status', '알 수 없음')}

📚 최근 개발 히스토리:
{recent_history}

📊 최근 작업 세션:
{recent_sessions}

💡 AI 어시스턴트를 위한 중요 정보:
- 이전 작업에서 AI 친화적 최적화 시스템을 구축했습니다
- 포트 번호 불일치 문제를 근본적으로 해결했습니다
- 강제적 검증 시스템이 구현되어 있습니다
- 모든 새 코드는 src/ 디렉토리에만 생성해야 합니다
- 포트 8501만 사용해야 합니다 (--server.port 옵션 금지)

⚠️ 주의사항:
- 규칙 위반 시 실행이 차단됩니다
- 모든 작업은 docs/AI_RULES.md 규칙을 준수해야 합니다
- 기존 중복 코드 삭제 시 사용자 승인이 필요합니다
        """
        
        return ai_context
    
    def _format_list(self, items: List[str]) -> str:
        """리스트를 포맷된 문자열로 변환"""
        if not items:
            return "  - 없음"
        return "\n".join([f"  - {item}" for item in items])
    
    def _generate_default_context(self) -> str:
        """기본 컨텍스트 생성 (저장된 맥락이 없을 때)"""
        return """
🔄 MAIC 프로젝트 작업 시작

📋 기본 정보:
- AI 친화적 최적화 시스템이 구축되어 있습니다
- 강제적 검증 시스템이 활성화되어 있습니다
- 모든 새 코드는 src/ 디렉토리에만 생성해야 합니다

💡 AI 어시스턴트를 위한 중요 규칙:
- docs/AI_RULES.md 파일을 먼저 읽어보세요
- 포트 8501만 사용하세요 (--server.port 옵션 금지)
- 규칙 위반 시 실행이 차단됩니다

📚 문서 참조:
- docs/DEVELOPMENT_HISTORY.md: 개발 과정 기록
- docs/AI_RULES.md: AI 규칙
- docs/PROJECT_STRUCTURE.md: 프로젝트 구조
        """
    
    def _extract_recent_history(self) -> str:
        """개발 히스토리에서 최근 섹션 추출"""
        if not self.history_file.exists():
            return "개발 히스토리 파일이 없습니다."
        
        try:
            content = self.history_file.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            # 마지막 3개 섹션 추출
            recent_sections = []
            current_section = []
            section_count = 0
            
            for line in lines:
                if line.startswith('## ') and section_count < 3:
                    if current_section:
                        recent_sections.append('\n'.join(current_section))
                        current_section = []
                    section_count += 1
                
                if section_count > 0 and section_count <= 3:
                    current_section.append(line)
            
            if current_section:
                recent_sections.append('\n'.join(current_section))
            
            return '\n'.join(recent_sections[-2:]) if recent_sections else "최근 히스토리가 없습니다."
            
        except Exception as e:
            return f"히스토리 추출 실패: {e}"
    
    def _extract_recent_sessions(self) -> str:
        """세션 로그에서 최근 작업 추출"""
        if not self.session_log.exists():
            return "세션 로그가 없습니다."
        
        try:
            content = self.session_log.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            # 마지막 10줄 추출
            recent_lines = lines[-10:] if len(lines) > 10 else lines
            return '\n'.join([line.strip() for line in recent_lines if line.strip()])
            
        except Exception as e:
            return f"세션 로그 추출 실패: {e}"
    
    def _get_last_commit(self) -> str:
        """마지막 커밋 정보 가져오기"""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "log", "-1", "--oneline"],
                capture_output=True, text=True, encoding='utf-8'
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return "알 수 없음"
    
    def _get_active_branch(self) -> str:
        """현재 활성 브랜치 가져오기"""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True, text=True, encoding='utf-8'
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return "알 수 없음"
    
    def _get_mcp_status(self) -> str:
        """MCP 상태 가져오기"""
        mcp_file = Path(".cursor/mcp.json")
        if mcp_file.exists():
            try:
                with open(mcp_file, 'r', encoding='utf-8') as f:
                    mcp_config = json.load(f)
                    servers = mcp_config.get('mcpServers', {})
                    return f"{len(servers)}개 서버 활성화"
            except Exception:
                pass
        return "MCP 설정 없음"
    
    def _get_environment_info(self) -> str:
        """환경 정보 가져오기"""
        import sys
        import os
        return f"Python {sys.version_info.major}.{sys.version_info.minor}, OS: {os.name}"

def save_current_work_context():
    """현재 작업 맥락을 저장하는 편의 함수"""
    manager = WorkContextManager()
    manager.save_work_context(
        current_phase="AI 친화적 최적화 시스템 구축 완료",
        achievements=[
            "포트 번호 불일치 문제 근본적 해결",
            "강제적 검증 시스템 구축",
            "AI 행동 패턴 강제 변경 시스템 구현",
            "자동 검증 시스템 통합 완료"
        ],
        next_tasks=[
            "GitHub 업로드 완료",
            "작업 연속성 시스템 100% 완성",
            "전체 시스템 검증 및 테스트"
        ],
        key_files_modified=[
            "docs/AI_RULES.md",
            "tools/mandatory_validator.py",
            "tools/ai_behavior_enforcer.py",
            "tools/universal_validator.py"
        ]
    )

def get_ai_context_for_start():
    """작업 시작 시 AI에게 전달할 맥락 가져오기"""
    manager = WorkContextManager()
    return manager.generate_ai_context_summary()

if __name__ == "__main__":
    # 테스트
    manager = WorkContextManager()
    
    # 현재 맥락 저장
    save_current_work_context()
    
    # AI 맥락 생성
    context = get_ai_context_for_start()
    print(context)
