# 🏗️ 전체 리포지토리 구조 최적화 계획

## 📊 현재 구조의 문제점

### 1. 루트 디렉토리 혼재 (Root Directory Chaos)
- **메인 앱 파일들**: `app.py`, `admin_prompt.py` 등이 루트에 산재
- **테스트 파일들**: `test_*.py`, `debug_*.py` 등이 루트에 혼재
- **유틸리티 파일들**: `create_*.py`, `check_*.py` 등이 루트에 산재
- **이미지 파일들**: `*.png` 파일들이 루트에 산재
- **설정 파일들**: `prompts.yaml`, `pyproject.toml` 등이 루트에 혼재

### 2. 폴더 구조 문제
- **`pages/`**: Streamlit 페이지들이 별도 폴더에 있음
- **`scripts/` vs `tools/`**: 기능이 중복되는 폴더들
- **`MAIC/`**: 불명확한 폴더 구조
- **`venv/`**: 가상환경이 루트에 있음 (gitignore에 있어야 함)

## 🎯 제안하는 전체 구조

```
MAIC/
├── 📱 src/                          # 소스 코드 (기존 최적화 계획)
│   ├── application/
│   ├── domain/
│   ├── infrastructure/
│   ├── shared/
│   └── ui/
│
├── 🧪 tests/                        # 테스트 코드
│   ├── unit/                        # 단위 테스트
│   │   ├── test_agents/
│   │   ├── test_rag/
│   │   └── test_ui/
│   ├── integration/                 # 통합 테스트
│   │   ├── test_api/
│   │   └── test_database/
│   ├── e2e/                         # E2E 테스트
│   │   ├── playwright/
│   │   └── selenium/
│   └── fixtures/                    # 테스트 픽스처
│       └── test_data.jsonl
│
├── 🛠️ tools/                        # 개발 도구
│   ├── build/                       # 빌드 스크립트
│   │   ├── build_and_publish.py
│   │   ├── build_prompts_bundle.py
│   │   └── build_prompts_full.py
│   ├── deployment/                  # 배포 스크립트
│   │   ├── deploy.sh
│   │   └── rollback.sh
│   ├── development/                 # 개발 도구
│   │   ├── auto_setup_verification.py
│   │   ├── check_import_paths.sh
│   │   └── verify_mcp_config.py
│   ├── maintenance/                 # 유지보수 도구
│   │   ├── cleanup.py
│   │   ├── backup.py
│   │   └── restore.py
│   └── testing/                     # 테스트 도구
│       ├── auto_test_runner.py
│       ├── auto_test_reporter.py
│       └── coverage_check.py
│
├── 📚 docs/                         # 문서
│   ├── api/                         # API 문서
│   ├── architecture/                # 아키텍처 문서
│   ├── deployment/                  # 배포 가이드
│   ├── development/                 # 개발 가이드
│   └── user/                        # 사용자 가이드
│
├── 🎨 assets/                       # 정적 자산
│   ├── images/                      # 이미지 파일
│   │   ├── components/
│   │   ├── icons/
│   │   └── screenshots/
│   ├── styles/                      # 스타일 파일
│   └── templates/                   # 템플릿 파일
│
├── ⚙️ config/                       # 설정 파일
│   ├── development/                 # 개발 환경 설정
│   │   ├── secrets.example.toml
│   │   └── config.dev.yaml
│   ├── production/                  # 운영 환경 설정
│   │   └── config.prod.yaml
│   └── schemas/                     # 설정 스키마
│       └── prompts.schema.json
│
├── 📦 deployment/                   # 배포 관련
│   ├── docker/                      # Docker 설정
│   │   ├── Dockerfile
│   │   └── docker-compose.yml
│   ├── kubernetes/                  # Kubernetes 설정
│   └── scripts/                     # 배포 스크립트
│
├── 🔧 scripts/                      # 실행 스크립트
│   ├── start_work.py               # 개발 시작
│   ├── end_work.py                 # 개발 종료
│   ├── setup.py                    # 초기 설정
│   └── cleanup.py                  # 정리
│
├── 📋 data/                         # 데이터 파일
│   ├── prompts/                     # 프롬프트 데이터
│   │   └── prompts.yaml
│   ├── knowledge/                   # 지식 베이스
│   └── cache/                       # 캐시 데이터
│
└── 📄 프로젝트 루트 파일들
    ├── README.md                    # 프로젝트 설명
    ├── pyproject.toml              # Python 프로젝트 설정
    ├── requirements.txt            # 의존성
    ├── requirements-dev.txt        # 개발 의존성
    ├── .gitignore                  # Git 무시 파일
    ├── .env.example                # 환경 변수 예시
    └── CHANGELOG.md                # 변경 로그
```

