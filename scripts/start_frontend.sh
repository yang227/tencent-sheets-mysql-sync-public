#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
FRONTEND_ROOT="${PROJECT_ROOT}/frontend"
cd "${FRONTEND_ROOT}"

if [[ ! -d "node_modules" ]]; then
  npm install
fi

npm run dev -- --host 0.0.0.0 --port 5173
