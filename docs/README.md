# MAIC Documentation

> **MAIC 프로젝트의 완전한 문서 모음**  
> 모든 가이드, 설정, 프로세스 문서를 한 곳에서 찾아보세요

## 📚 문서 구조

### 🚀 [Quick Start](README.md)
- [프로젝트 개요](../README.md)
- [빠른 시작 가이드](../README.md#-quick-start)
- [설치 및 설정](../README.md#-development)

### 📖 [가이드 문서](guides/)
- [자동 테스트 메커니즘](guides/AUTO_TEST_MECHANISM.md)
- [완전한 자동 설정 가이드](guides/COMPLETE_AUTO_SETUP_GUIDE.md)
- [Cursor 동기화 가이드](guides/CURSOR_SYNC_GUIDE.md)
- [개발 환경 설정](guides/DEV_SETUP.md)
- [Git 워크플로 가이드](guides/GIT_WORKFLOW_GUIDE.md)
- [테스트 가이드](guides/TESTING_GUIDE.md)
- [컴포넌트 가이드](guides/components.md)

### ⚙️ [설정 가이드](setup/)
- [야간 체크리스트](setup/NIGHTLY_CHECKLIST.md)
- [온라인 시크릿 설정](setup/ONLINE_SECRETS_SETUP.md)
- [자동 설정 README](setup/README_AUTO_SETUP.md)
- [시크릿 설정](setup/SECRETS_SETUP.md)

### 🔄 [프로세스 문서](process/)
- [테스트 프로세스](process/TESTING_PROCESS.md)
- [작업 세션 로그](process/WORK_SESSION_LOG.md)
- [변경 로그](process/CHANGELOG.md)
- [UI 정리 계획](process/ui_cleanup_plan.md)

### 📜 [개발 역사](DEVELOPMENT_HISTORY.md)
- [완전한 개발 과정 기록](DEVELOPMENT_HISTORY.md)
- [성공과 실패의 교훈](DEVELOPMENT_HISTORY.md#-교훈-및-모범-사례)
- [자주 반복된 실수들](DEVELOPMENT_HISTORY.md#-자주-반복된-실수들)

### 🏗️ [아키텍처 문서](_gpt/)
- [프로젝트 컨벤션](_gpt/CONVENTIONS.md)
- [마스터플랜](_gpt/MASTERPLAN_vFinal.md)
- [최적화 분석](_gpt/OPTIMIZATION_ANALYSIS_2025-10-06.md)
- [UI 통합 완료 보고서](_gpt/UI_INTEGRATION_COMPLETION_REPORT.md)

### 📋 [Pull Request](pr/)
- [앱 슬림 운영 PR](pr/PR-A1r_app_slim_ops.md)
- [레거시 정리 PR](pr/PR-L1a_legacy_sweep_app.md)

### 🗂️ [아카이브](_archive/)
- [레거시 문서들](_archive/)
- [과거 프로젝트 상태](_archive/2025-09-07_PROJECT_STATUS.md)

## 🎯 문서 사용 가이드

### 새로운 개발자라면?
1. [프로젝트 개요](../README.md) 읽기
2. [개발 환경 설정](guides/DEV_SETUP.md) 따라하기
3. [자동 설정 가이드](guides/COMPLETE_AUTO_SETUP_GUIDE.md) 실행
4. [테스트 가이드](guides/TESTING_GUIDE.md)로 테스트 실행

### 기존 개발자라면?
1. [변경 로그](process/CHANGELOG.md) 확인
2. [작업 세션 로그](process/WORK_SESSION_LOG.md) 검토
3. [야간 체크리스트](setup/NIGHTLY_CHECKLIST.md) 실행

### 문제 해결이 필요하다면?
1. [개발 역사](DEVELOPMENT_HISTORY.md)에서 유사한 문제 찾기
2. [자주 반복된 실수들](DEVELOPMENT_HISTORY.md#-자주-반복된-실수들) 확인
3. [테스트 프로세스](process/TESTING_PROCESS.md) 따라하기

## 📝 문서 작성 가이드

### 새로운 문서 작성 시
1. 적절한 폴더에 배치
2. 이 README.md에 링크 추가
3. 관련 문서들과 상호 참조 설정

### 문서 업데이트 시
1. 변경사항을 [변경 로그](process/CHANGELOG.md)에 기록
2. 관련 문서들도 함께 업데이트
3. 링크 유효성 확인

## 🔍 문서 검색

### 키워드로 찾기
- **설정**: setup/ 폴더
- **가이드**: guides/ 폴더  
- **프로세스**: process/ 폴더
- **아키텍처**: _gpt/ 폴더
- **이력**: _archive/ 폴더

### 주제별 찾기
- **환경 설정**: [DEV_SETUP.md](guides/DEV_SETUP.md), [SECRETS_SETUP.md](setup/SECRETS_SETUP.md)
- **테스트**: [TESTING_GUIDE.md](guides/TESTING_GUIDE.md), [TESTING_PROCESS.md](process/TESTING_PROCESS.md)
- **배포**: [COMPLETE_AUTO_SETUP_GUIDE.md](guides/COMPLETE_AUTO_SETUP_GUIDE.md)
- **개발**: [GIT_WORKFLOW_GUIDE.md](guides/GIT_WORKFLOW_GUIDE.md)

---

**💡 팁**: 이 문서는 MAIC 프로젝트의 모든 문서를 체계적으로 정리한 것입니다.  
문서를 찾기 어려울 때는 이 README.md를 먼저 확인해보세요!
