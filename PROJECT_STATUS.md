MAIC Project Master Plan (Report Draft v1)
Purpose: To summarize the results of the stabilization and quality improvement efforts from the last session, and to formalize the action plan, priorities, and team agreements for the next session. This document is intended to be the final version, ready for direct commit to the repository.

0) Current Status at a Glance
CI Pipeline (Strict Mode)

✅ ruff (lint/format) passing

✅ mypy (strict, py3.10/3.11/3.12) passing

⏭ pytest: Skips if test files are absent (maintaining the gate structure)

Workflows

✅ Basic CI (on push/PR)

✅ nightly.yml (scheduled/manual + optional pre-release after gates pass)

✅ release.yml (on tag/manual + official release after gates pass)

Code Quality (Key Improvements)

Removed remaining unnecessary # type: ignore[...] directives.

Applied exception guards, fallbacks, and dynamic imports for dynamic dependencies (e.g., streamlit, openai).

Reduced inter-module coupling and organized the structure for patches to be applicable on a sectional basis (START~END).

1) What We've Accomplished (Summary)
1.1 Linting & Type Stability
Ruff: Systematically fixed sorting, unused imports, line length exceeded (E501), unused variables (F841), etc.

mypy:

Resolved duplicate definitions/re-bindings (especially for Settings) — single alias binding + explicit types.

Eliminated remaining Optional/Any/attr-defined issues — guards + explicit type hints + Protocols.

Ensured exception-safe access for streamlit and other dynamically imported modules (hasattr, getattr, Mapping cast).

1.2 Key File Improvements (Functionally Unchanged, Stability↑)
src/rag_engine.py

Resolved F821 by removing global symbol dependencies (using internal wrapper _IndexObj).

Refactored to separate conflicting internal variables in the TF-IDF engine (mypy warnings).

src/ui_orchestrator.py

Removed unused restore_latest function (F841).

Eliminated mypy warnings by explicitly typing the details structure.

Cleaned up loose imports/guards and stabilized error log collection.

src/ui_components.py

Replaced callable with Callable[..., Any] and added explicit return types.

src/rag/index_build.py

Added an explicit type (Dict[str, Any]) for the out variable from unpacking ZIP snapshots.

src/rag/__init__.py

Removed export of a non-existent symbol (quick_precheck).

src/config.py

Refactored multiple Settings definitions into _SettingsP2/_SettingsP1/_SettingsSimple + single binding.

Eliminated multi-assignment warnings/ignores by declaring Settings: type[_BaseFields].

src/llm/providers.py

Implemented dynamic import (importlib) for openai + safe response handling.

Removed unnecessary ignores in _secret() by using guard-based access.

Formatted over-long lines (E501) into multi-line literals.

src/backup/github_release.py

Completely restructured and sectionalized: Added utility fallbacks, logger Protocol, and ensured get_secret always returns a string.

Replaced attribute imports with module imports + runtime guards.

Made release/asset selection/download/restore logic exception-safe.

app.py

Reinforced the section for the UI orchestrator with lazy imports and file path fallbacks.

Improved type and runtime stability with a spec.loader None guard.

src/ui_admin.py

Guarded access to st.secrets, removing an ignore directive.

1.3 CI/Actions System
Basic CI: ruff → format → mypy → pytest (if tests exist).

Nightly: Publishes artifacts/pre-releases (optional) after all gates pass.

Release: Publishes an official release on v* tags or manual trigger after all gates pass.

Configured with caching, parallelism, least privilege permissions, and ready for branch protection integration.

2) Retrospective: Failures & Learnings
"Failure is an asset" — We document causes and lessons clearly to inform future decisions.

Initial Failure to Detect Recurring Errors

Symptom: The same mypy/ruff errors reappeared in logs but were mistaken for new issues.

Cause: Section-based patches applied to multiple files simultaneously revealed missing headers (e.g., importlib) later in the process.

Lesson/Improvement: Established and now adhere to the protocol: "First, check if the log is identical to the previous one, then report my assessment (mistake vs. new cause)."

Over-reliance on Attribute Imports

Symptom: from src.common.utils import get_secret, logger led to attr-defined errors when a symbol was missing from the module.

Lesson: Adopted the module import + getattr guard pattern as the standard.

Dependency on Unnecessary # type: ignore

Symptom: Increase in unused-ignore directives, raising maintenance costs.

Lesson: Eliminate static errors "at the source" using guards, explicit types, and Protocols.

Skipping pytest Stage Due to Lack of Tests

Symptom: Lack of an automated trust signal against functional regressions.

Lesson: It is safer in the long run to have at least minimal smoke tests to fully engage the gate.

3) Core Team Agreements (Mandatory)
Single Section Replacement (START~END)

Replace exactly one required section at a time. Modifying partial sections or multiple sections at once is prohibited.

Functional Invariance First

The primary goal is to preserve existing functionality while eliminating errors. Refactoring and optimization are separate rounds.

Lint/Type Priority

Ruff/mypy are gates. Adhere locally to the same standards enforced in the pipeline.

Log Reporting Protocol

Always first report whether the error is "the same or different" from the last one.

Always include my opinion on whether it was "a mistake vs. needs new cause investigation."

