#!/usr/bin/env python3
"""
작업 종료 자동화 스크립트
집/학원에서 작업을 완료할 때 실행
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

def update_work_log(work_description):
    """작업 로그 업데이트"""
    log_file = Path("WORK_SESSION_LOG.md")
    today = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%H:%M")
    
    # 로그 파일이 없으면 생성
    if not log_file.exists():
        log_file.write_text(f"""# 작업 세션 로그

## {today}

### 집 (홈)
- [ ] 

### 학원 (아카데미)  
- [ ] 

## 다음 작업 계획
- [ ] 
- [ ] 
""", encoding='utf-8')
    
    # 기존 로그 읽기
    content = log_file.read_text(encoding='utf-8')
    
    # 오늘 날짜 섹션이 없으면 추가
    if f"## {today}" not in content:
        content += f"\n## {today}\n\n### 집 (홈)\n- [ ] \n\n### 학원 (아카데미)\n- [ ] \n\n"
    
    # 작업 내용 추가 (간단한 형태)
    lines = content.split('\n')
    new_lines = []
    in_today_section = False
    
    for line in lines:
        new_lines.append(line)
        if f"## {today}" in line:
            in_today_section = True
        elif in_today_section and line.startswith("## "):
            # 다음 날짜 섹션을 만나면 오늘 섹션 종료
            in_today_section = False
        elif in_today_section and line.startswith("- [ ]") and not line.strip().endswith("- [ ]"):
            # 빈 작업 항목을 찾으면 작업 내용 추가
            new_lines.append(f"- [x] {work_description} ({timestamp})")
    
    # 로그 파일 업데이트
    log_file.write_text('\n'.join(new_lines), encoding='utf-8')
    print(f"작업 로그 업데이트: {work_description}")

def main():
    print("작업 종료 자동화 스크립트")
    print("=" * 50)
    
    # 작업 내용 입력 받기
    work_description = input("오늘 작업한 내용을 간단히 입력하세요: ").strip()
    if not work_description:
        work_description = "작업 완료"
    
    # 1. 변경사항 확인
    run_command("git status", "변경사항 확인")
    
    # 2. 변경사항 추가
    if not run_command("git add .", "변경사항 추가"):
        print("Git add 실패. 작업을 중단합니다.")
        return
    
    # 3. 커밋
    commit_message = f"작업 완료: {work_description} ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
    if not run_command(f'git commit -m "{commit_message}"', "커밋"):
        print("Git commit 실패. 작업을 중단합니다.")
        return
    
    # 4. 원격 저장소에 업로드
    if not run_command("git push origin main", "원격 저장소 업로드"):
        print("Git push 실패. 작업을 중단합니다.")
        return
    
    # 5. 작업 로그 업데이트
    update_work_log(work_description)
    
    print("\n작업 종료 완료!")
    print("모든 변경사항이 원격 저장소에 업로드되었습니다.")
    
    # Cursor 설정 백업 옵션
    backup_choice = input("\nCursor 설정을 백업하시겠습니까? (y/n): ").strip().lower()
    if backup_choice == 'y':
        try:
            from sync_cursor_settings import backup_cursor_settings
            if backup_cursor_settings():
                print("Cursor 설정 백업 완료! Git에 커밋하세요.")
        except ImportError:
            print("Cursor 설정 동기화 스크립트를 찾을 수 없습니다.")
        except Exception as e:
            print(f"Cursor 설정 백업 실패: {e}")

if __name__ == "__main__":
    main()
