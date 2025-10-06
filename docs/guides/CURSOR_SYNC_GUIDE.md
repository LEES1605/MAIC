# Cursor 동기화 방법 가이드

## 🎯 **방법 1: Cursor Settings Sync (권장)**

### **설정 동기화 활성화**
1. **Cursor 열기**
2. **Ctrl+Shift+P** → **"Settings Sync: Turn On"** 검색
3. **GitHub 계정으로 로그인**
4. **동기화할 항목 선택**:
   - ✅ Extensions (확장 프로그램)
   - ✅ Settings (설정)
   - ✅ Keyboard Shortcuts (키보드 단축키)
   - ✅ User Snippets (사용자 스니펫)
   - ✅ UI State (UI 상태)

### **확인 방법**
- Cursor 하단에 **"Settings Sync: On"** 표시
- 다른 컴퓨터에서 동일한 계정으로 로그인하면 자동 동기화

## 🎯 **방법 2: 수동 설정 동기화**

### **설정 파일 위치**
- **Windows**: `%APPDATA%\Cursor\User\settings.json`
- **macOS**: `~/Library/Application Support/Cursor/User/settings.json`
- **Linux**: `~/.config/Cursor/User/settings.json`

### **동기화할 파일들**
1. **`settings.json`** - 기본 설정
2. **`keybindings.json`** - 키보드 단축키
3. **`snippets/`** - 코드 스니펫
4. **`extensions/`** - 확장 프로그램 목록

### **수동 동기화 스크립트**
```bash
# 설정 파일들을 Git에 추가
git add settings.json keybindings.json
git commit -m "Cursor 설정 동기화"
git push origin main
```

## 🎯 **방법 3: 확장 프로그램 동기화**

### **확장 프로그램 목록 내보내기**
```bash
# Cursor 터미널에서
code --list-extensions > extensions.txt
```

### **확장 프로그램 설치**
```bash
# 다른 컴퓨터에서
cat extensions.txt | xargs -L 1 code --install-extension
```

## 🎯 **방법 4: 프로젝트별 설정**

### **워크스페이스 설정**
1. **프로젝트 폴더**에 `.vscode/` 폴더 생성
2. **설정 파일들**을 프로젝트에 포함
3. **Git으로 동기화**

### **워크스페이스 설정 파일**
```json
// .vscode/settings.json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true
}
```

## 🎯 **방법 5: 클라우드 동기화**

### **OneDrive/Google Drive**
1. **Cursor 설정 폴더**를 클라우드에 동기화
2. **심볼릭 링크** 생성
3. **자동 동기화**

### **Windows 심볼릭 링크**
```cmd
# OneDrive에 설정 폴더 이동 후
mklink /D "%APPDATA%\Cursor\User" "C:\Users\%USERNAME%\OneDrive\Cursor\User"
```

## 🎯 **추천 방법**

### **가장 간단한 방법**:
1. **Cursor Settings Sync** 사용 (방법 1)
2. **Git 기반 워크플로우** 사용 (이미 구현됨)

### **고급 사용자**:
1. **수동 설정 동기화** (방법 2)
2. **프로젝트별 설정** (방법 4)

## 🚨 **주의사항**

- **Settings Sync**는 Cursor Pro 계정이 필요할 수 있음
- **수동 동기화**는 설정 충돌 가능성 있음
- **클라우드 동기화**는 보안상 주의 필요

## 💡 **현재 상황에서 추천**

1. **Git 워크플로우** 사용 (이미 구현됨)
2. **Cursor Settings Sync** 시도
3. **안 되면 수동 설정 동기화**
