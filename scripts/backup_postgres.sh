#!/bin/bash

set -euo pipefail

if [ -f /.dockerenv ]; then
  echo "This script cannot be run inside a docker container."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

requested_mode="${1:-prod}"
output_dir="${2:-${PROJECT_ROOT}/backups}"

if [[ "$output_dir" != /* ]]; then
  output_dir="${PROJECT_ROOT}/$output_dir"
fi

resolve_env_file() {
  local mode="$1"
  local -a candidates=()

  case "$mode" in
    dev)
      candidates=(
        "${PROJECT_ROOT}/.env"
        "${PROJECT_ROOT}/.env.example"
      )
      ;;
    prod)
      candidates=(
        "${PROJECT_ROOT}/.env.prod"
        "${PROJECT_ROOT}/.env"
        "${PROJECT_ROOT}/.env.example"
      )
      ;;
    *)
      if [ -f "$mode" ]; then
        echo "$mode"
        return 0
      elif [ -f "${PROJECT_ROOT}/$mode" ]; then
        echo "${PROJECT_ROOT}/$mode"
        return 0
      else
        echo "Environment file '$mode' not found" >&2
        return 1
      fi
      ;;
  esac

  for candidate in "${candidates[@]}"; do
    if [ -f "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done

  echo "No suitable environment file found for mode '$mode'" >&2
  return 1
}

config_file="$(resolve_env_file "$requested_mode")"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required but was not found in PATH"
  exit 1
fi

set -a
source "$config_file"
set +a

case "$requested_mode" in
  prod)
    DATE_DEVELOP="False"
    ;;
  dev)
    DATE_DEVELOP="${DATE_DEVELOP:-True}"
    ;;
esac

compose_file="docker-compose.yml"
if [ "${DATE_DEVELOP:-True}" = "False" ]; then
  compose_file="docker-compose.prod.yml"
fi

compose_path="${PROJECT_ROOT}/${compose_file}"
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
project_name="${COMPOSE_PROJECT_NAME}"
project_label="${PROJECT_NAME:-}"
db_service="db"
timestamp="$(date -u +"%Y%m%dT%H%M%SZ")"

mkdir -p "$output_dir"

dump_file="${output_dir}/${project_name}-${timestamp}.sql"
manifest_file="${output_dir}/${project_name}-${timestamp}.json"

docker_compose() {
  docker compose -f "$compose_path" "$@"
}

echo "Starting ${db_service} service using ${compose_file}"
docker_compose up -d "$db_service" >/dev/null

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

postgres_version="$(docker_compose exec -T "$db_service" psql -U "$db_user" -d "$db_name" -tAc "SHOW server_version")"
postgres_major_version="${postgres_version%%.*}"

echo "Creating dump at $dump_file"
if ! docker_compose exec -T "$db_service" pg_dump -U "$db_user" "$db_name" > "$dump_file"; then
  rm -f "$dump_file"
  echo "Database dump failed"
  exit 1
fi

if [ ! -s "$dump_file" ]; then
  rm -f "$dump_file"
  echo "Backup file is empty, exiting"
  exit 1
fi

python - "$manifest_file" "$project_name" "$project_label" "$timestamp" "$(basename "$dump_file")" "$db_service" "$db_name" "$db_user" "$postgres_version" "$postgres_major_version" <<'PY'
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
project_name = sys.argv[2]
project_label = sys.argv[3]
timestamp = sys.argv[4]
dump_filename = sys.argv[5]
db_service = sys.argv[6]
db_name = sys.argv[7]
db_user = sys.argv[8]
postgres_version = sys.argv[9]
postgres_major_version = sys.argv[10]

manifest = {
    "project_name": project_name,
    "created_at_utc": timestamp,
    "dump_filename": dump_filename,
    "dump_format": "plain_sql",
    "database_engine": "postgresql",
    "database_service": db_service,
    "database_name": db_name,
    "database_user": db_user,
    "postgres_version": postgres_version,
    "postgres_major_version": postgres_major_version,
}

if project_label:
    manifest["project_label"] = project_label

manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
PY

echo "Created backup dump: $dump_file"
echo "Created backup manifest: $manifest_file"
echo "BACKUP_DUMP_PATH=$dump_file"
echo "BACKUP_MANIFEST_PATH=$manifest_file"
