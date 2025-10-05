#!/usr/bin/env python3
"""
작업 시작 자동화 스크립트
집/학원에서 작업을 시작할 때 실행
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

def run_command(cmd, description):
    """명령어 실행 및 결과 출력"""
    print(f"[{description}] 실행 중...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, 
                              cwd=Path.cwd(), encoding='utf-8', errors='ignore')
        if result.returncode == 0:
            print(f"[{description}] 완료")
            if result.stdout and result.stdout.strip():
                print(f"   {result.stdout.strip()}")
        else:
            print(f"[{description}] 실패: {result.stderr.strip() if result.stderr else 'Unknown error'}")
            return False
    except Exception as e:
        print(f"[{description}] 오류: {e}")
        return False
    return True

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
                    
                    # 패키지 캐시 확인 (선택사항)
                    install_choice = input("NPX 패키지들을 미리 캐시하시겠습니까? (y/n): ").strip().lower()
                    if install_choice == 'y':
                        print("[INFO] NPX 패키지 캐시 중...")
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
        
        # 4. 환경 변수 확인
        print("\n[INFO] 환경 변수 확인...")
        env_vars_needed = set()
        
        for server_name, server_config in mcp_servers.items():
            env = server_config.get('env', {})
            for env_key, env_value in env.items():
                if env_value and 'your-' in str(env_value).lower():
                    env_vars_needed.add(env_key)
        
        if env_vars_needed:
            print("[WARN] 다음 환경 변수들을 설정해야 합니다:")
            for env_var in env_vars_needed:
                print(f"   - {env_var}")
            print("환경 변수는 시스템 설정에서 직접 설정하거나 .env 파일을 사용하세요.")
        else:
            print("[OK] 모든 환경 변수가 설정되어 있습니다.")
        
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
    
    # Git 저장소가 아니면 자동 클론
    print("Git 저장소가 아닙니다. 자동으로 클론하시겠습니까? (y/n): ", end="")
    if input().lower() != 'y':
        return False
    
    # 현재 디렉토리 확인
    current_dir = Path.cwd()
    print(f"현재 위치: {current_dir}")
    
    # 클론할 위치 선택
    clone_path = input("클론할 위치를 입력하세요 (엔터시 현재 위치): ").strip()
    if not clone_path:
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

def main():
    print("작업 시작 자동화 스크립트")
    print("=" * 50)
    
    # 0. 필요한 모듈 확인
    try:
        import psutil
        print("[OK] psutil 모듈 확인 완료")
    except ImportError:
        print("[WARN] psutil 모듈이 없습니다. Cursor 자동 재시작 기능이 제한될 수 있습니다.")
        print("   설치: pip install psutil")
    
    # 1. Git 저장소 확인 및 자동 클론
    if not check_git_repo():
        return
    
    # 2. 최신 코드 가져오기
    if not run_command("git pull origin main", "최신 코드 가져오기"):
        print("Git pull 실패. 계속 진행하시겠습니까? (y/n): ", end="")
        if input().lower() != 'y':
            return
    
    # 2.5. Linear 컴포넌트 규칙 자동 동기화
    sync_cursor_rules()
    
    # 3. 현재 상태 확인
    run_command("git status", "현재 상태 확인")
    
    # 4. 작업 로그 확인
    log_file = Path("WORK_SESSION_LOG.md")
    if log_file.exists():
        print("\n최근 작업 로그:")
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # 마지막 10줄만 표시
            for line in lines[-10:]:
                print(f"   {line.strip()}")
    
    # 5. 오늘 날짜로 작업 시작 기록
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n오늘 날짜: {today}")
    
    print("\n작업 시작 준비 완료!")
    print("작업 완료 후 'python end_work.py'를 실행하세요.")
    
    # Cursor 설정 및 MCP 동기화 옵션
    sync_choice = input("\nCursor 설정과 MCP를 동기화하시겠습니까? (y/n): ").strip().lower()
    if sync_choice == 'y':
        sync_mcp_settings()
        
        try:
            from sync_cursor_settings import restore_cursor_settings
            if restore_cursor_settings():
                print("Cursor 설정 복원 완료!")
                
                # Cursor 자동 재시작 옵션
                restart_choice = input("Cursor를 자동으로 재시작하시겠습니까? (y/n): ").strip().lower()
                if restart_choice == 'y':
                    print("Cursor를 재시작합니다...")
                    
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
                    
                    try:
                        import time
                        import os
                        
                        # Cursor 프로세스 찾기 (더 정확한 방법)
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
                            # Cursor 실행 파일 경로 찾기 (더 많은 경로 포함)
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
                                # 현재 작업 디렉토리에서 Cursor 시작
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
                        else:
                            print("[ERROR] 실행 중인 Cursor 프로세스를 찾을 수 없습니다.")
                            print("Cursor가 실행 중이 아닐 수 있습니다.")
                            
                            # Cursor 실행 파일만 찾아서 실행
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
                                    break
                            
                            if cursor_exe:
                                try:
                                    subprocess.Popen([cursor_exe, str(Path.cwd())], 
                                                   cwd=str(Path.cwd()),
                                                   creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
                                    print("[OK] Cursor가 시작되었습니다!")
                                except Exception as e:
                                    print(f"[ERROR] Cursor 실행 실패: {e}")
                                    print("수동으로 Cursor를 시작하세요.")
                            else:
                                print("[ERROR] Cursor 실행 파일을 찾을 수 없습니다.")
                                print("수동으로 Cursor를 시작하세요.")
                            
                    except Exception as e:
                        print(f"[ERROR] 자동 재시작 실패: {e}")
                        print("수동으로 Cursor를 재시작하세요.")
                else:
                    print("수동으로 Cursor를 재시작하세요.")
        except ImportError:
            print("Cursor 설정 동기화 스크립트를 찾을 수 없습니다.")
        except Exception as e:
            print(f"Cursor 설정 동기화 실패: {e}")

if __name__ == "__main__":
    main()