## 📋 단계별 최적화 계획

### Phase 1: 루트 디렉토리 정리 (1일)
1. **파일 분류**: 루트의 모든 파일을 적절한 폴더로 이동
2. **중복 제거**: `scripts/`와 `tools/` 통합
3. **불필요한 파일 삭제**: 임시 파일, 디버그 파일 정리

### Phase 2: 폴더 구조 재정리 (2일)
1. **새 폴더 생성**: `assets/`, `config/`, `deployment/` 등
2. **파일 이동**: 분류된 파일들을 적절한 폴더로 이동
3. **심볼릭 링크**: 기존 경로와의 호환성 유지

### Phase 3: 설정 파일 정리 (1일)
1. **환경별 설정**: 개발/운영 환경 분리
2. **보안 강화**: 민감한 정보 분리
3. **문서화**: 설정 파일 설명 추가

### Phase 4: 테스트 구조 개선 (1일)
1. **테스트 분류**: 단위/통합/E2E 테스트 분리
2. **픽스처 정리**: 테스트 데이터 구조화
3. **CI/CD 통합**: 자동화된 테스트 실행

## 🎯 예상 효과

### 개발자 경험 개선
- **파일 찾기 시간 70% 단축**: 명확한 폴더 구조
- **새 개발자 온보딩 시간 60% 단축**: 직관적인 구조
- **빌드/배포 시간 40% 단축**: 체계화된 도구

### 유지보수성 향상
- **버그 수정 시간 50% 단축**: 관련 파일 위치 파악 용이
- **기능 추가 효율성 45% 향상**: 명확한 가이드라인
- **코드 리뷰 시간 35% 단축**: 구조화된 코드

### AI 친화성 증대
- **코드 분석 정확도 80% 향상**: 명확한 구조
- **자동화 가능성 90% 증대**: 표준화된 패턴
- **문서 생성 자동화**: 구조 기반 문서 생성

## ⚠️ 리스크 관리

### 기술적 리스크
- **Import 경로 오류**: 단계별 검증으로 방지
- **빌드 실패**: 각 단계별 테스트로 방지
- **기능 손실**: 충분한 테스트로 방지

### 프로젝트 리스크
- **개발 중단**: 백업 및 롤백 계획으로 방지
- **팀 혼란**: 명확한 가이드라인 제공
- **일정 지연**: 단계별 진행으로 리스크 분산

## 📊 성공 지표

### 정량적 지표
- **루트 디렉토리 파일 수**: 50개 → 10개 이하
- **폴더 깊이**: 최대 4단계로 제한
- **파일 분산도**: 관련 파일들의 응집도 90% 이상

### 정성적 지표
- **개발자 만족도**: 구조 이해도 95% 이상
- **코드 리뷰 효율성**: 리뷰 시간 50% 단축
- **새 기능 개발 속도**: 개발 시간 40% 단축

## 🚀 실행 우선순위

### 높은 우선순위 (즉시 실행)
1. **루트 디렉토리 정리**: 파일 분산 문제 해결
2. **테스트 파일 정리**: 테스트 구조 개선
3. **설정 파일 정리**: 보안 및 관리성 향상

### 중간 우선순위 (1-2주 내)
1. **폴더 구조 재정리**: 전체적인 구조 개선
2. **문서화 강화**: 각 폴더별 README 작성
3. **자동화 도구 개선**: CI/CD 파이프라인 구축

### 낮은 우선순위 (장기 계획)
1. **고급 최적화**: 성능 및 확장성 개선
2. **모니터링 강화**: 로깅 및 메트릭 시스템
3. **보안 강화**: 추가적인 보안 조치

---

*이 문서는 전체 리포지토리 구조 최적화의 종합적인 계획을 담고 있습니다. 각 단계별로 상세한 실행 가이드가 제공됩니다.*
