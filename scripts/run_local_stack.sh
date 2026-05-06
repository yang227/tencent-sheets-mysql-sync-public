#!/usr/bin/env bash

set -euo pipefail

WITH_FRONTEND=0
if [[ "${1:-}" == "--with-frontend" ]]; then
  WITH_FRONTEND=1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

"${SCRIPT_DIR}/start_metadata_mysql.sh"

cd "${PROJECT_ROOT}"
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8083 --reload > server8083.out.log 2> server8083.err.log &

if [[ "${WITH_FRONTEND}" -eq 1 ]]; then
  cd "${PROJECT_ROOT}/frontend"
  if [[ ! -d node_modules ]]; then
    npm install
  fi
  nohup npm run dev -- --host 0.0.0.0 --port 5173 > ../server5173.out.log 2> ../server5173.err.log &
fi

echo "Backend started at http://127.0.0.1:8083"
if [[ "${WITH_FRONTEND}" -eq 1 ]]; then
  echo "Frontend dev server started at http://127.0.0.1:5173"
fi
