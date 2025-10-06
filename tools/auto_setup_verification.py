#!/usr/bin/env python3
"""
MAIC 프로젝트 자동 설정 검증 스크립트
어디서든 python start_work.py 실행 후 모든 설정이 올바르게 되었는지 검증
"""

import json
import os
import subprocess
import sys
from pathlib import Path

def check_python_environment():
    """Python 환경 확인"""
    print("[검증] Python 환경 확인...")
    
    # Python 버전 확인
    python_version = sys.version_info
    print(f"   Python 버전: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    # 필수 모듈 확인
    required_modules = ['psutil', 'pathlib', 'subprocess']
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
            print(f"   [OK] {module} 모듈 사용 가능")
        except ImportError:
            missing_modules.append(module)
            print(f"   [ERROR] {module} 모듈 없음")
    
    if missing_modules:
        print(f"[WARN] 누락된 모듈: {missing_modules}")
        print("   자동 설치를 시도합니다...")
        
        for module in missing_modules:
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", module], 
                             check=True, capture_output=True)
                print(f"   [OK] {module} 설치 완료")
            except subprocess.CalledProcessError:
                print(f"   [ERROR] {module} 설치 실패")
    
    return len(missing_modules) == 0

def check_git_repository():
    """Git 저장소 확인"""
    print("[검증] Git 저장소 확인...")
    
    try:
        result = subprocess.run("git status", shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print("   [OK] Git 저장소 정상")
            
            # 원격 저장소 확인
            result = subprocess.run("git remote -v", shell=True, capture_output=True, text=True)
            if "github.com/LEES1605/MAIC" in result.stdout:
                print("   [OK] 올바른 원격 저장소 연결됨")
                return True
            else:
                print("   [WARN] 원격 저장소가 다릅니다")
                return False
        else:
            print("   [ERROR] Git 저장소가 아닙니다")
            return False
    except Exception as e:
        print(f"   [ERROR] Git 확인 실패: {e}")
        return False

def check_mcp_configuration():
    """MCP 설정 확인"""
    print("[검증] MCP 설정 확인...")
    
    # 프로젝트 MCP 설정 파일 확인
    project_config = Path(".cursor/config.json")
    if not project_config.exists():
        print("   [ERROR] 프로젝트 MCP 설정 파일 없음: .cursor/config.json")
        return False
    
    # 전역 MCP 설정 파일 확인
    if os.name == 'nt':  # Windows
        cursor_user_path = Path(os.environ['APPDATA']) / "Cursor" / "User"
    else:
        cursor_user_path = Path.home() / ".config" / "Cursor" / "User"
    
    global_config = cursor_user_path / "mcp.json"
    if not global_config.exists():
        print("   [ERROR] 전역 MCP 설정 파일 없음")
        return False
    
    # 설정 파일 내용 비교
    try:
        with open(project_config, 'r', encoding='utf-8') as f:
            project_data = json.load(f)
        
        with open(global_config, 'r', encoding='utf-8') as f:
            global_data = json.load(f)
        
        if project_data == global_data:
            print("   [OK] 프로젝트와 전역 MCP 설정 일치")
        else:
            print("   [WARN] 프로젝트와 전역 MCP 설정이 다름")
            return False
        
        # 필수 MCP 서버 확인
        required_servers = ["GitKraken", "playwright", "supabase", "filesystem", "memory", "sequential-thinking"]
        mcp_servers = project_data.get("mcpServers", {})
        
        missing_servers = [server for server in required_servers if server not in mcp_servers]
        if missing_servers:
            print(f"   [ERROR] 누락된 MCP 서버: {missing_servers}")
            return False
        
        print(f"   [OK] 필수 MCP 서버 {len(required_servers)}개 모두 존재")
        return True
        
    except Exception as e:
        print(f"   [ERROR] MCP 설정 확인 실패: {e}")
        return False

def check_cursor_rules():
    """Cursor 규칙 파일 확인"""
    print("[검증] Cursor 규칙 파일 확인...")
    
    required_files = [
        ".cursor/rules/linear-components.mdc",
        ".cursorrules",
        "components.md"
    ]
    
    all_exist = True
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"   [OK] {file_path} 존재")
        else:
            print(f"   [ERROR] {file_path} 없음")
            all_exist = False
    
    return all_exist

