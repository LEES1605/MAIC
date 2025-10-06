# Git 기반 연속성 있는 개발 가이드

## 🚀 자동화 스크립트 사용법

### **작업 시작할 때**
```bash
# 방법 1: Python 스크립트
python start_work.py

# 방법 2: 배치 파일 (Windows)
start_work.bat
```

### **작업 종료할 때**
```bash
# 방법 1: Python 스크립트
python end_work.py

# 방법 2: 배치 파일 (Windows)
end_work.bat
```

## 📋 자동화 스크립트 기능

### **start_work.py (작업 시작)**
- ✅ 최신 코드 자동 가져오기 (`git pull origin main`)
- ✅ 현재 상태 확인 (`git status`)
- ✅ 최근 작업 로그 표시
- ✅ 오늘 날짜 표시

### **end_work.py (작업 종료)**
- ✅ 변경사항 자동 추가 (`git add .`)
- ✅ 작업 내용 입력 받기
- ✅ 자동 커밋 (`git commit`)
- ✅ 원격 저장소 업로드 (`git push origin main`)
- ✅ 작업 로그 자동 업데이트

## 🎯 사용 시나리오

### **집에서 작업하는 경우**
1. **아침에**: `python start_work.py` 실행
2. **작업 후**: `python end_work.py` 실행
3. **작업 내용 입력**: "관리자 UI 수정 완료"

### **학원에서 작업하는 경우**
1. **학원 도착 후**: `python start_work.py` 실행
2. **작업 후**: `python end_work.py` 실행
3. **작업 내용 입력**: "테스트 코드 추가"

## 💡 장점

- ✅ **자동화**: Git 명령어를 기억할 필요 없음
- ✅ **안전성**: 각 단계별 확인 및 오류 처리
- ✅ **추적성**: 작업 로그 자동 업데이트
- ✅ **연속성**: 집과 학원에서 동일한 워크플로우

## 🔧 수동 Git 명령어 (참고용)

### **작업 시작**
```bash
git pull origin main
git status
```

### **작업 종료**
```bash
git add .
git commit -m "작업 완료: 구체적인 내용"
git push origin main
```

## 📝 작업 로그 파일

`WORK_SESSION_LOG.md` 파일이 자동으로 업데이트됩니다:
- 날짜별 작업 기록
- 완료된 작업 체크
- 다음 작업 계획

## 🚨 주의사항

- 스크립트 실행 전에 Git 저장소가 올바르게 설정되어 있는지 확인
- 네트워크 연결 상태 확인
- 작업 내용은 간단명료하게 입력
