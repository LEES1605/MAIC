# MCP 설정 동기화 가이드

## 현재 상황
- 집에서 MCP 패키지들을 설치했지만 학원에서는 동기화되지 않음
- MCP는 Cursor 사용자별 설정으로 Git 추적 대상이 아님

## 해결 방법

### 1. MCP 설정 파일 백업/복원
```bash
# 집에서 실행 (MCP 설정 백업)
cp "$env:APPDATA\Cursor\User\settings.json" ./MAIC/.cursor/cursor_settings.json

# 학원에서 실행 (MCP 설정 복원)
cp ./MAIC/.cursor/cursor_settings.json "$env:APPDATA\Cursor\User\settings.json"
```

### 2. MCP 패키지 목록 관리
```bash
# MCP 패키지 목록 저장
pip list | findstr /i mcp > ./MAIC/.cursor/mcp_packages.txt

# MCP 패키지 일괄 설치
Get-Content ./MAIC/.cursor/mcp_packages.txt | ForEach-Object { pip install $_.Split()[0] }
```

### 3. 자동화 스크립트에 MCP 동기화 추가
- start_work.py에 MCP 설정 복원 로직 추가
- end_work.py에 MCP 설정 백업 로직 추가

## 권장사항
1. MCP 설정을 프로젝트에 포함시켜 버전 관리
2. 환경별 MCP 패키지 설치 스크립트 작성
3. Cursor 설정 파일도 동기화 대상에 포함


