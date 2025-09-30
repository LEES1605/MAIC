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
    
    # 0. Git 저장소 확인 및 자동 클론
    if not check_git_repo():
        return
    
    # 1. 최신 코드 가져오기
    if not run_command("git pull origin main", "최신 코드 가져오기"):
        print("Git pull 실패. 계속 진행하시겠습니까? (y/n): ", end="")
        if input().lower() != 'y':
            return
    
    # 2. 현재 상태 확인
    run_command("git status", "현재 상태 확인")
    
    # 3. 작업 로그 확인
    log_file = Path("WORK_SESSION_LOG.md")
    if log_file.exists():
        print("\n최근 작업 로그:")
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # 마지막 10줄만 표시
            for line in lines[-10:]:
                print(f"   {line.strip()}")
    
    # 4. 오늘 날짜로 작업 시작 기록
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
                    try:
                        # Cursor 프로세스 찾기 및 재시작
                        import psutil
                        import time
                        
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
                            
                            # 잠시 대기
                            time.sleep(2)
                            
                            # Cursor 재시작
                            import subprocess
                            import os
                            
                            # Cursor 실행 파일 경로 찾기
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
                                # 현재 작업 디렉토리에서 Cursor 시작
                                subprocess.Popen([cursor_exe, str(Path.cwd())], 
                                               cwd=str(Path.cwd()))
                                print("✅ Cursor가 자동으로 재시작되었습니다!")
                            else:
                                print("❌ Cursor 실행 파일을 찾을 수 없습니다. 수동으로 재시작하세요.")
                        else:
                            print("❌ 실행 중인 Cursor 프로세스를 찾을 수 없습니다.")
                            
                    except ImportError:
                        print("❌ psutil 모듈이 없습니다. 수동으로 재시작하세요.")
                        print("설치: pip install psutil")
                    except Exception as e:
                        print(f"❌ 자동 재시작 실패: {e}")
                        print("수동으로 Cursor를 재시작하세요.")
                else:
                    print("수동으로 Cursor를 재시작하세요.")
        except ImportError:
            print("Cursor 설정 동기화 스크립트를 찾을 수 없습니다.")
        except Exception as e:
            print(f"Cursor 설정 동기화 실패: {e}")

if __name__ == "__main__":
    main()
