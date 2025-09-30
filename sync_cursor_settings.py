#!/usr/bin/env python3
"""
Cursor 설정 동기화 스크립트
집과 학원에서 Cursor 설정을 자동으로 동기화
"""

import os
import shutil
import json
from pathlib import Path
from datetime import datetime

def get_cursor_settings_path():
    """Cursor 설정 폴더 경로 반환"""
    if os.name == 'nt':  # Windows
        return Path(os.environ['APPDATA']) / 'Cursor' / 'User'
    elif os.name == 'posix':  # macOS/Linux
        if os.uname().sysname == 'Darwin':  # macOS
            return Path.home() / 'Library' / 'Application Support' / 'Cursor' / 'User'
        else:  # Linux
            return Path.home() / '.config' / 'Cursor' / 'User'
    else:
        raise OSError("지원하지 않는 운영체제입니다.")

def backup_cursor_settings():
    """현재 Cursor 설정을 프로젝트에 백업"""
    cursor_path = get_cursor_settings_path()
    backup_path = Path.cwd() / '.cursor_settings'
    
    if not cursor_path.exists():
        print(f"Cursor 설정 폴더를 찾을 수 없습니다: {cursor_path}")
        return False
    
    # 백업 폴더 생성
    backup_path.mkdir(exist_ok=True)
    
    # 설정 파일들 복사
    files_to_sync = [
        'settings.json',
        'keybindings.json',
        'snippets',
        'extensions'
    ]
    
    for file_name in files_to_sync:
        src = cursor_path / file_name
        dst = backup_path / file_name
        
        if src.exists():
            if src.is_file():
                shutil.copy2(src, dst)
                print(f"백업 완료: {file_name}")
            elif src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                print(f"백업 완료: {file_name}/")
        else:
            print(f"파일 없음: {file_name}")
    
    # 백업 정보 저장
    backup_info = {
        'timestamp': datetime.now().isoformat(),
        'cursor_path': str(cursor_path),
        'backup_path': str(backup_path)
    }
    
    with open(backup_path / 'backup_info.json', 'w', encoding='utf-8') as f:
        json.dump(backup_info, f, indent=2, ensure_ascii=False)
    
    print(f"Cursor 설정 백업 완료: {backup_path}")
    return True

def restore_cursor_settings():
    """프로젝트의 Cursor 설정을 복원"""
    backup_path = Path.cwd() / '.cursor_settings'
    cursor_path = get_cursor_settings_path()
    
    if not backup_path.exists():
        print(f"백업 폴더를 찾을 수 없습니다: {backup_path}")
        return False
    
    # Cursor 설정 폴더 생성
    cursor_path.mkdir(parents=True, exist_ok=True)
    
    # 설정 파일들 복원
    files_to_sync = [
        'settings.json',
        'keybindings.json',
        'snippets',
        'extensions'
    ]
    
    for file_name in files_to_sync:
        src = backup_path / file_name
        dst = cursor_path / file_name
        
        if src.exists():
            if src.is_file():
                shutil.copy2(src, dst)
                print(f"복원 완료: {file_name}")
            elif src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                print(f"복원 완료: {file_name}/")
        else:
            print(f"백업 파일 없음: {file_name}")
    
    print(f"Cursor 설정 복원 완료: {cursor_path}")
    return True

def main():
    print("Cursor 설정 동기화 스크립트")
    print("=" * 50)
    
    print("1. 현재 설정 백업")
    print("2. 백업된 설정 복원")
    print("3. 종료")
    
    choice = input("선택하세요 (1-3): ").strip()
    
    if choice == '1':
        if backup_cursor_settings():
            print("\n백업 완료! Git에 커밋하세요:")
            print("git add .cursor_settings/")
            print("git commit -m 'Cursor 설정 백업'")
            print("git push origin main")
    elif choice == '2':
        if restore_cursor_settings():
            print("\n복원 완료! Cursor를 재시작하세요.")
    elif choice == '3':
        print("종료합니다.")
    else:
        print("잘못된 선택입니다.")

if __name__ == "__main__":
    main()
