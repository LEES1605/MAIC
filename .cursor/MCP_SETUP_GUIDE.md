# MCP 설정 가이드 - MAIC 프로젝트

## 📋 **MCP 서버 구성**

### **현재 설치된 MCP 서버 (6개)**

| 서버명 | 용도 | 도구 수 | 필수 여부 |
|--------|------|---------|-----------|
| **GitKraken** | Git 관리, PR, 이슈 추적 | ~30개 | ✅ 필수 |
| **playwright** | E2E 테스트 (Streamlit) | ~25개 | ✅ 필수 |
| **supabase** | 데이터베이스, 인증 | ~15개 | ✅ 필수 |
| **filesystem** | 파일 시스템 관리 | ~20개 | ✅ 필수 |
| **memory** | 메모리/컨텍스트 관리 | ~10개 | ✅ 필수 |
| **sequential-thinking** | 순차 사고 처리 | ~15개 | ✅ 필수 |

**총 도구 수**: ~115개 (권장 80개 초과하지만 MAIC 프로젝트 필수)

## 🎯 **설정 파일 구조**

### **프로젝트 설정**
- **위치**: `.cursor/config.json`
- **용도**: 프로젝트별 MCP 서버 설정
- **우선순위**: 최우선

### **전역 설정**
- **위치**: `AppData/Roaming/Cursor/User/mcp.json`
- **용도**: Cursor 전역 MCP 설정
- **동기화**: 프로젝트 설정과 동일하게 유지

## ⚠️ **중요 규칙**

### **1. 설정 파일 관리**
- **config.json만 사용**: mcp.json 생성 금지
- **동기화 필수**: 두 설정 파일이 항상 동일해야 함
- **백업 유지**: 변경 전 항상 백업

### **2. 서버 추가/제거**
- **신규 서버 추가**: config.json에만 추가 후 동기화
- **서버 제거**: config.json에서 제거 후 동기화
- **환경변수**: 민감한 정보는 환경변수로 관리

### **3. 문제 해결**
- **중복 서버**: 두 설정 파일 동기화 확인
- **활성화 실패**: Cursor 완전 재시작
- **도구 수 초과**: 불필요한 서버 제거

## 🔧 **동기화 스크립트**

### **자동 동기화 (start_work.py)**
```python
# 프로젝트 설정을 전역 설정으로 복사
copy .cursor\config.json "C:\Users\daeha.DEAN-DESKTOP\AppData\Roaming\Cursor\User\mcp.json"
```

### **수동 동기화**
```bash
# Windows
copy .cursor\config.json "%APPDATA%\Cursor\User\mcp.json"

# 또는 PowerShell
Copy-Item .cursor\config.json "$env:APPDATA\Cursor\User\mcp.json"
```

## 📊 **모니터링**

### **정상 상태 확인**
- [ ] MCP 서버 6개 모두 enabled
- [ ] 중복 서버 없음
- [ ] 도구 수 ~115개
- [ ] Cursor 재시작 후 정상 작동

### **문제 발생 시**
1. **설정 파일 동기화** 확인
2. **Cursor 완전 재시작**
3. **불필요한 서버 제거**
4. **환경변수 확인**

## 🚨 **금지 사항**

- ❌ mcp.json 파일 생성
- ❌ 두 설정 파일 내용 불일치
- ❌ 불필요한 MCP 서버 추가
- ❌ 민감한 정보 하드코딩

## 📝 **변경 이력**

- **2025-01-XX**: 초기 MCP 설정 구성
- **2025-01-XX**: 중복 서버 문제 해결
- **2025-01-XX**: 설정 파일 구조 정리





