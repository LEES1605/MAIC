# MAIC - My AI Teacher

> **SSOT(단일 진실 원천) 기반의 AI 교육 플랫폼**

MAIC는 코드/문서/프롬프트의 **일관성**을 보장하는 AI 교육 시스템입니다.
엄격한 CI 게이트와 5-Layer Clean Architecture를 통해 **회귀를 사전에 차단**하고
**최고의 개발자 경험**을 제공합니다.

## 🚀 Quick Start

```bash
# 1. 저장소 클론
git clone https://github.com/LEES1605/MAIC.git
cd MAIC

# 2. 자동 설정 실행
python tools/start_work.py

# 3. 앱 실행
streamlit run app.py
```

## 📁 Project Structure

```
MAIC/
├── app.py                    # 메인 Streamlit 앱
├── src/                      # 5-Layer Clean Architecture
│   ├── application/          # 비즈니스 로직
│   ├── domain/              # 핵심 엔티티
│   ├── infrastructure/      # 외부 시스템
│   ├── shared/              # 공통 유틸리티
│   └── ui/                  # 사용자 인터페이스
├── docs/                    # 프로젝트 문서
│   ├── guides/              # 가이드 문서
│   ├── setup/               # 설정 가이드
│   └── process/             # 프로세스 문서
├── config/                  # 설정 파일들
├── tools/                   # 개발 도구 및 스크립트
├── tests/                   # 테스트 코드
└── assets/                  # 이미지 및 리소스
```

## 🏗️ Architecture

### 5-Layer Clean Architecture
- **Application Layer**: 비즈니스 로직 및 서비스
- **Domain Layer**: 핵심 엔티티 및 도메인 규칙
- **Infrastructure Layer**: 외부 시스템 통합
- **Shared Layer**: 공통 유틸리티 및 도구
- **UI Layer**: 사용자 인터페이스 컴포넌트

### 🎨 UI Components
- **Linear Design System**: 일관된 디자인 언어
- **Streamlit Integration**: 웹 기반 인터페이스
- **Responsive Design**: 모바일 우선 설계

## 🔧 Development

### Prerequisites
- Python 3.11+
- Streamlit
- Git

### Setup
```bash
# 의존성 설치
pip install -r config/requirements.txt

# 개발 의존성 설치
pip install -r config/requirements-dev.txt

# 자동 설정 실행
python tools/start_work.py
```

### Testing
```bash
# 전체 테스트 실행
pytest tests/

# 특정 테스트 실행
pytest tests/test_specific.py

# 커버리지 확인
pytest --cov=src tests/
```

## 📚 Documentation

- **[Setup Guide](docs/setup/)** - 초기 설정 및 환경 구성
- **[Development Guide](docs/guides/)** - 개발 가이드 및 모범 사례
- **[Process Guide](docs/process/)** - 개발 프로세스 및 워크플로

## 🚀 Features

- **🤖 AI-Powered Learning**: Gemini API 기반 지능형 학습 시스템
- **📚 RAG (Retrieval-Augmented Generation)**: 지식 베이스 기반 정확한 답변
- **🎨 Linear Design System**: 일관되고 아름다운 UI/UX
- **🔒 Security First**: 입력 검증, XSS 방지, 보안 강화
- **⚡ Performance Optimized**: 캐싱, 스트리밍, 최적화된 성능
- **🧪 Comprehensive Testing**: 단위 테스트, E2E 테스트, 자동화된 검증

## 🔄 CI/CD Pipeline

- **Code Quality**: Ruff, MyPy, Pytest
- **Security**: pip-audit, gitleaks
- **Coverage**: 자동 커버리지 추적
- **Documentation**: 자동 문서 생성

## 📄 License

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📞 Support

문제가 있으시면 [Issues](https://github.com/LEES1605/MAIC/issues)에 등록해 주세요.

---

**MAIC** - *Making AI Education Intelligent and Consistent* 🚀
