# MAIC Secrets 설정 가이드

## 🎯 개요
MAIC 프로젝트는 로컬 개발과 온라인 배포에서 다른 방식으로 secrets를 관리합니다.

## 📁 로컬 개발 (Local Development)

### 1. 자동 설정
```bash
python start_work.py
```
실행하면 `.streamlit/secrets.toml` 파일이 자동으로 생성됩니다.

### 2. 수동 설정
`.streamlit/secrets.toml` 파일을 직접 편집:
```toml
# GitHub 설정 (자동 복원용)
GITHUB_REPO = "daeha-DEAN-DESKTOP/LOCAL_MAIC"
GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"

# Supabase 설정 (선택사항)
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "your-service-role-key"

# OpenAI 설정 (선택사항)
OPENAI_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxx"

# 기타 설정
MAIC_DEBUG = true
MAIC_LOCAL_DEV = true
```

## ☁️ 온라인 배포 (Streamlit Cloud)

### 1. Streamlit Cloud Secrets 설정
1. Streamlit Cloud 대시보드에서 앱 선택
2. "Settings" → "Secrets" 클릭
3. 다음 내용 추가:

```toml
GITHUB_REPO = "daeha-DEAN-DESKTOP/LOCAL_MAIC"
GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "your-service-role-key"
OPENAI_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxx"
MAIC_DEBUG = false
MAIC_LOCAL_DEV = false
```

## 🔧 토큰 생성 방법

### GitHub Token
1. GitHub → Settings → Developer settings → Personal access tokens
2. "Generate new token" 클릭
3. 권한 선택: `repo` (전체 저장소 접근)
4. 토큰 복사하여 설정

### Supabase Keys
1. Supabase 프로젝트 → Settings → API
2. `URL`과 `service_role` 키 복사

### OpenAI API Key
1. OpenAI → API Keys
2. "Create new secret key" 클릭
3. 키 복사하여 설정

## 🚀 자동 복원 활성화

### 로컬에서 테스트
```bash
# 1. secrets 파일 설정
# 2. Streamlit 앱 실행
streamlit run app.py

# 3. 관리자 모드에서 "복원" 버튼 클릭
```

### 온라인에서 자동 복원
- GitHub Token이 설정되면 앱 시작 시 자동으로 최신 인덱스 복원
- 관리자 모드에서 "Release에서 최신 인덱스 복원" 버튼 사용 가능

## 🔒 보안 주의사항

- **로컬**: `.streamlit/secrets.toml`은 `.gitignore`에 포함되어 Git에 업로드되지 않음
- **온라인**: Streamlit Cloud의 secrets는 암호화되어 안전하게 저장됨
- **토큰 관리**: 토큰은 정기적으로 갱신하고, 사용하지 않는 토큰은 삭제

## 🐛 문제 해결

### 자동 복원이 안될 때
1. GitHub Token이 올바르게 설정되었는지 확인
2. Token 권한이 `repo`로 설정되었는지 확인
3. `GITHUB_REPO`가 올바른 저장소를 가리키는지 확인

### 로컬에서 secrets가 안 읽힐 때
1. `.streamlit/secrets.toml` 파일이 존재하는지 확인
2. 파일 형식이 올바른지 확인 (TOML 형식)
3. Streamlit 앱을 재시작

## 📞 지원

문제가 발생하면 다음을 확인하세요:
- [GitHub Issues](https://github.com/daeha-DEAN-DESKTOP/LOCAL_MAIC/issues)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [Supabase Documentation](https://supabase.com/docs)
