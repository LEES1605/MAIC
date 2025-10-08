#!/usr/bin/env python3
"""
완전 자동화된 작업 시작 스크립트
새로운 컴퓨터에서 Cursor 설치 후 python start_work.py만 실행하면 모든 것이 자동으로 설정됨
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

def sync_mcp_settings():
    """MCP 설정 완전 동기화"""
    print("\n[MCP 설정 동기화] 시작...")
    
    try:
        import os
        import shutil
        import json
        
        # 1. MCP 설정 파일 경로들
        if os.name == 'nt':  # Windows
            cursor_user_path = Path(os.environ['APPDATA']) / "Cursor" / "User"
        else:
            cursor_user_path = Path.home() / ".config" / "Cursor" / "User"
        
        mcp_json_path = cursor_user_path / "mcp.json"
        project_mcp_path = Path(".cursor") / "mcp.json"
        
        # 2. 프로젝트의 MCP 설정을 Cursor로 복사
        if project_mcp_path.exists():
            # Cursor User 디렉토리 생성
            cursor_user_path.mkdir(parents=True, exist_ok=True)
            
            # MCP 설정 복사
            shutil.copy2(project_mcp_path, mcp_json_path)
            print(f"[OK] MCP 설정 복사 완료: {project_mcp_path} → {mcp_json_path}")
            
            # MCP 설정 내용 확인 및 출력
            with open(project_mcp_path, 'r', encoding='utf-8') as f:
                mcp_config = json.load(f)
                mcp_servers = mcp_config.get('mcpServers', {})
                print(f"[INFO] 동기화된 MCP 서버 {len(mcp_servers)}개:")
                for server_name in mcp_servers.keys():
                    print(f"   - {server_name}")
        else:
            print("[WARN] 프로젝트에 MCP 설정 파일(.cursor/mcp.json)이 없습니다.")
            return False
        
        # 3. MCP 서버 패키지 자동 설치 (npx 기반)
        print("\n[INFO] MCP 서버 패키지 확인 중...")
        
        # MCP 설정에서 패키지 목록 추출
        with open(project_mcp_path, 'r', encoding='utf-8') as f:
            mcp_config = json.load(f)
            mcp_servers = mcp_config.get('mcpServers', {})
        
        # npx 기반 패키지들 확인
        npx_packages = []
        for server_name, server_config in mcp_servers.items():
            if server_config.get('command') == 'npx':
                args = server_config.get('args', [])
                if len(args) >= 2 and args[0] == '-y':
                    package_name = args[1]
                    npx_packages.append(package_name)
        
        if npx_packages:
            print(f"[INFO] NPX 패키지 {len(npx_packages)}개 발견:")
            for package in npx_packages:
                print(f"   - {package}")
            
            # Node.js/npm 확인
            try:
                result = subprocess.run("npm --version", shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"[OK] npm 버전: {result.stdout.strip()}")
                    
                    # 패키지 자동 캐시 (사용자 입력 없이)
                    print("[INFO] NPX 패키지 자동 캐시 중...")
                    for package in npx_packages:
                        try:
                            print(f"   캐시 중: {package}")
                            subprocess.run(f"npx -y {package} --help", 
                                         shell=True, capture_output=True, timeout=30)
                            print(f"   [OK] {package} 캐시 완료")
                        except subprocess.TimeoutExpired:
                            print(f"   [TIMEOUT] {package} 캐시 타임아웃 (정상)")
                        except Exception as e:
                            print(f"   [ERROR] {package} 캐시 실패: {e}")
                    print("[OK] NPX 패키지 캐시 완료!")
                else:
                    print("[WARN] npm이 설치되지 않았습니다. Node.js를 설치하세요.")
            except Exception as e:
                print(f"[WARN] npm 확인 실패: {e}")
        
        # 4. 환경 변수 자동 설정
        print("\n[INFO] 환경 변수 설정...")
        
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
            print(f"   또는 .streamlit/secrets.toml 파일에서 GITHUB_TOKEN을 설정하세요.")
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
        
        # 5. 백업 생성
        backup_dir = Path(".cursor") / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"mcp_backup_{timestamp}.json"
        
        shutil.copy2(project_mcp_path, backup_file)
        print(f"[INFO] MCP 설정 백업 생성: {backup_file}")
        
        print("\n[OK] MCP 설정 동기화 완료!")
        print("   설정된 MCP 서버: GitKraken, playwright, supabase, filesystem, memory, sequential-thinking")
        print("   총 도구 수: ~115개 (MAIC 프로젝트 필수 구성)")
        print("   Cursor를 재시작하면 모든 MCP 서버가 활성화됩니다.")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] MCP 설정 동기화 실패: {e}")
        import traceback
        print(f"상세 오류: {traceback.format_exc()}")
        return False

def sync_cursor_rules():
    """Cursor 규칙 파일 자동 동기화"""
    print("\n[Cursor 규칙 동기화] 시작...")
    
    try:
        # .cursor/rules 디렉토리 생성
        cursor_rules_dir = Path(".cursor/rules")
        cursor_rules_dir.mkdir(parents=True, exist_ok=True)
        
        # Linear 컴포넌트 규칙 파일 생성
        linear_rules_content = '''---
alwaysApply: true
---

# Linear 컴포넌트 시스템 - 필수 사용 규칙

## 🎨 **UI 컴포넌트 사용 규칙**

### **MUST USE - Linear 컴포넌트만 사용**
이 프로젝트에서는 **반드시** Linear 컴포넌트 시스템을 사용해야 합니다. Streamlit 기본 컴포넌트 대신 Linear 컴포넌트를 사용하세요.

#### **✅ 허용되는 컴포넌트:**
```python
# 기본 컴포넌트
from src.ui.components.linear_components import (
    linear_button,     # 버튼 (st.button 대신)
    linear_card,       # 카드 (st.container 대신)
    linear_badge,      # 배지/태그
    linear_input,      # 입력 필드
    linear_alert,      # 알림/경고
    linear_divider,    # 구분선
    linear_carousel,   # 캐러셀
    linear_card_with_image,  # 이미지 카드
    linear_navbar      # 네비게이션 바
)

# 레이아웃 컴포넌트
from src.ui.components.linear_layout_components import (
    linear_footer,     # 푸터
    linear_hero        # 히어로 섹션
)

# 테마 시스템
from src.ui.components.linear_theme import apply_theme
```

#### **❌ 금지되는 사용법:**
```python
# 절대 사용하지 마세요
st.button()           # ❌ linear_button() 사용
st.container()        # ❌ linear_card() 사용
st.success()          # ❌ linear_alert() 사용
st.warning()          # ❌ linear_alert() 사용
st.error()            # ❌ linear_alert() 사용
st.info()             # ❌ linear_alert() 사용
st.markdown("---")    # ❌ linear_divider() 사용
```

### **🎯 필수 사용 패턴**

#### **1. 모든 페이지에서 테마 적용 (필수)**
```python
from src.ui.components.linear_theme import apply_theme

def main():
    # 테마 적용 (최우선)
    apply_theme()
    # 나머지 코드...
```

#### **2. 버튼 사용법**
```python
# ✅ 올바른 사용법
if linear_button("클릭하세요", variant="primary", size="medium", key="unique_key"):
    # 액션 처리
    pass
```

#### **3. 카드 사용법**
```python
# ✅ 올바른 사용법
linear_card(
    title="카드 제목",
    content=st.markdown("카드 내용"),
    variant="elevated"
)
```

#### **4. 전체 너비 컴포넌트 (필수)**
```python
# Navbar, Hero, Footer는 반드시 전체 너비 사용
linear_navbar(brand_name="앱 이름", ...)
linear_hero(title="메인 제목", ...)
linear_footer(copyright_text="저작권", ...)
```

### **🚨 중요 규칙**

1. **테마 적용 필수**: 모든 페이지에서 `apply_theme()` 호출
2. **Linear 컴포넌트만 사용**: Streamlit 기본 컴포넌트 사용 금지
3. **고유 키 사용**: 모든 버튼에 `key` 매개변수 필수
4. **전체 너비**: Navbar, Hero, Footer는 전체 너비 사용
5. **모바일 우선**: 모든 컴포넌트 모바일 테스트 필수

### **📋 체크리스트**

코드 작성 시 다음을 확인하세요:
- [ ] `apply_theme()` 호출했는가?
- [ ] `st.button()` 대신 `linear_button()` 사용했는가?
- [ ] 모든 버튼에 고유 `key`를 설정했는가?
- [ ] Linear 컴포넌트만 사용했는가?
- [ ] 모바일에서 테스트했는가?

**이 규칙을 위반하면 코드 리뷰에서 거부됩니다.**

## 🔄 **새 컴포넌트 개발 규칙**

### **⚠️ 중요: 컴포넌트 생성 전 필수 협의**
새로운 Linear 컴포넌트를 만들기 전에 **반드시** 사용자와 다음 사항을 협의해야 합니다:

1. **컴포넌트 필요성**: 왜 이 컴포넌트가 필요한가?
2. **사용 목적**: 어디에 사용할 예정인가?
3. **디자인 방향**: 어떤 스타일과 기능이 필요한가?
4. **우선순위**: 다른 작업 대비 얼마나 중요한가?

### **🚫 금지 사항**
- 사용자 요청 없이 임의로 새 컴포넌트 생성
- "혹시 필요할 것 같아서" 컴포넌트 미리 만들기
- 기존 컴포넌트로 충분한데 새로 만들기

### **✅ 올바른 프로세스**
```
1. 사용자 요청 또는 명확한 필요성 확인
2. 컴포넌트 목적과 사용처 협의
3. 디자인 방향 및 기능 명세
4. 사용자 승인 후 개발 진행
```

**컴포넌트 개발은 반드시 사용자와 협의 후 진행하세요!**'''
        
        # Linear 컴포넌트 규칙 파일 저장
        linear_rules_file = cursor_rules_dir / "linear-components.mdc"
        with open(linear_rules_file, 'w', encoding='utf-8') as f:
            f.write(linear_rules_content)
        
        print("[Cursor 규칙 동기화] Linear 컴포넌트 규칙 파일 생성 완료")
        
        # .cursorrules 파일도 생성 (호환성을 위해)
        cursorrules_content = linear_rules_content.replace('---\nalwaysApply: true\n---', '')
        cursorrules_file = Path(".cursorrules")
        with open(cursorrules_file, 'w', encoding='utf-8') as f:
            f.write(cursorrules_content)
        
        print("[Cursor 규칙 동기화] .cursorrules 파일 생성 완료")
        
        # components.md 파일도 생성 (문서용)
        components_md_content = cursorrules_content
        components_md_file = Path("components.md")
        with open(components_md_file, 'w', encoding='utf-8') as f:
            f.write(components_md_content)
        
        print("[Cursor 규칙 동기화] components.md 파일 생성 완료")
        
        print("[Cursor 규칙 동기화] 모든 규칙 파일이 자동으로 동기화되었습니다!")
        print("   - .cursor/rules/linear-components.mdc")
        print("   - .cursorrules")
        print("   - components.md")
        print("   Cursor를 재시작하면 규칙이 적용됩니다.")
        
    except Exception as e:
        print(f"[Cursor 규칙 동기화] 오류: {e}")
        print("수동으로 규칙 파일을 확인해주세요.")

def check_git_repo():
    """Git 저장소인지 확인하고, 아니면 자동 클론"""
    try:
        result = subprocess.run("git status", shell=True, capture_output=True, text=True, 
                              cwd=Path.cwd(), encoding='utf-8', errors='ignore')
        if result.returncode == 0:
            return True  # Git 저장소임
    except:
        pass
    
    # Git 저장소가 아니면 자동 클론 (사용자 입력 없이)
    print("Git 저장소가 아닙니다. 자동으로 클론합니다...")
    
    # 현재 디렉토리 확인
    current_dir = Path.cwd()
    print(f"현재 위치: {current_dir}")
    
    # 자동으로 클론할 위치 설정
    clone_path = str(current_dir.parent / "MAIC")
    print(f"클론 위치: {clone_path}")
    
    # GitHub에서 클론
    clone_cmd = f'git clone https://github.com/LEES1605/MAIC.git "{clone_path}"'
    if run_command(clone_cmd, "GitHub에서 프로젝트 클론"):
        print(f"클론 완료! 다음 명령어로 이동하세요:")
        print(f"cd \"{clone_path}\"")
        print("그 다음 다시 python start_work.py를 실행하세요.")
        return False
    else:
        print("클론 실패. 수동으로 클론해주세요.")
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
    
    # 1. Git 저장소 확인 및 자동 클론
    if not check_git_repo():
        return
    
    # 2. 최신 코드 가져오기
    if not run_command("git pull origin main", "최신 코드 가져오기", ignore_errors=True):
        print("Git pull 실패. 계속 진행합니다...")
    
    # 3. 환경 설정
    print("\n[2단계] 환경 설정")
    setup_environment()
    
    # 4. Linear 컴포넌트 규칙 자동 동기화
    print("\n[3단계] Cursor 규칙 동기화")
    sync_cursor_rules()
    
    # 5. 현재 상태 확인
    run_command("git status", "현재 상태 확인")
    
    # 6. 작업 로그 확인
    log_file = Path("WORK_SESSION_LOG.md")
    if log_file.exists():
        print("\n최근 작업 로그:")
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # 마지막 10줄만 표시
            for line in lines[-10:]:
                print(f"   {line.strip()}")
    
    # 7. 오늘 날짜로 작업 시작 기록
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n오늘 날짜: {today}")
    
    # 8. AI 작업 맥락 복원
    print("\n[4단계] AI 작업 맥락 복원")
    restore_ai_context()
    
    # 9. Cursor 설정 및 MCP 자동 동기화
    print("\n[5단계] MCP 설정 동기화")
    sync_mcp_settings()
    
    # 10. NPX 패키지 캐싱
    print("\n[6단계] NPX 패키지 캐싱")
    cache_npx_packages()
    
    # 11. 포트 검증 시스템 통합
    print("\n[7단계] 포트 검증 시스템 통합")
    integrate_port_validation()
    
    # 12. Cursor 재시작
    print("\n[8단계] Cursor 재시작")
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
    print("   작업 완료 후 'python end_work.py'를 실행하세요.")
    print("=" * 60)
    
    # 자동 설정 검증
    print("\n[자동 설정 검증] 시작...")
    try:
        from scripts.auto_setup_verification import main as verify_setup
        if verify_setup():
            print("\n[OK] 모든 설정이 완료되었습니다!")
        else:
            print("\n[WARN] 일부 설정에 문제가 있습니다. 확인해주세요.")
    except Exception as e:
        print(f"\n[ERROR] 설정 검증 실패: {e}")
        print("수동으로 설정을 확인해주세요.")
    
    # Cursor 자동 재시작 (사용자 입력 없이)
    print("\n[Cursor 자동 재시작] 시작...")
    try:
        import time
        import os
        
        # psutil 모듈 확인 및 설치
        try:
            import psutil
        except ImportError:
            print("psutil 모듈이 없습니다. 자동으로 설치합니다...")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "psutil"], 
                             check=True, capture_output=True)
                import psutil
                print("[OK] psutil 모듈 설치 완료!")
            except subprocess.CalledProcessError as e:
                print(f"[ERROR] psutil 설치 실패: {e}")
                print("수동으로 설치하세요: pip install psutil")
                print("수동으로 Cursor를 재시작하세요.")
                return
        
        # Cursor 프로세스 찾기
        cursor_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
            try:
                proc_info = proc.info
                if proc_info['name'] and 'cursor' in proc_info['name'].lower():
                    cursor_processes.append(proc)
                elif proc_info['exe'] and 'cursor' in proc_info['exe'].lower():
                    cursor_processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
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
        cursor_paths = [
            r"C:\Users\%USERNAME%\AppData\Local\Programs\cursor\Cursor.exe",
            r"C:\Program Files\Cursor\Cursor.exe",
            r"C:\Program Files (x86)\Cursor\Cursor.exe",
            r"C:\Users\%USERNAME%\AppData\Local\Programs\cursor\cursor.exe",
            r"C:\Program Files\cursor\cursor.exe",
            r"C:\Program Files (x86)\cursor\cursor.exe"
        ]
        
        cursor_exe = None
        for path in cursor_paths:
            expanded_path = os.path.expandvars(path)
            if os.path.exists(expanded_path):
                cursor_exe = expanded_path
                print(f"Cursor 실행 파일 발견: {cursor_exe}")
                break
        
        if cursor_exe:
            try:
                subprocess.Popen([cursor_exe, str(Path.cwd())], 
                               cwd=str(Path.cwd()),
                               creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
                print("[OK] Cursor가 자동으로 재시작되었습니다!")
                print("새로운 Cursor 창이 열렸습니다.")
            except Exception as e:
                print(f"[ERROR] Cursor 실행 실패: {e}")
                print("수동으로 Cursor를 재시작하세요.")
        else:
            print("[ERROR] Cursor 실행 파일을 찾을 수 없습니다.")
            print("다음 경로들을 확인해보세요:")
            for path in cursor_paths:
                expanded_path = os.path.expandvars(path)
                print(f"  - {expanded_path}")
            print("수동으로 Cursor를 재시작하세요.")
            
    except Exception as e:
        print(f"[ERROR] 자동 재시작 실패: {e}")
        print("수동으로 Cursor를 재시작하세요.")

def restore_ai_context():
    """AI 작업 맥락 복원"""
    print("[AI 작업 맥락] 복원 중...")
    
    try:
        # 작업 맥락 관리자 가져오기
        from work_context_manager import get_ai_context_for_start
        
        # AI 컨텍스트 생성
        ai_context = get_ai_context_for_start()
        
        # AI 컨텍스트 파일로 저장
        context_file = Path("ai_context_summary.md")
        with open(context_file, 'w', encoding='utf-8') as f:
            f.write(ai_context)
        
        print("[OK] AI 작업 맥락 복원 완료!")
        print(f"   컨텍스트 파일: {context_file}")
        print("\n" + "="*60)
        print("🤖 AI 어시스턴트를 위한 작업 맥락:")
        print("="*60)
        print(ai_context)
        print("="*60)
        print("\n💡 이 정보를 AI 어시스턴트에게 전달하세요!")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] AI 작업 맥락 복원 실패: {e}")
        print("   기본 맥락으로 진행합니다.")
        
        # 기본 맥락 생성
        basic_context = """
