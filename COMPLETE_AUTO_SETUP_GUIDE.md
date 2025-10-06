# 완전 자동화된 새 컴퓨터 설정 가이드

## 🎯 목적
새로운 컴퓨터에 Cursor를 설치하고 `python start_work_auto.py`만 실행하면 모든 것이 자동으로 설정되도록 구현

## 📋 사전 요구사항

### 필수 소프트웨어
1. **Python 3.8 이상**
   - 다운로드: https://python.org/
   - 설치 시 "Add to PATH" 옵션 체크

2. **Git**
   - 다운로드: https://git-scm.com/
   - 기본 설정으로 설치

3. **Cursor**
   - 다운로드: https://cursor.sh/
   - 기본 설정으로 설치

### 권장 소프트웨어
4. **Node.js** (선택사항)
   - 다운로드: https://nodejs.org/
   - MCP 서버 일부 기능에 필요

## 🚀 완전 자동화 설정 과정

### 1단계: 프로젝트 다운로드
```bash
# Git으로 프로젝트 클론
git clone https://github.com/daeha-DEAN-DESKTOP/LOCAL_MAIC.git
cd LOCAL_MAIC
```

### 2단계: 자동 설정 실행
```bash
# 완전 자동화 스크립트 실행
python start_work_auto.py
```

### 3단계: 완료!
- 모든 설정이 자동으로 완료됨
- Cursor가 자동으로 재시작됨
- MAIC 프로젝트 사용 준비 완료

## 🔧 자동화되는 설정들

### 1. 필수 요구사항 확인
- Python 버전 확인
- Git 설치 확인
- Node.js 설치 확인 (선택사항)
- Cursor 설치 확인

### 2. Git 동기화
- 최신 코드 자동 가져오기
- 로컬 변경사항 처리

### 3. 환경 설정
- `.streamlit/secrets.toml` 파일 자동 생성
- GitHub 토큰 설정 가이드
- 환경 변수 자동 설정

### 4. Cursor 규칙 동기화
- 프로젝트 규칙 파일들 자동 복사
- Cursor 설정 디렉토리 생성

### 5. MCP 설정 동기화
- MCP 서버 설정 자동 복사
- Cursor MCP 설정 파일 생성
- MCP 서버 목록 표시

### 6. NPX 패키지 캐싱
- 필요한 MCP 서버 패키지들 자동 캐싱
- 네트워크 지연 방지

### 7. Cursor 재시작
- 기존 Cursor 프로세스 자동 종료
- 새로운 Cursor 창 자동 실행
- 프로젝트 폴더 자동 열기

## 📊 자동 테스트 실행

설정 완료 후 자동으로 다음 테스트들이 실행됩니다:

1. **Git 상태 확인**: ✅ 통과
2. **Import 테스트**: ✅ 통과
3. **문법 검사**: ✅ 통과 (3개 파일)
4. **Streamlit 앱 실행 상태**: ✅ 실행 중
5. **Playwright 테스트**: ✅ 성공

## 🎉 완료 후 상태

### ✅ 자동으로 설정되는 것들
- Git 저장소 동기화
- 환경 변수 설정
- Cursor 규칙 동기화
- MCP 설정 동기화
- NPX 패키지 캐싱
- Cursor 재시작

### 📁 생성되는 파일들
- `.streamlit/secrets.toml`: 로컬 개발용 설정
- `.cursor/`: Cursor 설정 파일들
- `AppData/Roaming/Cursor/User/mcp.json`: MCP 설정

### 🔧 설정되는 MCP 서버들
- `GitKraken`: Git 통합
- `playwright`: E2E 테스트
- `supabase`: 데이터베이스
- `filesystem`: 파일 시스템
- `memory`: 메모리 관리
- `sequential-thinking`: 순차적 사고

## 🚨 문제 해결

### Git 오류
```bash
# Git 사용자 정보 설정
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### Python 모듈 오류
```bash
# 필요한 모듈 설치
pip install psutil streamlit playwright
```

### Cursor 재시작 실패
- 수동으로 Cursor 재시작
- 프로젝트 폴더를 Cursor로 열기

## 📝 사용법

### 일상적인 사용
```bash
# 작업 시작
python start_work_auto.py

# 작업 완료 (선택사항)
python end_work.py
```

### 새로운 컴퓨터에서
1. 필수 소프트웨어 설치 (Python, Git, Cursor)
2. 프로젝트 클론
3. `python start_work_auto.py` 실행
4. 완료!

## 🎯 핵심 장점

1. **완전 자동화**: 사용자 개입 최소화
2. **오류 방지**: 사전 요구사항 자동 확인
3. **일관성**: 모든 환경에서 동일한 설정
4. **신속성**: 몇 분 내에 완전한 개발 환경 구축
5. **안정성**: 자동 테스트로 설정 검증

## 📞 지원

문제가 발생하면:
1. 자동 테스트 결과 확인
2. 오류 메시지 분석
3. 필요한 소프트웨어 설치 확인
4. 수동 설정 가이드 참조

---

**이제 새로운 컴퓨터에서도 `python start_work_auto.py` 하나의 명령어로 모든 것이 자동으로 설정됩니다!** 🚀


