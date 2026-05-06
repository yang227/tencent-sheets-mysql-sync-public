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
  echo "[FAIL] python or python3 is not available" >&2
  exit 1
fi

read_runtime() {
  "${PYTHON_BIN}" "${SCRIPT_DIR}/runtime_settings.py"
}

APP_URL_HOST="$(read_runtime | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin)['app_url_host'])")"
APP_PORT="$(read_runtime | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin)['app_port'])")"

ok() {
  echo "[OK] $1"
}

warn() {
  echo "[WARN] $1"
}

fail() {
  echo "[FAIL] $1" >&2
}

ok "$("${PYTHON_BIN}" --version)"

if command -v node >/dev/null 2>&1; then
  ok "Node.js $(node --version)"
else
  warn "node is not available"
fi

if command -v docker >/dev/null 2>&1; then
  ok "$(docker --version)"
else
  warn "docker is not available"
fi

[[ -f .env ]] && ok ".env exists" || warn ".env does not exist"
[[ -f config.yaml ]] && ok "config.yaml exists" || warn "config.yaml does not exist"

if [[ -f requirements.txt ]]; then
  ok "requirements.txt exists"
else
  fail "requirements.txt is missing"
  exit 1
fi

if [[ -f frontend/package.json ]]; then
  ok "frontend package.json exists"
else
  fail "frontend package.json is missing"
  exit 1
fi

if curl -fsS --max-time 3 "http://${APP_URL_HOST}:${APP_PORT}/health" >/dev/null 2>&1; then
  ok "backend health endpoint is reachable"
else
  warn "backend health endpoint is not reachable"
fi

echo "Deployment check completed."
