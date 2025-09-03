# ============================ [01] NIGHTLY CHECKLIST — START ============================

# Nightly 재검증 체크리스트 (초보 모드)
> 매일 새벽 도는 **Nightly Pre-Release**가 정상 동작하는지 **아주 쉬운 순서**로 확인합니다.  
> 실패하면 아래 “자주 나는 오류 & 복구” 섹션만 따라 고치면 됩니다.

---

## 1) 수동 실행으로 바로 재현해 보기
1. GitHub → **Actions** → **Nightly Pre-Release** 워크플로 선택  
2. 우측 상단 **Run workflow** 클릭 → **Run**  
3. 잡 진행이 **checks → prerelease** 순으로 흐르면 정상

> checks = Ruff → mypy (테스트 포함 시 pytest)  
> prerelease = 태그 생성/푸시 → zip/sha256 생성 → **Pre-release 발행**

---

## 2) 실행이 끝난 뒤 확인할 것들
- **태그**: 저장소 **Tags**에 `nightly-YYYYMMDD`가 **오늘 날짜**로 생성되어 있어야 합니다.  
- **Releases**: “Pre-release”가 오늘 날짜 태그로 하나 생겼는지 확인합니다.  
- **Assets(첨부)**: 아래 2개가 있어야 합니다.
  - `maic-nightly-YYYYMMDD.zip` *(혹은 워크플로에서 지정한 파일명)*
  - `maic-nightly-YYYYMMDD.zip.sha256`
- **로그**: `Publish pre-release` 스텝이 **성공(Success)** 이어야 합니다.

---

## 3) 로컬에서도 태그 확인(선택)
```bash
git fetch --tags
git tag -l "nightly-*"
# 가장 최근 태그 확인
git show --no-patch --pretty="format:%D %ci" $(git tag -l "nightly-*" | sort | tail -n 1)
