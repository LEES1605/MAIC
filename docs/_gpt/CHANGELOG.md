# CHANGELOG

## 2025-09-08
### Changed
- **출처 라벨 표준화**: `[문법책]` → **`[문법서적]`** (칩 표기 통일).
  - 과거 라벨은 에일리어스로 흡수.
- **관리자 세션 키 통일**: `admin_mode` 단일 키.
  - 하위호환: 세션의 `is_admin` 감지 시 1회성 승격 후 제거.
- **CI 보강**: `.github/workflows/ci.yml`에 **persist 경로 매트릭스** 추가.
  - 케이스: 기본(ENV 미설정), `MAIC_PERSIST_DIR` 지정.
  - 단계: `ruff` → **No‑Ellipsis Gate** → `mypy` → `pytest`.

### Notes
- **SSOT Persist 우선순위(현 버전)**  
  `st.session_state['_PERSIST_DIR']` → `src.rag.index_build.PERSIST_DIR`
  → `env: MAIC_PERSIST_DIR` → `~/.maic/persist`  
  (향후 `MAIC_PERSIST`를 도입·우선으로 승격 예정)  
