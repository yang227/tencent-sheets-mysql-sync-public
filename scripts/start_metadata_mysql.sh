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

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

ROOT_PASSWORD="${METADATA_MYSQL_ROOT_PASSWORD:-}"
if [[ -z "${ROOT_PASSWORD}" || "${ROOT_PASSWORD}" == "change_this_root_password" ]]; then
  echo "METADATA_MYSQL_ROOT_PASSWORD is required. Copy .env.example to .env and set a real password." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required but was not found in PATH." >&2
  exit 1
fi

METADATA_CONTAINER_NAME="$(read_runtime | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin)['metadata_container_name'])")"
METADATA_COMPOSE_FILE="$(read_runtime | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin)['metadata_compose_file'])")"
METADATA_PORT="$(read_runtime | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin)['metadata_port'])")"
METADATA_HOST="$(read_runtime | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin)['metadata_host'])")"
METADATA_DATABASE="$(read_runtime | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin)['metadata_database'])")"
METADATA_ROOT_USER="$(read_runtime | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin)['metadata_root_user'])")"
METADATA_READY_TIMEOUT="$(read_runtime | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin)['metadata_ready_timeout'])")"

if docker ps -a --filter "name=^${METADATA_CONTAINER_NAME}$" --format "{{.Names}}" | grep -qx "${METADATA_CONTAINER_NAME}"; then
  docker start "${METADATA_CONTAINER_NAME}" >/dev/null
else
  docker compose -f "${METADATA_COMPOSE_FILE}" up -d
fi

for _ in $(seq 1 $(( (METADATA_READY_TIMEOUT + 1) / 2 ))); do
  if docker exec "${METADATA_CONTAINER_NAME}" sh -lc "mysqladmin -h127.0.0.1 -u${METADATA_ROOT_USER} -p'${ROOT_PASSWORD}' ping >/dev/null 2>&1"; then
    ready=1
    break
  fi
  sleep 2
done

if [[ "${ready:-0}" -ne 1 ]]; then
  echo "Metadata MySQL container started, but MySQL did not become ready in time." >&2
  exit 1
fi

docker exec -i "${METADATA_CONTAINER_NAME}" sh -lc "mysql -h127.0.0.1 -u${METADATA_ROOT_USER} -p'${ROOT_PASSWORD}' ${METADATA_DATABASE}" < migrations/init.sql
docker exec -i "${METADATA_CONTAINER_NAME}" sh -lc "mysql -h127.0.0.1 -u${METADATA_ROOT_USER} -p'${ROOT_PASSWORD}' ${METADATA_DATABASE}" < migrations/add_config_tables.sql

echo "Metadata MySQL is ready on ${METADATA_HOST}:${METADATA_PORT}"
