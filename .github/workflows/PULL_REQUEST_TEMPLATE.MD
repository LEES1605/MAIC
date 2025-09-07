<!-- ================== [02] PULL_REQUEST_TEMPLATE.md — START ================== -->

## 변경 요약
- 무엇을 왜 바꾸는지, 동작 변화는 있는지 간단히 설명

## 체크리스트
- [ ] 로컬 금지 / **Actions 전용**에 맞게 테스트·검증 설계
- [ ] ruff / mypy / pytest 통과
- [ ] (패치 기반 교체 시) 아래 **PATCH-GUARD** 정보 기입

<!--
PATCH-GUARD
files:
  - path: src/ui/header.py
    sha256: "<기준 브랜치 파일의 SHA256>"
    anchors:
      - "def _ready_level"
      - "brand-wrap"
  # 여러 파일이면 항목을 추가하세요
-->

### 참고
- `.ci/patch-guard.yml` 파일을 PR에 포함해도 됩니다(위 블록 대신).
- SHA256 계산이 필요하면 **“SHA Helper”** 워크플로를 사용하세요.

<!-- ================== [02] PULL_REQUEST_TEMPLATE.md — END ==================== -->
