# 🌐 온라인 Streamlit Cloud Secrets 설정 가이드

## 🚨 문제 상황
- **로컬**: 자동 복원이 정상 작동 ✅
- **온라인**: 자동 복원이 실패 ❌

## 🔍 원인 분석
온라인 Streamlit Cloud에 `GITHUB_TOKEN`이 설정되지 않았기 때문입니다.

## 📋 해결 방법

### 1단계: Streamlit Cloud 대시보드 접속
1. https://share.streamlit.io/ 접속
2. 로그인 후 해당 앱 선택
3. **"Settings"** → **"Secrets"** 클릭

### 2단계: GitHub 토큰 추가
다음 내용을 secrets에 추가하세요:

```toml
# GitHub 설정 (자동 복원용)
GITHUB_REPO = "LEES1605/MAIC"
GITHUB_TOKEN = "your-github-token-here"

# 기타 필수 설정
MAIC_DEBUG = false
MAIC_LOCAL_DEV = false
```

### 3단계: 앱 재시작
- **"Reboot app"** 버튼 클릭
- 또는 자동으로 재시작됨

## ✅ 확인 방법
1. 앱 접속 후 **관리자 모드** 진입
2. **인덱스 상태** 확인
3. **"복원필요"** → **"정상"**으로 변경되면 성공

## 🔧 추가 설정 (선택사항)
필요한 경우 다음도 추가할 수 있습니다:

```toml
# LLM 설정
GEMINI_API_KEY = "your-gemini-api-key-here"
OPENAI_API_KEY = "your-openai-api-key-here"

# Google Drive 설정
GDRIVE_PREPARED_FOLDER_ID = "1bltOvqYsifPtmcx-epwJTq-hYAklNp2j"
```

## ⚠️ 보안 주의사항
- GitHub 토큰은 **읽기 전용** 권한만 부여하세요
- 토큰이 노출되면 즉시 재생성하세요
- 운영 환경에서는 더 강한 비밀번호를 사용하세요

## 🎯 예상 결과
설정 완료 후:
- ✅ 자동 복원이 정상 작동
- ✅ 인덱스 상태가 "정상"으로 표시
- ✅ RAG 검색이 온라인에서도 작동
