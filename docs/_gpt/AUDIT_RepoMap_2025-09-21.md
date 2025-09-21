
# AUDIT — Repo Map & Quick Findings (2025-09-21)

## Top-level snapshot
```
├─ .github/
│  ├─ .github/CODEOWNERS
│  ├─ .github/ISSUE_TEMPLATE/
│  ├─ .github/PULL_REQUEST_TEMPLATE.md
│  ├─ .github/codeql/
│  ├─ .github/pull_request_template.md
│  ├─ .github/semantic.yml
│  ├─ .github/workflows/
├─ .streamlit/
│  ├─ .streamlit/config.toml
│  ├─ .streamlit/secrets.example.toml
├─ CHANGELOG.md
├─ DEV_SETUP.md
├─ NIGHTLY_CHECKLIST.md
├─ README.md
├─ TESTING_GUIDE.md
├─ WORKSPACE_INDEX.md
├─ app.py
├─ docs/
│  ├─ docs/_archive/
│  ├─ docs/_gpt/
│  ├─ docs/pr/
│  ├─ docs/roadmap/
├─ mypy.ini
├─ pages/
│  ├─ pages/15_index_status.py
│  ├─ pages/90_admin_prompt.py
├─ prompts.yaml
├─ pyproject.toml
├─ pytest.ini
├─ requirements.txt
├─ ruff.toml
├─ schemas/
│  ├─ schemas/prompts.schema.json
├─ scripts/
│  ├─ scripts/build_and_publish.py
│  ├─ scripts/build_prompts_bundle.py
│  ├─ scripts/check_import_paths.sh
│  ├─ scripts/check_ssot_pointer.py
│  ├─ scripts/check_workspace_pointer.py
│  ├─ scripts/fix_markers_and_ellipsis.py
│  ├─ scripts/gen_tree.py
│  ├─ scripts/hotfix_patch_guard.py
│  ├─ scripts/no_ellipsis_gate.py
│  ├─ scripts/publish_index_bundle.py
│  ├─ scripts/restore_and_verify.py
│  ├─ scripts/restore_latest_index.py
│  ├─ scripts/smoke_checks.py
│  ├─ scripts/validate_prompts.py
│  ├─ scripts/verify_index_ready.py
├─ src/
│  ├─ src/__init__.py
│  ├─ src/agents/
│  ├─ src/backup/
│  ├─ src/common/
│  ├─ src/compat/
│  ├─ src/config.py
│  ├─ src/core/
│  ├─ src/drive/
│  ├─ src/integrations/
│  ├─ src/llm/
│  ├─ src/modes/
│  ├─ src/prompt_modes.py
│  ├─ src/prompting/
│  ├─ src/rag/
│  ├─ src/runtime/
│  ├─ src/services/
│  ├─ src/state/
│  ├─ src/ui/
│  ├─ src/ui_admin/
│  ├─ src/ui_orchestrator.py
│  ├─ src/validation/
│  ├─ src/vision/
├─ tests/
│  ├─ tests/conftest.py
│  ├─ tests/fixtures/
│  ├─ tests/test_agents_common_api.py
│  ├─ tests/test_agents_no_local_duplicates.py
│  ├─ tests/test_agents_use_common_module.py
│  ├─ tests/test_app_helpers_uniqueness.py
│  ├─ tests/test_brackets_validator.py
│  ├─ tests/test_core_index_probe.py
│  ├─ tests/test_eval_parser.py
│  ├─ tests/test_evaluator_prompt_shape.py
│  ├─ tests/test_fix_markers_and_ellipsis.py
│  ├─ tests/test_generate_mode_docs_smoke.py
│  ├─ tests/test_label_policy.py
│  ├─ tests/test_label_rag.py
│  ├─ tests/test_modes.py
│  ├─ tests/test_modes_canon_config.py
│  ├─ tests/test_modes_router.py
│  ├─ tests/test_no_legacy_imports.py
│  ├─ tests/test_persist_calls_standardized.py
│  ├─ tests/test_prepared_helpers_api_surface.py
│  ├─ tests/test_prompt_builder.py
│  ├─ tests/test_rag_engine_bm25.py
│  ├─ tests/test_rag_engine_toggle.py
│  ├─ tests/test_rag_search.py
│  ├─ tests/test_removed_files_absent.py
│  ├─ tests/test_sentence_prompt_template.py
│  ├─ tests/test_smoke_app_import.py
│  ├─ tests/test_smoke_gdrive_driver.py
│  ├─ tests/test_ui_header_ready_level.py
├─ tools/
│  ├─ tools/changelog_release.py
│  ├─ tools/check_coverage.py
│  ├─ tools/coverage_baseline.txt
│  ├─ tools/generate_mode_docs.py
│  ├─ tools/guard_patch.py
│  ├─ tools/print_profiles.py
│  ├─ tools/validate_canon.py
```

### Notable modules (src/)
- `app.py` — Streamlit 엔트리포인트. 관리자 사이드바는 `src.ui.utils.sider.apply_admin_chrome()`로 적용.  
- `src/ui/ops/indexing_panel.py`, `src/services/index_state.py`, `src/services/index_actions.py` — 관리자 인덱싱 패널 이관(A1r).
- `src/ui/admin_prompts.py` + `pages/90_admin_prompt.py` — 관리자 프롬프트 관리.
- `src/rag/*` — 라벨/검색/인덱싱.
- `src/ui/utils/sider.py` — 관리자 크롬.
- `tests/*` — 레거시 가드(`test_removed_files_absent.py` 등).

### Quick findings (outside docs)
- `.github/` 내 PR 템플릿 중복(대소문자/경로 불일치) → 하나만 남기고 정규화 권장
- `src/ui_admin/` 패키지(디렉터리) 잔존 — 사용하지 않으면 삭제 권장(혼동 방지)
