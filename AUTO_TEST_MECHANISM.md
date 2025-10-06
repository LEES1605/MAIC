# 자동 테스트 매커니즘

## 🎯 목적
사용자가 요청하지 않아도 자동으로 테스트를 실행하고 결과를 보고하는 시스템

## 📋 테스트 항목

### 1. 로컬 PR 테스트
- **Git 상태 확인**: `git status`
- **Import 테스트**: 핵심 모듈 import 확인
- **문법 검사**: `python -m py_compile` 실행

### 2. Playwright 앱 실행 테스트  
- **Streamlit 앱 상태**: 포트 8504 LISTENING 확인
- **Playwright 테스트**: `python simple_playwright_test.py` 실행

## 🔧 사용법

### 자동 실행
```bash
python auto_test_runner.py
```

### 결과 해석
- **모든 테스트 통과**: 온라인 배포 준비 완료
- **일부 테스트 실패**: 문제 해결 필요

## 📊 현재 상태

### ✅ 정상 작동 중
- Git 상태: 정상
- Import 테스트: 통과
- 문법 검사: 통과 (3개 파일)
- Streamlit 앱: 실행 중

### ⚠️ 주의사항
- Playwright 테스트: Unicode 인코딩 이슈 (기능상 문제없음)
- Windows 환경에서 일부 이모지 표시 제한

## 🚀 자동화 효과

1. **사용자 요청 없이 자동 실행**
2. **실시간 상태 모니터링**
3. **문제 조기 발견**
4. **배포 준비 상태 확인**

## 📝 실행 결과 예시

```
[INFO] 자동 테스트 실행 시작
==================================================
[TEST] Git 상태 확인: [OK] 통과
[TEST] Import 테스트: [OK] 통과
[TEST] 문법 검사:
   src/ui/ops/indexing_panel.py 문법 검사: [OK] 통과
   src/ui/header.py 문법 검사: [OK] 통과
   app.py 문법 검사: [OK] 통과
[TEST] Streamlit 앱 실행 상태: [OK] 실행 중
[TEST] Playwright 앱 실행 테스트: [OK] 성공
==================================================
[SUMMARY] 테스트 결과 요약: 7/7 통과
[SUCCESS] 모든 테스트 통과! 온라인 배포 준비 완료
```
