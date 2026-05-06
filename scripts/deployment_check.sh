#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

ok() {
  echo "[OK] $1"
}

warn() {
  echo "[WARN] $1"
}

fail() {
  echo "[FAIL] $1" >&2
}

if command -v python3 >/dev/null 2>&1; then
  ok "$(python3 --version)"
else
  fail "python3 is not available"
  exit 1
fi

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

if curl -fsS --max-time 3 http://127.0.0.1:8083/health >/dev/null 2>&1; then
  ok "backend health endpoint is reachable"
else
  warn "backend health endpoint is not reachable"
fi

echo "Deployment check completed."
