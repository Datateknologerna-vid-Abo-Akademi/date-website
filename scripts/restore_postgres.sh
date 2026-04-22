#!/bin/bash

set -euo pipefail

if [ -f /.dockerenv ]; then
  echo "This script cannot be run inside a docker container."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

backup_path="${1:-}"

if [ -z "$backup_path" ]; then
  echo "Usage: $0 <backup-dump-or-manifest>"
  echo ""
  echo "  backup   Path to a .sql dump file or its .json manifest"
  exit 1
fi

if [[ "$backup_path" != /* ]]; then
  backup_path="${PROJECT_ROOT}/$backup_path"
fi

# Accept either a manifest or a dump file; resolve the other from it
if [[ "$backup_path" == *.json ]]; then
  manifest_file="$backup_path"
  dump_file="${backup_path%.json}.sql"
else
  dump_file="$backup_path"
  manifest_file="${backup_path%.sql}.json"
fi

if [ ! -f "$dump_file" ]; then
  echo "Dump file not found: $dump_file"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required but was not found in PATH"
  exit 1
fi

env_file="${PROJECT_ROOT}/.env"
if [ ! -f "$env_file" ]; then
  echo "No .env file found at $env_file"
  exit 1
fi

set -a
source "$env_file"
set +a

compose_file="${COMPOSE_FILE:-docker-compose.yml}"
if [[ "$compose_file" = /* ]]; then
  compose_path="$compose_file"
else
  compose_path="${PROJECT_ROOT}/${compose_file}"
fi
if [ ! -f "$compose_path" ]; then
  echo "Compose file $compose_path not found"
  exit 1
fi

if [ -z "${DATE_POSTGRESQL_VERSION:-}" ] || [ -z "${DATE_DB_PASSWORD:-}" ] || [ -z "${COMPOSE_PROJECT_NAME:-}" ]; then
  echo "Error: Required environment variables are not set"
  exit 1
fi

db_name="${DB_DATABASE:-postgres}"
db_user="${DB_USERNAME:-postgres}"
db_service="db"

# Verify checksum against manifest when available
if [ -f "$manifest_file" ]; then
  echo "Verifying dump integrity against manifest: $(basename "$manifest_file")"
  python - "$manifest_file" "$dump_file" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
dump_path = Path(sys.argv[2])

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
expected = manifest.get("dump_sha256", "")
if not expected:
    print("Manifest has no dump_sha256 field, skipping integrity check")
    sys.exit(0)

digest = hashlib.sha256()
with dump_path.open("rb") as f:
    for chunk in iter(lambda: f.read(1024 * 1024), b""):
        digest.update(chunk)

actual = digest.hexdigest()
if actual != expected:
    print(f"Checksum mismatch!\n  expected: {expected}\n  actual:   {actual}")
    sys.exit(1)

print(f"Checksum OK: {actual[:16]}...")
PY
else
  echo "No manifest found alongside dump, skipping integrity check"
fi

docker_compose() {
  docker compose --project-directory "$PROJECT_ROOT" -f "$compose_path" "$@"
}

db_started_by_script=0
db_container_id="$(docker_compose ps -q "$db_service" 2>/dev/null || true)"
if [ -n "$db_container_id" ] && [ "$(docker inspect -f '{{.State.Running}}' "$db_container_id" 2>/dev/null || true)" = "true" ]; then
  echo "${db_service} is already running, reusing existing container"
else
  echo "Starting ${db_service} service using ${compose_file}"
  docker_compose up -d "$db_service" >/dev/null
  db_started_by_script=1
fi

cleanup() {
  if [ "$db_started_by_script" -eq 1 ]; then
    echo "Stopping ${db_service} service started for restore"
    docker_compose stop "$db_service" >/dev/null || true
  fi
}

trap cleanup EXIT

echo "Waiting for PostgreSQL to accept connections"
ready=0
for _ in $(seq 1 30); do
  if docker_compose exec -T "$db_service" pg_isready -U "$db_user" -d "$db_name" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done

if [ "$ready" -ne 1 ]; then
  echo "PostgreSQL did not become ready in time"
  exit 1
fi

echo "Dropping and recreating database: $db_name"
docker_compose exec -T "$db_service" psql -U "$db_user" -d postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$db_name' AND pid <> pg_backend_pid();" \
  >/dev/null
docker_compose exec -T "$db_service" psql -U "$db_user" -d postgres \
  -c "DROP DATABASE IF EXISTS \"$db_name\";" \
  >/dev/null
docker_compose exec -T "$db_service" psql -U "$db_user" -d postgres \
  -c "CREATE DATABASE \"$db_name\" OWNER \"$db_user\";" \
  >/dev/null

echo "Restoring dump: $dump_file"
if ! docker_compose exec -T "$db_service" psql -U "$db_user" -d "$db_name" < "$dump_file"; then
  echo "Restore failed"
  exit 1
fi

echo "Restore complete"
