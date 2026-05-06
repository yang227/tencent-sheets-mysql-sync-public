#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
FRONTEND_ROOT="${PROJECT_ROOT}/frontend"

if command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  echo "python or python3 is required." >&2
  exit 1
fi

read_runtime() {
  "${PYTHON_BIN}" "${SCRIPT_DIR}/runtime_settings.py"
}

FRONTEND_HOST="$(read_runtime | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin)['frontend_host'])")"
FRONTEND_PORT="$(read_runtime | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin)['frontend_port'])")"
FRONTEND_BACKEND_URL="$(read_runtime | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin)['frontend_backend_url'])")"

cd "${FRONTEND_ROOT}"

if [[ ! -d "node_modules" ]]; then
  npm install
fi

export FRONTEND_HOST FRONTEND_PORT FRONTEND_BACKEND_URL
npm run dev -- --host "${FRONTEND_HOST}" --port "${FRONTEND_PORT}"
