#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

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

APP_HOST="$(read_runtime | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin)['app_host'])")"
APP_PORT="$(read_runtime | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin)['app_port'])")"

"${PYTHON_BIN}" -m uvicorn app.main:app --host "${APP_HOST}" --port "${APP_PORT}" --reload
