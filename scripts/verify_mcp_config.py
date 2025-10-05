#!/usr/bin/env python3
"""
MCP 설정 검증 스크립트
MAIC 프로젝트의 MCP 설정이 올바른지 확인합니다.
"""

import json
import os
from pathlib import Path

def verify_mcp_config():
    """MCP 설정 검증"""
    print("[INFO] MCP 설정 검증 시작...")
    
    # 프로젝트 설정 파일 경로
    project_config = Path(".cursor/config.json")
    global_config = Path(os.path.expanduser("~/AppData/Roaming/Cursor/User/mcp.json"))
    
    # 1. 프로젝트 설정 파일 존재 확인
    if not project_config.exists():
        print("[ERROR] 프로젝트 설정 파일이 없습니다: .cursor/config.json")
        return False
    
    # 2. 프로젝트 설정 파일 로드
    try:
        with open(project_config, 'r', encoding='utf-8') as f:
            project_data = json.load(f)
    except Exception as e:
        print(f"[ERROR] 프로젝트 설정 파일 로드 실패: {e}")
        return False
    
    # 3. 전역 설정 파일 존재 확인
    if not global_config.exists():
        print("[ERROR] 전역 설정 파일이 없습니다: AppData/Roaming/Cursor/User/mcp.json")
        return False
    
    # 4. 전역 설정 파일 로드
    try:
        with open(global_config, 'r', encoding='utf-8') as f:
            global_data = json.load(f)
    except Exception as e:
        print(f"[ERROR] 전역 설정 파일 로드 실패: {e}")
        return False
    
    # 5. 설정 파일 내용 비교
    if project_data != global_data:
        print("[ERROR] 프로젝트 설정과 전역 설정이 다릅니다!")
        print("   해결방법: start_work.py 실행 또는 수동 동기화")
        return False
    
    # 6. 필수 MCP 서버 확인
    required_servers = [
        "GitKraken", "playwright", "supabase", 
        "filesystem", "memory", "sequential-thinking"
    ]
    
    mcp_servers = project_data.get("mcpServers", {})
    missing_servers = [server for server in required_servers if server not in mcp_servers]
    
    if missing_servers:
        print(f"[ERROR] 필수 MCP 서버가 누락되었습니다: {missing_servers}")
        return False
    
    # 7. 도구 수 추정
    estimated_tools = len(mcp_servers) * 20  # 서버당 평균 20개 도구
    if estimated_tools > 150:
        print(f"[WARN] 도구 수가 많습니다: ~{estimated_tools}개 (권장: 80개 이하)")
        print("   불필요한 서버 제거를 고려하세요.")
    
    # 8. 환경변수 확인
    supabase_config = mcp_servers.get("supabase", {})
    env_vars = supabase_config.get("env", {})
    
    if "SUPABASE_URL" in env_vars and env_vars["SUPABASE_URL"]:
        print("[OK] Supabase URL 설정됨")
    else:
        print("[WARN] Supabase URL이 설정되지 않았습니다")
    
    if "SUPABASE_SERVICE_ROLE_KEY" in env_vars and env_vars["SUPABASE_SERVICE_ROLE_KEY"]:
        print("[OK] Supabase 서비스 키 설정됨")
    else:
        print("[WARN] Supabase 서비스 키가 설정되지 않았습니다")
    
    print("\n[OK] MCP 설정 검증 완료!")
    print(f"   설정된 서버: {len(mcp_servers)}개")
    print(f"   예상 도구 수: ~{estimated_tools}개")
    print("   모든 설정이 올바르게 구성되었습니다.")
    
    return True

if __name__ == "__main__":
    success = verify_mcp_config()
    exit(0 if success else 1)
