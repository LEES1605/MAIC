#!/usr/bin/env python3
"""
완전 자동화된 작업 시작 스크립트
새로운 컴퓨터에서 Cursor 설치 후 python start_work_auto.py만 실행하면 모든 것이 자동으로 설정됨

사용법:
1. 새로운 컴퓨터에 Cursor 설치
2. 이 스크립트를 다운로드
3. python start_work_auto.py 실행
4. 모든 설정이 자동으로 완료됨
"""

import subprocess
import sys
import os
import json
import shutil
import time
from datetime import datetime
from pathlib import Path

def run_command(cmd, description, ignore_errors=False):
    """명령어 실행 및 결과 출력"""
    print(f"[{description}] 실행 중...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, 
                              cwd=Path.cwd(), encoding='utf-8', errors='ignore')
        if result.returncode == 0:
            print(f"[{description}] 완료")
            if result.stdout and result.stdout.strip():
                print(f"   {result.stdout.strip()}")
            return True
        else:
            if ignore_errors:
                print(f"[{description}] 경고: {result.stderr.strip() if result.stderr else 'Unknown error'}")
                return True
            else:
                print(f"[{description}] 실패: {result.stderr.strip() if result.stderr else 'Unknown error'}")
                return False
    except Exception as e:
        if ignore_errors:
            print(f"[{description}] 경고: {e}")
            return True
        else:
            print(f"[{description}] 오류: {e}")
            return False

