# ============================== [01] check_import_paths.sh — START ==============================
#!/usr/bin/env bash
set -euo pipefail

# 잘못된 모듈 경로 패턴 (정규식)
BAD_PATTERNS='(src\.intergrations|src\.intergration|src\.intergratoins|src\.integratons|src\.integations|src\.integraitons|src\.integratoin|src\.integratioins|src\.integratinos|scr\.integrations|scr\.intergrations|scr\.intergratoins)'

# 스캔 대상에서 흔한 폴더 제외
grep -RInE "$BAD_PATTERNS" \
  --exclude-dir .git \
  --exclude-dir venv \
  --exclude-dir .venv \
  --exclude-dir node_modules \
  --include='*.py' --include='*.pyi' --include='*.y*ml' --include='*.toml' --include='*.md' --include='*.json' \
  . || { echo "OK: no bad import paths found."; exit 0; }

echo "ERROR: invalid import path detected above. Use 'src.integrations' instead." >&2
exit 1
# =============================== [01] check_import_paths.sh — END ===============================
