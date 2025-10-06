# 🚀 MAIC 프로젝트 완전 자동화 설정 가이드

## 📋 **어디서든 새로 Cursor 설치 후 1분 내 완전 설정**

### **🎯 목표**
- **새 컴퓨터**에서 Cursor 설치 후
- **`python start_work.py`** 한 번만 실행
- **모든 설정 자동 완료** (MCP, 환경변수, Cursor 재시작)

---

## 🛠️ **사전 요구사항**

### **1. 필수 소프트웨어**
- **Python 3.8+** (자동 설치됨)
- **Node.js & npm** (MCP 서버용)
- **Git** (코드 동기화용)
- **Cursor** (IDE)

### **2. 자동 설치되는 것들**
- `psutil` (프로세스 관리)
- NPX 패키지들 (MCP 서버들)
- 환경변수 설정
- Cursor 설정 파일들

---

## 🚀 **완전 자동화 실행 방법**

### **1단계: 프로젝트 클론**
```bash
git clone https://github.com/LEES1605/MAIC.git
cd MAIC
```

### **2단계: 자동 설정 실행**
```bash
python start_work.py
```

**끝!** 🎉

---

## 🔧 **자동으로 처리되는 작업들**

### **✅ Git 동기화**
- 최신 코드 자동 pull
- 충돌 해결 자동화
- 백업 생성

### **✅ MCP 서버 설정**
- **6개 필수 서버** 자동 설치:
  - `GitKraken` - Git 관리
  - `playwright` - E2E 테스트  
  - `supabase` - 데이터베이스
  - `filesystem` - 파일 시스템
  - `memory` - 메모리 관리
  - `sequential-thinking` - 순차 사고

### **✅ Cursor 설정**
- 프로젝트 설정 → 전역 설정 자동 복사
- Linear 컴포넌트 규칙 자동 적용
- `.cursorrules` 파일 생성

### **✅ 환경 설정**
- NPX 패키지 자동 캐시
- 환경변수 자동 설정
- Node.js 환경 확인

### **✅ Cursor 자동 재시작**
- 기존 Cursor 프로세스 종료
- 새 Cursor 창 자동 시작
- 모든 MCP 서버 활성화

### **✅ 설정 검증**
- 모든 설정 자동 검증
- 문제점 자동 감지
- 성공/실패 상태 보고

---

## 📊 **설정 완료 후 상태**

### **🎯 MCP 서버 (6개)**
- ✅ GitKraken (Git 관리)
- ✅ playwright (E2E 테스트)
- ✅ supabase (데이터베이스)
- ✅ filesystem (파일 시스템)
- ✅ memory (메모리 관리)
- ✅ sequential-thinking (순차 사고)

### **🎯 도구 수**
- **현재**: ~48개 도구 (권장 80개 이하)
- **상태**: ✅ 최적화 완료

### **🎯 Cursor 설정**
- ✅ Linear 컴포넌트 규칙 적용
- ✅ MCP 서버 모두 활성화
- ✅ 프로젝트별 설정 동기화

---

## 🔍 **문제 해결**

### **자주 발생하는 문제들**

#### **1. Git 충돌**
```bash
# 자동으로 해결됨
git stash
git pull origin main
git stash pop
```

#### **2. NPX 패키지 설치 실패**
```bash
# Node.js 설치 확인
node --version
npm --version

# 수동 설치
npm install -g @modelcontextprotocol/server-filesystem
```

#### **3. Cursor 재시작 실패**
```bash
# 수동 재시작
# Cursor를 완전히 종료 후 다시 시작
```

#### **4. MCP 서버 비활성화**
```bash
# 설정 검증
python scripts/auto_setup_verification.py

# 수동 동기화
python start_work.py
```

---

## 📝 **수동 검증 방법**

### **설정 상태 확인**
```bash
python scripts/auto_setup_verification.py
```

### **MCP 설정 확인**
```bash
python scripts/verify_mcp_config.py
```

### **Git 상태 확인**
```bash
git status
git log --oneline -5
```

---

## 🎉 **성공 확인**

### **✅ 모든 것이 정상이면:**
- Cursor에서 MCP 서버 6개 모두 활성화
- 도구 수 48개 (권장 범위 내)
- Linear 컴포넌트 규칙 적용
- 모든 환경변수 설정됨

### **⚠️ 문제가 있으면:**
- 검증 스크립트가 자동으로 문제점 보고
- 수동으로 문제 해결 후 재실행

---

## 🚀 **다음 단계**

설정 완료 후:
1. **Cursor 재시작** (자동으로 됨)
2. **MCP 서버 확인** (6개 모두 활성화)
3. **개발 시작** 🎯

**이제 어디서든 `python start_work.py` 한 번만 실행하면 완전한 개발 환경이 구축됩니다!** 🎉