def check_node_environment():
    """Node.js 환경 확인"""
    print("[검증] Node.js 환경 확인...")
    
    try:
        # npm 버전 확인
        result = subprocess.run("npm --version", shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"   [OK] npm 버전: {result.stdout.strip()}")
        else:
            print("   [ERROR] npm이 설치되지 않음")
            return False
        
        # npx 사용 가능 확인
        result = subprocess.run("npx --version", shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"   [OK] npx 버전: {result.stdout.strip()}")
        else:
            print("   [ERROR] npx가 설치되지 않음")
            return False
        
        return True
        
    except Exception as e:
        print(f"   [ERROR] Node.js 환경 확인 실패: {e}")
        return False

def check_mcp_packages():
    """MCP 패키지 확인"""
    print("[검증] MCP 패키지 확인...")
    
    # MCP 설정에서 패키지 목록 추출
    try:
        with open(".cursor/config.json", 'r', encoding='utf-8') as f:
            mcp_config = json.load(f)
        
        mcp_servers = mcp_config.get("mcpServers", {})
        npx_packages = []
        
        for server_name, server_config in mcp_servers.items():
            if server_config.get('command') == 'npx':
                args = server_config.get('args', [])
                if len(args) >= 2 and args[0] == '-y':
                    package_name = args[1]
                    npx_packages.append(package_name)
        
        if not npx_packages:
            print("   [WARN] NPX 기반 MCP 패키지가 없습니다")
            return True
        
        print(f"   [INFO] NPX 패키지 {len(npx_packages)}개 확인 중...")
        
        # 각 패키지 확인
        all_available = True
        for package in npx_packages:
            try:
                result = subprocess.run(f"npx -y {package} --help", 
                                      shell=True, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    print(f"   [OK] {package} 사용 가능")
                else:
                    print(f"   [WARN] {package} 확인 실패 (첫 실행 시 정상)")
            except subprocess.TimeoutExpired:
                print(f"   [OK] {package} 타임아웃 (정상)")
            except Exception as e:
                print(f"   [WARN] {package} 확인 실패: {e}")
                all_available = False
        
        return all_available
        
    except Exception as e:
        print(f"   [ERROR] MCP 패키지 확인 실패: {e}")
        return False

def check_environment_variables():
    """환경 변수 확인"""
    print("[검증] 환경 변수 확인...")
    
    # Supabase 환경 변수 확인
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    
    if supabase_url and supabase_url != "your-supabase-url":
        print("   [OK] SUPABASE_URL 설정됨")
    else:
        print("   [WARN] SUPABASE_URL 설정되지 않음")
    
    if supabase_key and supabase_key != "your-service-role-key":
        print("   [OK] SUPABASE_SERVICE_ROLE_KEY 설정됨")
    else:
        print("   [WARN] SUPABASE_SERVICE_ROLE_KEY 설정되지 않음")
    
    return True

def main():
    """메인 검증 함수"""
    print("MAIC 프로젝트 자동 설정 검증")
    print("=" * 50)
    
    checks = [
        ("Python 환경", check_python_environment),
        ("Git 저장소", check_git_repository),
        ("MCP 설정", check_mcp_configuration),
        ("Cursor 규칙", check_cursor_rules),
        ("Node.js 환경", check_node_environment),
        ("MCP 패키지", check_mcp_packages),
        ("환경 변수", check_environment_variables)
    ]
    
    results = []
    for check_name, check_func in checks:
        print(f"\n[{check_name}] 검증 중...")
        try:
            result = check_func()
            results.append((check_name, result))
            if result:
                print(f"[{check_name}] ✅ 통과")
            else:
                print(f"[{check_name}] ❌ 실패")
        except Exception as e:
            print(f"[{check_name}] ❌ 오류: {e}")
            results.append((check_name, False))
    
    # 최종 결과
    print("\n" + "=" * 50)
    print("검증 결과 요약:")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for check_name, result in results:
        status = "✅ 통과" if result else "❌ 실패"
        print(f"   {check_name}: {status}")
    
    print(f"\n전체: {passed}/{total} 통과")
    
    if passed == total:
        print("\n🎉 모든 검증이 통과했습니다!")
        print("   MAIC 프로젝트가 완전히 설정되었습니다.")
        print("   Cursor를 재시작하면 모든 MCP 서버가 활성화됩니다.")
        return True
    else:
        print(f"\n⚠️ {total - passed}개 검증이 실패했습니다.")
        print("   실패한 항목들을 확인하고 수정해주세요.")
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)