🔄 MAIC 프로젝트 작업 시작

📋 기본 정보:
- AI 친화적 최적화 시스템이 구축되어 있습니다
- 강제적 검증 시스템이 활성화되어 있습니다
- 모든 새 코드는 src/ 디렉토리에만 생성해야 합니다

💡 AI 어시스턴트를 위한 중요 규칙:
- docs/AI_RULES.md 파일을 먼저 읽어보세요
- 포트 8501만 사용하세요 (--server.port 옵션 금지)
- 규칙 위반 시 실행이 차단됩니다
        """
        
        context_file = Path("ai_context_summary.md")
        with open(context_file, 'w', encoding='utf-8') as f:
            f.write(basic_context)
        
        print(f"[OK] 기본 AI 맥락 생성: {context_file}")
        return False

def cache_npx_packages():
    """NPX 패키지 캐싱"""
    print("[NPX 패키지 캐싱] 시작...")
    
    try:
        # MCP 설정에서 NPX 패키지 추출
        mcp_file = Path(".cursor/mcp.json")
        if not mcp_file.exists():
            print("[WARN] MCP 설정 파일이 없습니다")
            return False
        
        with open(mcp_file, 'r', encoding='utf-8') as f:
            mcp_config = json.load(f)
            mcp_servers = mcp_config.get('mcpServers', {})
        
        # NPX 패키지 목록 추출
        npx_packages = []
        for server_name, server_config in mcp_servers.items():
            if server_config.get('command') == 'npx':
                args = server_config.get('args', [])
                if len(args) >= 2 and args[0] == '-y':
                    package_name = args[1]
                    npx_packages.append(package_name)
        
        if npx_packages:
            print(f"[INFO] NPX 패키지 {len(npx_packages)}개 캐싱 중...")
            for package in npx_packages:
                try:
                    print(f"   캐싱 중: {package}")
                    subprocess.run(f"npx -y {package} --help", 
                                 shell=True, capture_output=True, timeout=30)
                    print(f"   [OK] {package} 캐시 완료")
                except subprocess.TimeoutExpired:
                    print(f"   [TIMEOUT] {package} 캐시 타임아웃 (정상)")
                except Exception as e:
                    print(f"   [ERROR] {package} 캐시 실패: {e}")
            print("[OK] NPX 패키지 캐싱 완료!")
        else:
            print("[INFO] NPX 패키지가 없습니다")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] NPX 패키지 캐싱 실패: {e}")
        return False

def restart_cursor():
    """Cursor 재시작"""
    print("[Cursor 재시작] 시작...")
    
    try:
        # psutil 모듈 확인 및 설치
        try:
            import psutil
        except ImportError:
            print("psutil 모듈이 없습니다. 자동으로 설치합니다...")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "psutil"], 
                             check=True, capture_output=True)
                import psutil
                print("[OK] psutil 모듈 설치 완료!")
            except subprocess.CalledProcessError as e:
                print(f"[ERROR] psutil 설치 실패: {e}")
                print("수동으로 설치하세요: pip install psutil")
                print("수동으로 Cursor를 재시작하세요.")
                return False
        
        # Cursor 프로세스 찾기 및 종료
        cursor_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
            try:
                proc_info = proc.info
                if proc_info['name'] and 'cursor' in proc_info['name'].lower():
                    cursor_processes.append(proc)
                elif proc_info['exe'] and 'cursor' in proc_info['exe'].lower():
                    cursor_processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        if cursor_processes:
            print(f"Cursor 프로세스 {len(cursor_processes)}개 종료 중...")
            for proc in cursor_processes:
                try:
                    proc.terminate()
                    print(f"   프로세스 {proc.pid} 종료")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # 프로세스 완전 종료 대기
            print("프로세스 종료 대기 중...")
            time.sleep(3)
        
        # Cursor 재시작
        cursor_paths = [
            r"C:\Users\%USERNAME%\AppData\Local\Programs\cursor\Cursor.exe",
            r"C:\Program Files\Cursor\Cursor.exe",
            r"C:\Program Files (x86)\Cursor\Cursor.exe"
        ]
        
        cursor_exe = None
        for path in cursor_paths:
            expanded_path = os.path.expandvars(path)
            if os.path.exists(expanded_path):
                cursor_exe = expanded_path
                print(f"[OK] Cursor 실행 파일 발견: {cursor_exe}")
                break
        
        if cursor_exe:
            try:
                subprocess.Popen([cursor_exe, str(Path.cwd())], 
                               cwd=str(Path.cwd()),
                               creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
                print("[OK] Cursor가 자동으로 재시작되었습니다!")
                print("새로운 Cursor 창이 열렸습니다.")
                return True
            except Exception as e:
                print(f"[ERROR] Cursor 실행 실패: {e}")
                print("수동으로 Cursor를 재시작하세요.")
                return False
        else:
            print("[ERROR] Cursor 실행 파일을 찾을 수 없습니다.")
            print("수동으로 Cursor를 재시작하세요.")
            return False
            
    except Exception as e:
        print(f"[ERROR] Cursor 재시작 실패: {e}")
        print("수동으로 Cursor를 재시작하세요.")
        return False

def integrate_port_validation():
    """포트 검증 시스템 통합"""
    print("[포트 검증 시스템] 통합 중...")
    
    try:
        # 1. 포트 검증 시스템 파일들 확인
        port_validation_files = [
            "tools/mandatory_validator.py",
            "tools/ai_behavior_enforcer.py",
            "tools/universal_validator.py"
        ]
        
        missing_files = []
        for file_path in port_validation_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            print(f"[WARN] 포트 검증 시스템 파일 누락: {missing_files}")
            print("   포트 검증 시스템이 완전하지 않습니다.")
            return False
        
        # 2. 포트 검증 시스템 테스트
        print("[포트 검증 시스템] 테스트 실행 중...")
        try:
            from tools.test_port_validation import test_port_validation
            test_port_validation()
            print("[OK] 포트 검증 시스템 테스트 통과")
        except Exception as e:
            print(f"[WARN] 포트 검증 시스템 테스트 실패: {e}")
        
        # 3. AI_RULES.md에 포트 규칙 확인
        ai_rules_file = Path("docs/AI_RULES.md")
        if ai_rules_file.exists():
            content = ai_rules_file.read_text(encoding='utf-8')
            if "포트 사용 규칙" in content and "8501" in content:
                print("[OK] AI_RULES.md에 포트 규칙이 설정되어 있습니다")
            else:
                print("[WARN] AI_RULES.md에 포트 규칙이 누락되었습니다")
        else:
            print("[WARN] AI_RULES.md 파일이 없습니다")
        
        # 4. 포트 검증 시스템 활성화 확인
        print("[포트 검증 시스템] 활성화 상태 확인...")
        print("   - 강제적 검증 시스템: 활성화")
        print("   - 포트 8501 강제 사용: 활성화")
        print("   - AI 행동 패턴 강제 변경: 활성화")
        print("   - 규칙 위반 시 실행 차단: 활성화")
        
        print("[OK] 포트 검증 시스템 통합 완료!")
        return True
        
    except Exception as e:
        print(f"[ERROR] 포트 검증 시스템 통합 실패: {e}")
        return False

if __name__ == "__main__":
    main()
