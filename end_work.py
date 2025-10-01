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

def sync_cursor_rules_for_upload():
    """업로드 전 Cursor 규칙 파일 동기화"""
    print("\n[Cursor 규칙 동기화] 업로드 준비 중...")
    
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

**이 규칙을 위반하면 코드 리뷰에서 거부됩니다.**'''
        
        # Linear 컴포넌트 규칙 파일 저장
        linear_rules_file = cursor_rules_dir / "linear-components.mdc"
        with open(linear_rules_file, 'w', encoding='utf-8') as f:
            f.write(linear_rules_content)
        
        print("[Cursor 규칙 동기화] Linear 컴포넌트 규칙 파일 업데이트 완료")
        
        # .cursorrules 파일도 생성 (호환성을 위해)
        cursorrules_content = linear_rules_content.replace('---\nalwaysApply: true\n---', '')
        cursorrules_file = Path(".cursorrules")
        with open(cursorrules_file, 'w', encoding='utf-8') as f:
            f.write(cursorrules_content)
        
        print("[Cursor 규칙 동기화] .cursorrules 파일 업데이트 완료")
        
        # components.md 파일도 생성 (문서용)
        components_md_content = cursorrules_content
        components_md_file = Path("components.md")
        with open(components_md_file, 'w', encoding='utf-8') as f:
            f.write(components_md_content)
        
        print("[Cursor 규칙 동기화] components.md 파일 업데이트 완료")
        
        print("[Cursor 규칙 동기화] 모든 규칙 파일이 업로드 준비되었습니다!")
        
    except Exception as e:
        print(f"[Cursor 규칙 동기화] 오류: {e}")
        print("수동으로 규칙 파일을 확인해주세요.")

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
    print("[변경사항 확인] 실행 중...")
    try:
        result = subprocess.run("git status --porcelain", shell=True, capture_output=True, text=True, 
                              cwd=Path.cwd(), encoding='utf-8', errors='ignore')
        if result.returncode == 0:
            print("[변경사항 확인] 완료")
            if result.stdout and result.stdout.strip():
                print(f"   {result.stdout.strip()}")
                has_changes = True
            else:
                print("   변경사항 없음")
                has_changes = False
        else:
            print(f"[변경사항 확인] 실패: {result.stderr.strip() if result.stderr else 'Unknown error'}")
            has_changes = False
    except Exception as e:
        print(f"[변경사항 확인] 오류: {e}")
        has_changes = False
    
    # 2. 변경사항이 있을 때만 커밋
    if has_changes:
        # 변경사항 추가
        if not run_command("git add .", "변경사항 추가"):
            print("Git add 실패. 작업을 중단합니다.")
            return
        
        # 커밋
        commit_message = f"작업 완료: {work_description} ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
        if not run_command(f'git commit -m "{commit_message}"', "커밋"):
            print("Git commit 실패. 작업을 중단합니다.")
            return
    else:
        print("변경사항이 없어서 커밋을 건너뜁니다.")
    
    # 4. 원격 저장소에 업로드
    if not run_command("git push origin main", "원격 저장소 업로드"):
        print("Git push 실패. 작업을 중단합니다.")
        return
    
    # 5. Cursor 규칙 자동 동기화 (업로드 전)
    sync_cursor_rules_for_upload()
    
    # 6. 작업 로그 업데이트
    update_work_log(work_description)
    
    print("\n작업 종료 완료!")
    print("모든 변경사항이 원격 저장소에 업로드되었습니다.")
    
    # Cursor 설정 백업 옵션
    backup_choice = input("\nCursor 설정을 백업하시겠습니까? (y/n): ").strip().lower()
    if backup_choice == 'y':
        try:
            from sync_cursor_settings import backup_cursor_settings
            if backup_cursor_settings():
                print("Cursor 설정 백업 완료! 자동으로 Git에 커밋합니다.")
                
                # Cursor 설정 백업 파일들을 자동으로 커밋
                if run_command("git add .cursor_settings/", "Cursor 설정 파일 추가"):
                    if run_command('git commit -m "Cursor 설정 백업"', "Cursor 설정 커밋"):
                        if run_command("git push origin main", "Cursor 설정 푸시"):
                            print("✅ Cursor 설정이 자동으로 백업되고 동기화되었습니다!")
                        else:
                            print("❌ Cursor 설정 푸시 실패")
                    else:
                        print("❌ Cursor 설정 커밋 실패")
                else:
                    print("❌ Cursor 설정 파일 추가 실패")
        except ImportError:
            print("Cursor 설정 동기화 스크립트를 찾을 수 없습니다.")
        except Exception as e:
            print(f"Cursor 설정 백업 실패: {e}")

if __name__ == "__main__":
    main()
