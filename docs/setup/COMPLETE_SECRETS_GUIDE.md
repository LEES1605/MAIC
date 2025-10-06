# MAIC Secrets 완전 가이드

> **로컬 개발부터 온라인 배포까지 모든 Secrets 설정 방법**

## 🎯 개요

MAIC 프로젝트는 로컬 개발과 온라인 배포에서 다른 방식으로 secrets를 관리합니다. 이 가이드는 모든 환경에서 올바른 설정을 도와드립니다.

## 📋 목차

1. [로컬 개발 설정](#-로컬-개발-설정)
2. [온라인 배포 설정](#-온라인-배포-설정)
3. [문제 해결](#-문제-해결)
4. [보안 모범 사례](#-보안-모범-사례)

---

## 🏠 로컬 개발 설정

### 1. 자동 설정 (권장)

```bash
python tools/start_work.py
```

실행하면 `.streamlit/secrets.toml` 파일이 자동으로 생성됩니다.

### 2. 수동 설정

`.streamlit/secrets.toml` 파일을 직접 편집:

```toml
# GitHub 설정 (자동 복원용)
GITHUB_REPO = "LEES1605/MAIC"
GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"

# AI API 설정
GEMINI_API_KEY = "AIzaSyxxxxxxxxxxxxxxxxxxxx"

# Supabase 설정 (선택사항)
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# 관리자 설정
ADMIN_PASSWORD = "your_secure_password_here"
```

### 3. 환경 변수 설정 (대안)

`.env` 파일 생성:

```bash
# env.example을 복사하여 .env 생성
cp env.example .env
```

`.env` 파일 편집:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GITHUB_TOKEN=your_github_token_here
ADMIN_PASSWORD=your_admin_password_here
```

---

## 🌐 온라인 배포 설정

### Streamlit Cloud 설정

#### 1단계: Streamlit Cloud 대시보드 접속
1. https://share.streamlit.io/ 접속
2. 로그인 후 해당 앱 선택
3. **"Settings"** → **"Secrets"** 클릭

#### 2단계: Secrets 추가
다음 내용을 secrets에 추가:

```toml
# GitHub 설정 (필수 - 자동 복원용)
GITHUB_REPO = "LEES1605/MAIC"
GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"

# AI API 설정 (필수)
GEMINI_API_KEY = "AIzaSyxxxxxxxxxxxxxxxxxxxx"

# Supabase 설정 (선택사항)
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# 관리자 설정 (필수)
ADMIN_PASSWORD = "your_secure_password_here"
```

#### 3단계: 앱 재배포
Secrets 설정 후 앱을 재배포하면 자동 복원이 정상 작동합니다.

### GitHub Actions 설정

`.github/workflows/` 파일에서 secrets 사용:

```yaml
env:
  GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
  GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## 🔧 문제 해결

### 자주 발생하는 문제들

#### 1. 자동 복원 실패
**증상**: 온라인에서 "복원필요" 상태가 계속 표시됨

**원인**: `GITHUB_TOKEN`이 설정되지 않음

**해결책**:
1. Streamlit Cloud Secrets에 `GITHUB_TOKEN` 추가
2. 앱 재배포
3. 관리자 모드에서 수동 복원 시도

#### 2. API 키 오류
**증상**: "API key not found" 에러

**원인**: API 키가 올바르게 설정되지 않음

**해결책**:
1. API 키 형식 확인 (공백, 따옴표 등)
2. API 키 권한 확인
3. 환경 변수 이름 확인

#### 3. 관리자 로그인 실패
**증상**: 관리자 비밀번호 입력창이 나타나지 않음

**원인**: `ADMIN_PASSWORD`가 설정되지 않음

**해결책**:
1. Secrets에 `ADMIN_PASSWORD` 추가
2. 앱 재시작
3. 브라우저 캐시 삭제

### 디버깅 방법

#### 로컬 디버깅
```bash
# 환경 변수 확인
python -c "import os; print('GEMINI_API_KEY:', 'SET' if os.getenv('GEMINI_API_KEY') else 'NOT SET')"

# Streamlit secrets 확인
python -c "import streamlit as st; print('Secrets loaded:', bool(st.secrets))"
```

#### 온라인 디버깅
1. Streamlit Cloud 로그 확인
2. 관리자 모드에서 시스템 상태 확인
3. GitHub Actions 로그 확인

---

## 🔒 보안 모범 사례

### 1. API 키 관리
- ✅ **절대 코드에 하드코딩하지 마세요**
- ✅ **환경 변수나 secrets 사용**
- ✅ **정기적으로 API 키 로테이션**
- ✅ **최소 권한 원칙 적용**

### 2. 비밀번호 관리
- ✅ **강력한 비밀번호 사용**
- ✅ **정기적으로 비밀번호 변경**
- ✅ **비밀번호 공유 금지**

### 3. GitHub 토큰 관리
- ✅ **Personal Access Token 사용**
- ✅ **필요한 권한만 부여**
- ✅ **토큰 만료일 설정**
- ✅ **토큰 사용 내역 모니터링**

### 4. 파일 보안
- ✅ **`.env` 파일을 `.gitignore`에 추가**
- ✅ **`secrets.toml` 파일을 Git에 커밋하지 마세요**
- ✅ **민감한 정보가 포함된 파일 삭제**

---

## 📚 관련 문서

- [개발 환경 설정](DEV_SETUP.md)
- [자동 설정 가이드](../guides/COMPLETE_AUTO_SETUP_GUIDE.md)
- [문제 해결 가이드](../guides/TESTING_GUIDE.md)
- [보안 체크리스트](../guides/SECURITY_CHECKLIST.md)

---

## 🆘 지원

문제가 지속되면:
1. [개발 역사](../DEVELOPMENT_HISTORY.md)에서 유사한 문제 확인
2. [GitHub Issues](https://github.com/LEES1605/MAIC/issues)에 문제 보고
3. [작업 세션 로그](../process/WORK_SESSION_LOG.md) 확인

---

*이 가이드는 MAIC 프로젝트의 모든 환경에서 올바른 secrets 설정을 도와드립니다.*
