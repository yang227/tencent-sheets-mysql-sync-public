#!/usr/bin/env bash

set -euo pipefail

WITH_FRONTEND=0
if [[ "${1:-}" == "--with-frontend" ]]; then
  WITH_FRONTEND=1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

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
APP_URL_HOST="$(read_runtime | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin)['app_url_host'])")"
FRONTEND_HOST="$(read_runtime | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin)['frontend_host'])")"
FRONTEND_PORT="$(read_runtime | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin)['frontend_port'])")"
FRONTEND_URL_HOST="$(read_runtime | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin)['frontend_url_host'])")"
FRONTEND_BACKEND_URL="$(read_runtime | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin)['frontend_backend_url'])")"

"${SCRIPT_DIR}/start_metadata_mysql.sh"

cd "${PROJECT_ROOT}"
nohup "${PYTHON_BIN}" -m uvicorn app.main:app --host "${APP_HOST}" --port "${APP_PORT}" --reload > "server${APP_PORT}.out.log" 2> "server${APP_PORT}.err.log" &

if [[ "${WITH_FRONTEND}" -eq 1 ]]; then
  cd "${PROJECT_ROOT}/frontend"
  if [[ ! -d node_modules ]]; then
    npm install
  fi
  export FRONTEND_HOST FRONTEND_PORT FRONTEND_BACKEND_URL
  nohup npm run dev -- --host "${FRONTEND_HOST}" --port "${FRONTEND_PORT}" > "../server${FRONTEND_PORT}.out.log" 2> "../server${FRONTEND_PORT}.err.log" &
fi

echo "Backend started at http://${APP_URL_HOST}:${APP_PORT}"
if [[ "${WITH_FRONTEND}" -eq 1 ]]; then
  echo "Frontend dev server started at http://${FRONTEND_URL_HOST}:${FRONTEND_PORT}"
fi
