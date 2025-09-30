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
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=Path.cwd())
        if result.returncode == 0:
            print(f"[{description}] 완료")
            if result.stdout.strip():
                print(f"   {result.stdout.strip()}")
        else:
            print(f"[{description}] 실패: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"[{description}] 오류: {e}")
        return False
    return True

def main():
    print("작업 시작 자동화 스크립트")
    print("=" * 50)
    
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

if __name__ == "__main__":
    main()
