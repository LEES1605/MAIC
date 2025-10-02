#!/usr/bin/env python3
"""
Cursor 자동 재시작 기능 테스트 스크립트
"""

import subprocess
import sys
import os
from pathlib import Path

def test_psutil():
    """psutil 모듈 테스트"""
    print("=== psutil 모듈 테스트 ===")
    try:
        import psutil
        print("[OK] psutil 모듈이 설치되어 있습니다.")
        
        # 프로세스 목록 확인
        print(f"총 프로세스 수: {len(list(psutil.process_iter()))}")
        
        # Cursor 프로세스 찾기
        cursor_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                proc_info = proc.info
                if proc_info['name'] and 'cursor' in proc_info['name'].lower():
                    cursor_processes.append(proc)
                    print(f"  - Cursor 프로세스 발견: PID {proc_info['pid']}, 이름: {proc_info['name']}")
                elif proc_info['exe'] and 'cursor' in proc_info['exe'].lower():
                    cursor_processes.append(proc)
                    print(f"  - Cursor 프로세스 발견: PID {proc_info['pid']}, 경로: {proc_info['exe']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        if not cursor_processes:
            print("[ERROR] 실행 중인 Cursor 프로세스를 찾을 수 없습니다.")
        else:
            print(f"[OK] {len(cursor_processes)}개의 Cursor 프로세스를 발견했습니다.")
        
        return True
    except ImportError:
        print("[ERROR] psutil 모듈이 설치되어 있지 않습니다.")
        print("설치 명령어: pip install psutil")
        return False

def test_cursor_paths():
    """Cursor 실행 파일 경로 테스트"""
    print("\n=== Cursor 실행 파일 경로 테스트 ===")
    
    cursor_paths = [
        r"C:\Users\%USERNAME%\AppData\Local\Programs\cursor\Cursor.exe",
        r"C:\Program Files\Cursor\Cursor.exe",
        r"C:\Program Files (x86)\Cursor\Cursor.exe",
        r"C:\Users\%USERNAME%\AppData\Local\Programs\cursor\cursor.exe",
        r"C:\Program Files\cursor\cursor.exe",
        r"C:\Program Files (x86)\cursor\cursor.exe"
    ]
    
    found_paths = []
    for path in cursor_paths:
        expanded_path = os.path.expandvars(path)
        if os.path.exists(expanded_path):
            found_paths.append(expanded_path)
            print(f"[OK] 발견: {expanded_path}")
        else:
            print(f"[ERROR] 없음: {expanded_path}")
    
    if found_paths:
        print(f"\n[OK] {len(found_paths)}개의 Cursor 실행 파일을 발견했습니다.")
        return found_paths[0]  # 첫 번째 발견된 경로 반환
    else:
        print("\n[ERROR] Cursor 실행 파일을 찾을 수 없습니다.")
        return None

def test_cursor_launch(cursor_exe):
    """Cursor 실행 테스트"""
    print(f"\n=== Cursor 실행 테스트 ===")
    if not cursor_exe:
        print("[ERROR] Cursor 실행 파일이 없어서 테스트를 건너뜁니다.")
        return False
    
    try:
        # 현재 디렉토리에서 Cursor 시작
        result = subprocess.Popen([cursor_exe, str(Path.cwd())], 
                                cwd=str(Path.cwd()),
                                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
        print(f"[OK] Cursor 실행 성공! PID: {result.pid}")
        return True
    except Exception as e:
        print(f"[ERROR] Cursor 실행 실패: {e}")
        return False

def main():
    print("Cursor 자동 재시작 기능 진단 도구")
    print("=" * 50)
    
    # 1. psutil 테스트
    psutil_ok = test_psutil()
    
    # 2. Cursor 경로 테스트
    cursor_exe = test_cursor_paths()
    
    # 3. Cursor 실행 테스트 (사용자 확인 후)
    if cursor_exe and psutil_ok:
        choice = input("\nCursor를 실행해서 테스트하시겠습니까? (y/n): ").strip().lower()
        if choice == 'y':
            test_cursor_launch(cursor_exe)
    
    print("\n=== 진단 결과 요약 ===")
    print(f"psutil 모듈: {'[OK] 정상' if psutil_ok else '[ERROR] 문제'}")
    print(f"Cursor 실행 파일: {'[OK] 발견' if cursor_exe else '[ERROR] 없음'}")
    
    if psutil_ok and cursor_exe:
        print("[OK] 모든 조건이 충족되었습니다. start_work.py의 자동 재시작 기능이 정상 작동할 것입니다.")
    else:
        print("[ERROR] 일부 조건이 충족되지 않았습니다. 위의 문제를 해결한 후 다시 시도하세요.")

if __name__ == "__main__":
    main()
