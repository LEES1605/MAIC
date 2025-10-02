#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cursor 자동 재시작 테스트
"""

import subprocess
import sys
import os
from pathlib import Path

def test_cursor_restart():
    print("Cursor 자동 재시작 테스트")
    print("=" * 30)
    
    # Cursor 실행 파일 찾기
    cursor_paths = [
        r"C:\Program Files\Cursor\Cursor.exe",
        r"C:\Program Files\cursor\cursor.exe"
    ]
    
    cursor_exe = None
    for path in cursor_paths:
        if os.path.exists(path):
            cursor_exe = path
            print(f"[OK] Cursor 실행 파일 발견: {path}")
            break
    
    if not cursor_exe:
        print("[ERROR] Cursor 실행 파일을 찾을 수 없습니다.")
        return False
    
    try:
        # 현재 디렉토리에서 Cursor 시작
        result = subprocess.Popen([cursor_exe, str(Path.cwd())], 
                                cwd=str(Path.cwd()),
                                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
        print(f"[OK] Cursor가 자동으로 재시작되었습니다! PID: {result.pid}")
        print("새로운 Cursor 창이 열렸습니다.")
        return True
    except Exception as e:
        print(f"[ERROR] Cursor 실행 실패: {e}")
        return False

if __name__ == "__main__":
    test_cursor_restart()