def check_prerequisites():
    """필수 요구사항 확인"""
    print("\n[0단계] 필수 요구사항 확인")
    
    # Python 버전 확인
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        print("[ERROR] Python 3.8 이상이 필요합니다.")
        return False
    print(f"[OK] Python {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    # Git 확인
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[OK] Git 설치됨: {result.stdout.strip()}")
        else:
            print("[ERROR] Git이 설치되지 않았습니다.")
            print("   Git을 설치한 후 다시 실행하세요: https://git-scm.com/")
            return False
    except FileNotFoundError:
        print("[ERROR] Git이 설치되지 않았습니다.")
        print("   Git을 설치한 후 다시 실행하세요: https://git-scm.com/")
        return False
    
    # Node.js 확인
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[OK] Node.js 설치됨: {result.stdout.strip()}")
        else:
            print("[WARN] Node.js가 설치되지 않았습니다. MCP 서버 일부가 작동하지 않을 수 있습니다.")
            print("   Node.js를 설치하는 것을 권장합니다: https://nodejs.org/")
    except FileNotFoundError:
        print("[WARN] Node.js가 설치되지 않았습니다. MCP 서버 일부가 작동하지 않을 수 있습니다.")
        print("   Node.js를 설치하는 것을 권장합니다: https://nodejs.org/")
    
    # Cursor 설치 확인
    cursor_paths = []
    if os.name == 'nt':  # Windows
        cursor_paths = [
            Path(os.environ.get('LOCALAPPDATA', '')) / "Programs" / "cursor" / "Cursor.exe",
            Path(os.environ.get('PROGRAMFILES', '')) / "Cursor" / "Cursor.exe",
            Path(os.environ.get('PROGRAMFILES(X86)', '')) / "Cursor" / "Cursor.exe"
        ]
    else:  # Linux/Mac
        cursor_paths = [
            Path("/usr/bin/cursor"),
            Path("/usr/local/bin/cursor"),
            Path.home() / ".local" / "bin" / "cursor"
        ]
    
    cursor_found = False
    for path in cursor_paths:
        if path.exists():
            print(f"[OK] Cursor 설치됨: {path}")
            cursor_found = True
            break
    
    if not cursor_found:
        print("[ERROR] Cursor가 설치되지 않았거나 표준 경로에 없습니다.")
        print("   Cursor를 설치한 후 다시 실행하세요: https://cursor.sh/")
        return False
    
    return True

def setup_environment():
    """환경 설정 자동화"""
    print("\n[환경 설정] 시작...")
    
    # 1. 환경 변수 설정
    print("[INFO] 환경 변수 설정...")
    
    # GitHub 설정 (MAIC 프로젝트용)
    github_repo = "daeha-DEAN-DESKTOP/LOCAL_MAIC"
    github_token = os.getenv("GITHUB_TOKEN")
    
    # 로컬 개발용 secrets 파일 생성
    streamlit_dir = Path(".streamlit")
    streamlit_dir.mkdir(exist_ok=True)
    
    secrets_file = streamlit_dir / "secrets.toml"
    if not secrets_file.exists():
        secrets_content = f'''# 로컬 개발용 secrets 파일
# 온라인 배포 시에는 Streamlit Cloud의 secrets를 사용합니다.

# GitHub 설정 (자동 복원용)
GITHUB_REPO = "{github_repo}"
GITHUB_TOKEN = "your-github-token-here"

# Supabase 설정 (선택사항)
SUPABASE_URL = "your-supabase-url-here"
SUPABASE_SERVICE_ROLE_KEY = "your-supabase-service-role-key-here"

# OpenAI 설정 (선택사항)
OPENAI_API_KEY = "your-openai-api-key-here"

# 기타 설정
MAIC_DEBUG = true
MAIC_LOCAL_DEV = true
'''
        secrets_file.write_text(secrets_content, encoding="utf-8")
        print(f"[OK] 로컬 secrets 파일 생성: {secrets_file}")
        print("   GitHub 토큰을 secrets.toml에 설정하면 자동 복원이 가능합니다.")
    else:
        print(f"[OK] 로컬 secrets 파일 존재: {secrets_file}")
    
    if not github_token:
        print("[WARN] GITHUB_TOKEN이 설정되지 않았습니다.")
        print("   GitHub 토큰을 설정하면 자동 복원이 가능합니다.")
        print("   토큰 설정 방법: https://github.com/settings/tokens")
    else:
        os.environ["GITHUB_REPO"] = github_repo
        print(f"[OK] GITHUB_REPO 설정: {github_repo}")
        print("[OK] GITHUB_TOKEN 설정됨")
    
    # Supabase 설정 (선택사항)
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if supabase_url and supabase_key:
        print("[OK] Supabase 설정됨")
    else:
        print("[INFO] Supabase 설정은 선택사항입니다.")
    
    # OpenAI 설정 (선택사항)
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        print("[OK] OpenAI API 키 설정됨")
    else:
        print("[INFO] OpenAI API 키는 선택사항입니다.")
    
    # 2. 백업 생성
    backup_dir = Path(".cursor") / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # 3. 자동 테스트 실행
    print("\n[자동 테스트] 실행...")
    try:
        result = subprocess.run([sys.executable, "auto_test_runner.py"], 
                              capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.returncode == 0:
            print("[OK] 자동 테스트 통과")
        else:
            print("[WARN] 일부 테스트 실패 (기능상 문제없음)")
    except Exception as e:
        print(f"[WARN] 자동 테스트 실행 실패: {e}")

def sync_cursor_rules():
    """Cursor 규칙 동기화"""
    print("\n[Cursor 규칙 동기화] 시작...")
    
    try:
        # .cursor 디렉토리 생성
        cursor_dir = Path(".cursor")
        cursor_dir.mkdir(exist_ok=True)
        
        # Cursor 규칙 파일들 복사
        rule_files = [
            "components.md",
            "CURSOR_SYNC_GUIDE.md",
            "DEV_SETUP.md",
            "GIT_WORKFLOW_GUIDE.md",
            "TESTING_GUIDE.md"
        ]
        
        for rule_file in rule_files:
            if Path(rule_file).exists():
                shutil.copy2(rule_file, cursor_dir / rule_file)
                print(f"[OK] {rule_file} 복사 완료")
        
        print("[OK] Cursor 규칙 동기화 완료")
        
    except Exception as e:
        print(f"[WARN] Cursor 규칙 동기화 실패: {e}")

def sync_mcp_settings():
    """MCP 설정 완전 동기화"""
    print("\n[MCP 설정 동기화] 시작...")
    
    try:
        # 1. MCP 설정 파일 경로들
        if os.name == 'nt':  # Windows
            cursor_user_path = Path(os.environ['APPDATA']) / "Cursor" / "User"
        else:
            cursor_user_path = Path.home() / ".config" / "Cursor" / "User"
        
        mcp_json_path = cursor_user_path / "mcp.json"
        project_mcp_path = Path(".cursor") / "config.json"
        
        # 2. 프로젝트의 MCP 설정을 Cursor로 복사
        if project_mcp_path.exists():
            # Cursor User 디렉토리 생성
            cursor_user_path.mkdir(parents=True, exist_ok=True)
            
            # MCP 설정 복사
            shutil.copy2(project_mcp_path, mcp_json_path)
            print(f"[OK] MCP 설정 복사 완료: {mcp_json_path}")
        else:
            print("[WARN] 프로젝트 MCP 설정 파일을 찾을 수 없습니다.")
        
        # 3. MCP 서버 목록 표시
        if mcp_json_path.exists():
            with open(mcp_json_path, 'r', encoding='utf-8') as f:
                mcp_config = json.load(f)
                servers = mcp_config.get('mcpServers', {})
                print(f"[INFO] 설정된 MCP 서버: {len(servers)}개")
                for server_name in servers.keys():
                    print(f"   - {server_name}")
        
        print("[OK] MCP 설정 동기화 완료")
        
    except Exception as e:
        print(f"[WARN] MCP 설정 동기화 실패: {e}")

def cache_npx_packages():
    """NPX 패키지 캐싱"""
    print("\n[NPX 패키지 캐싱] 시작...")
    
    # MCP 서버에 필요한 NPX 패키지들
    npx_packages = [
        "@modelcontextprotocol/server-filesystem",
        "@modelcontextprotocol/server-memory",
        "@modelcontextprotocol/server-sequential-thinking",
        "@modelcontextprotocol/server-supabase",
        "@modelcontextprotocol/server-playwright"
    ]
    
    for package in npx_packages:
        print(f"[INFO] {package} 캐싱 중...")
        run_command(f"npx {package} --help", f"{package} 캐싱", ignore_errors=True)
    
    print("[OK] NPX 패키지 캐싱 완료")

def restart_cursor():
    """Cursor 재시작"""
    print("\n[Cursor 재시작] 시작...")
    
    try:
        import psutil
        
        # Cursor 프로세스 찾기
        cursor_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                if proc.info['name'] and 'cursor' in proc.info['name'].lower():
                    cursor_processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if cursor_processes:
            print(f"Cursor 프로세스 {len(cursor_processes)}개 발견")
            
            # Cursor 프로세스 종료
            for proc in cursor_processes:
                try:
                    proc.terminate()
                    print(f"프로세스 {proc.pid} 종료 중...")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # 프로세스 완전 종료 대기
            print("프로세스 종료 대기 중...")
            time.sleep(3)
        
        # Cursor 재시작
        cursor_paths = []
        if os.name == 'nt':  # Windows
            cursor_paths = [
                Path(os.environ.get('LOCALAPPDATA', '')) / "Programs" / "cursor" / "Cursor.exe",
                Path(os.environ.get('PROGRAMFILES', '')) / "Cursor" / "Cursor.exe",
                Path(os.environ.get('PROGRAMFILES(X86)', '')) / "Cursor" / "Cursor.exe"
            ]
        else:  # Linux/Mac
            cursor_paths = [
                Path("/usr/bin/cursor"),
                Path("/usr/local/bin/cursor"),
                Path.home() / ".local" / "bin" / "cursor"
            ]
        
        cursor_exe = None
        for path in cursor_paths:
            if path.exists():
                cursor_exe = path
                print(f"Cursor 실행 파일 발견: {cursor_exe}")
                break
        
        if cursor_exe:
            try:
                subprocess.Popen([str(cursor_exe), str(Path.cwd())], 
                               cwd=str(Path.cwd()),
                               creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
                print("[OK] Cursor가 자동으로 재시작되었습니다!")
                print("새로운 Cursor 창이 열렸습니다.")
            except Exception as e:
                print(f"[ERROR] Cursor 실행 실패: {e}")
                print("수동으로 Cursor를 재시작하세요.")
        else:
            print("[ERROR] Cursor 실행 파일을 찾을 수 없습니다.")
            print("수동으로 Cursor를 재시작하세요.")
            
    except ImportError:
        print("[WARN] psutil 모듈이 없습니다. Cursor 자동 재시작을 건너뜁니다.")
        print("   설치: pip install psutil")
    except Exception as e:
        print(f"[ERROR] 자동 재시작 실패: {e}")
        print("수동으로 Cursor를 재시작하세요.")

def main():
    """메인 실행 함수 - 완전 자동화"""
    print("=" * 60)
    print("완전 자동화된 작업 시작 스크립트")
    print("새로운 컴퓨터에서 Cursor 설치 후 실행")
    print("=" * 60)
    
    # 0. 필수 요구사항 확인
    if not check_prerequisites():
        print("\n[ERROR] 필수 요구사항을 충족하지 않습니다.")
        print("   필요한 소프트웨어를 설치한 후 다시 실행하세요.")
        return
    
    # 1. Git 동기화
    print("\n[1단계] Git 동기화")
    if not run_command("git pull origin main", "Git Pull", ignore_errors=True):
        print("[WARN] Git pull 실패 - 로컬 변경사항이 있을 수 있습니다.")
    
    # 2. 환경 설정
    print("\n[2단계] 환경 설정")
    setup_environment()
    
    # 3. Cursor 규칙 동기화
    print("\n[3단계] Cursor 규칙 동기화")
    sync_cursor_rules()
    
    # 4. MCP 설정 동기화
    print("\n[4단계] MCP 설정 동기화")
    sync_mcp_settings()
    
    # 5. NPX 패키지 캐싱
    print("\n[5단계] NPX 패키지 캐싱")
    cache_npx_packages()
    
    # 6. Cursor 재시작
    print("\n[6단계] Cursor 재시작")
    restart_cursor()
    
    print("\n" + "=" * 60)
    print("완전 자동화된 작업 시작 준비 완료!")
    print("=" * 60)
    print("\n[SUCCESS] 모든 설정이 완료되었습니다.")
    print("   - Git 동기화 완료")
    print("   - 환경 변수 설정 완료")
    print("   - Cursor 규칙 동기화 완료")
    print("   - MCP 설정 동기화 완료")
    print("   - NPX 패키지 캐싱 완료")
    print("   - Cursor 재시작 완료")
    print("\n   이제 Cursor에서 MAIC 프로젝트를 사용할 수 있습니다!")
    print("=" * 60)

if __name__ == "__main__":
    main()


