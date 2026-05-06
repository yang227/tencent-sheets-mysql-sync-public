#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

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

if docker ps -a --filter "name=^tencent-sync-metadata-mysql$" --format "{{.Names}}" | grep -qx "tencent-sync-metadata-mysql"; then
  docker start tencent-sync-metadata-mysql >/dev/null
else
  docker compose -f docker-compose.metadata.yml up -d
fi

for _ in $(seq 1 30); do
  if docker exec tencent-sync-metadata-mysql sh -lc "mysqladmin -h127.0.0.1 -uroot -p'${ROOT_PASSWORD}' ping >/dev/null 2>&1"; then
    ready=1
    break
  fi
  sleep 2
done

if [[ "${ready:-0}" -ne 1 ]]; then
  echo "Metadata MySQL container started, but MySQL did not become ready in time." >&2
  exit 1
fi

docker exec -i tencent-sync-metadata-mysql sh -lc "mysql -h127.0.0.1 -uroot -p'${ROOT_PASSWORD}' tencent_sheets_sync" < migrations/init.sql
docker exec -i tencent-sync-metadata-mysql sh -lc "mysql -h127.0.0.1 -uroot -p'${ROOT_PASSWORD}' tencent_sheets_sync" < migrations/add_config_tables.sql

echo "Metadata MySQL is ready on 127.0.0.1:13306"
