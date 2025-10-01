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
    
    # Cursor 설정 동기화 옵션
    sync_choice = input("\nCursor 설정을 동기화하시겠습니까? (y/n): ").strip().lower()
    if sync_choice == 'y':
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