Guard Dynamic Dependencies

For streamlit, SDKs, and external modules, standardize on module import + hasattr/getattr + fallbacks.

Prohibit Unnecessary Ignores

# type: ignore[...] is a last resort. Resolve issues with types, guards, or Protocols whenever possible.

One Change at a Time

Keep changes small to enable rapid CI cycles and simplify cause-and-effect tracing.

Documentation & Sectioning

All changes must be accompanied by section comments, a summary, and testing methods in the PR description.

4) Roadmap: What's Next
4.1 Immediate (Urgent)
Add Smoke Tests (min. 2)

tests/test_smoke_app.py: Smoke test for app entry point import and core function calls.

tests/test_rag_engine.py: Verify in-memory index loading and simple query result shape.

→ This is the minimum set required to activate the pytest gate.

Apply Branch Protection Rules

main Required checks: CI / gate (py3.10/3.11/3.12)

Connect Release Environments (with approver settings).

4.2 Short-Term (1–2 Sprints)
Introduce pre-commit hooks (ruff/mypy/black-like) — to reduce local mistakes.

Enhance Dependency Reproducibility

Generate requirements.lock with pip-tools and prioritize its use in CI.

Integrate Security Scanning

Add GitHub CodeQL workflow.

Attach SBOM (syft) to releases.

4.3 Mid-Term
Improve RAG Quality

Make embedding models/tokenizers selectable options.

Enhance chunking/metadata (section hints, page estimation precision).

Introduce a simple evaluation script (Recall@k, MRR, etc.).

Improve UI/UX

Add more granular health check items and timestamps to the diagnostics panel.

Implement download logs + auto-create issue template button.

4.4 Long-Term
Standardize Deployment (Containers / Infrastructure as Code).

Observability (structured logging, trace IDs, opt-in usage statistics).

Data Lifecycle Management (backup, encryption, retention policies).

5) Plan for the Next Session
Principle: "Minimize code changes, maximize trust signals."

Add 2 smoke tests (Two separate PRs, one for each section change).

Document and apply branch protection rules to the repository.

Add pre-commit configuration.

(Optional) Draft PRs for CodeQL and SBOM workflows.

6) Operations & Development Checklist
[ ] Capture the latest successful CI log and include it in release notes.

[ ] Set retention period for nightly pre-releases (e.g., 14 days).

[ ] Periodically check the validity of secrets/tokens (and set expiration alerts).

[ ] Add a Developer Onboarding section to README (local setup, local CI reproduction commands).

[ ] Document the error reporting process (issue templates) and log attachment rules.

7) Appendix A — Summary of Changes (By Section)
The following is an excerpt of representative items that were actually modified and sectionalized in this session.

src/rag_engine.py

[04] SECRETS/ID HELPERS — START~END

[08] LOCAL TF-IDF QUERY ENGINE — START~END

[09] PUBLIC API — START~END

src/ui_orchestrator.py

[01] lazy imports — START~END

[03] render_index_orchestrator_panel — START~END

src/ui_components.py

[UI-01] TOP OF FILE — START~END

[UI-06] LIST ROW — START~END

src/rag/index_build.py

[03] ZIP 스냅샷 생성/복원 — START~END

src/rag/__init__.py

[01] EXPORTS — START~END

src/config.py

[03] Settings 모델 — START~END (+ reinforced [03-BINDING])

src/llm/providers.py

[LLM-01] IMPORTS & SECRET HELPER — START~END

[LLM-02] OpenAI raw call — START~END

src/backup/github_release.py

[01] IMPORTS & UTILS FALLBACK — START~END

[02] CONSTANTS & PUBLIC EXPORTS — START~END

[03] HEADERS / LOG HELPERS — START~END

[04] RELEASE DISCOVERY — START~END

[05] ASSET DOWNLOAD & EXTRACT — START~END

[06] PUBLIC API: restore_latest — START~END

app.py

[11] 관리자 패널(지연 임포트 + 파일경로 폴백) — START~END

.github/workflows/ci.yml · nightly.yml · release.yml

Gate steps (ruff/mypy/pytest) + cache/permissions/concurrency settings.

8) Appendix B — Local Reproduction Guide
# 1) Install dependencies
python -m pip install -U pip wheel
pip install -r requirements.txt || true
pip install -U ruff mypy pytest pytest-cov

# 2) Run quality gates (same as CI)
ruff check . --fix && ruff format .
mypy .
pytest -q --maxfail=1 --disable-warnings # when tests/ exists

9) Appendix C — Log Reporting Template (Internal Team Protocol)
Common template for PRs/Issues/DMs

Summary: (1 line)

Identical/Different: Identical / Different from the last log.

My Assessment: (A mistake/omission vs. needs new cause investigation)

Basis: (File/line/rule name)

Patch Scope: (Section name, START~END, one section only)

Verification: (ruff/mypy/pytest command + expected result)

Conclusion
The current state is stable, adhering to a "functionally unchanged + strict quality" standard, with automated gates in place for Nightly and Release workflows.
The next session should start with adding smoke tests and hardening security/reproducibility. This will allow us to further elevate quality while maintaining development velocity.
