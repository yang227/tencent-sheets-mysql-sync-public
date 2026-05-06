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

if [[ ! -f ".env" ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

if [[ ! -f "config.yaml" ]]; then
  cp config.example.yaml config.yaml
  echo "Created config.yaml from config.example.yaml"
fi

if [[ ! -d ".venv" ]]; then
  "${PYTHON_BIN}" -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

cd frontend
npm install

echo "Local bootstrap complete. Fill .env and config.yaml before starting the stack."
