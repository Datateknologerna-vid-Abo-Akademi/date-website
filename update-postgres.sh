#!/bin/bash

set -euo pipefail

# Script to update the database
# The script delegates dump creation to scripts/backup_postgres.sh

if [ -f /.dockerenv ]; then
  echo "This script cannot be run inside a docker container.";
  exit 1;
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/scripts/lib/date_env.sh"

version="${1:-}"
requested_mode=${2:-prod}

if [ -z "$version" ]; then
  echo "Please provide the desired PostgreSQL version as the first argument"
  exit 1
fi

config_file="$(date_resolve_env_file "$SCRIPT_DIR" "$requested_mode")"
resolved_mode="$(date_resolve_env_mode "$requested_mode" "$config_file")"

if [ "$config_file" = "${SCRIPT_DIR}/.env.example" ]; then
  echo "Resolved environment file is ${config_file}, which is not writable for upgrades."
  echo "Provide a writable env file or use a mode/path that resolves to one."
  exit 1
fi

set -a
source "$config_file"
set +a

config_compose_file="$(date_read_env_value "$config_file" COMPOSE_FILE)"
date_apply_env_mode "$resolved_mode"

compose_file="$(date_resolve_compose_file "$resolved_mode" "$config_compose_file")"

if [[ "$compose_file" = /* ]]; then
  compose_path="$compose_file"
else
  compose_path="${SCRIPT_DIR}/${compose_file}"
fi

docker_compose() {
  docker compose --project-directory "$SCRIPT_DIR" -f "$compose_path" "$@"
}

wait_for_db() {
  local max_attempts="${1:-30}"
  local attempt

  for attempt in $(seq 1 "$max_attempts"); do
    if docker_compose exec -T db pg_isready -U "$db_user" -d "$db_name" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  return 1
}

db_container_id() {
  docker_compose ps -q db 2>/dev/null || true
}

ensure_db_running() {
  local container_id
  container_id="$(db_container_id)"

  if [ -z "$container_id" ] || [ "$(docker inspect -f '{{.State.Running}}' "$container_id" 2>/dev/null || true)" != "true" ]; then
    echo "The db container failed to start."
    return 1
  fi

  if ! wait_for_db 45; then
    echo "PostgreSQL did not become ready in time."
    return 1
  fi
}

validate_data_directory_is_persisted() {
  local container_id
  local data_directory
  local mount_destinations
  local mount_destination

  container_id="$(db_container_id)"
  if [ -z "$container_id" ]; then
    echo "Could not determine db container id while validating data directory"
    return 1
  fi

  data_directory="$(docker_compose exec -T db psql -U "$db_user" -d "$db_name" -tAc "SHOW data_directory")"
  if [ -z "$data_directory" ]; then
    echo "Could not determine PostgreSQL data_directory"
    return 1
  fi

  mount_destinations="$(docker inspect -f '{{range .Mounts}}{{println .Destination}}{{end}}' "$container_id" 2>/dev/null || true)"
  while IFS= read -r mount_destination; do
    [ -z "$mount_destination" ] && continue
    case "$data_directory" in
      "$mount_destination"|"$mount_destination"/*)
        return 0
        ;;
    esac
  done <<< "$mount_destinations"

  echo "PostgreSQL data_directory '$data_directory' is not inside a mounted volume."
  echo "Refusing to continue because recreating containers would discard the database files."
  echo "Set PGDATA to a path under a mounted directory such as /var/lib/postgresql/data/pgdata."
  return 1
}

read_public_table_count() {
  docker_compose exec -T db psql -U "$db_user" -d "$db_name" -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
}

read_django_migration_count() {
  docker_compose exec -T db psql -U "$db_user" -d "$db_name" -tAc "SELECT COUNT(*) FROM django_migrations" 2>/dev/null || echo ""
}

# Check if the required environment variables are set
if [ -z "${DATE_POSTGRESQL_VERSION:-}" ] || [ -z "${DATE_DB_PASSWORD:-}" ] || [ -z "${COMPOSE_PROJECT_NAME:-}" ]; then
  echo "Error: Required environment variables are not set"
  exit 1
fi

db_name="${DB_DATABASE:-postgres}"
db_user="${DB_USERNAME:-postgres}"
current_version="${DATE_POSTGRESQL_VERSION}"
current_major="${current_version%%.*}"
target_major="${version%%.*}"

if ! [[ "$target_major" =~ ^[0-9]+$ ]]; then
  echo "Target PostgreSQL version '$version' does not start with a numeric major version"
  exit 1
fi

if ! [[ "$current_major" =~ ^[0-9]+$ ]]; then
  echo "Current DATE_POSTGRESQL_VERSION '$current_version' does not start with a numeric major version"
  exit 1
fi

if [ "$target_major" -le "$current_major" ]; then
  if [ "$target_major" -eq "$current_major" ]; then
    echo "Target version '$version' is in the same major series as current version '$current_version'."
    echo "This script is only for major upgrades. For minor upgrades, update DATE_POSTGRESQL_VERSION and recreate the containers."
  else
    echo "Refusing to downgrade from PostgreSQL major version $current_major to $target_major."
  fi
  exit 1
fi

env_backup_file="$(mktemp)"
cp "$config_file" "$env_backup_file"
env_version_updated=0
upgrade_completed=0
backup_dump_path=""
backup_manifest_path=""
source_table_count=""
source_migration_count=""

cleanup() {
  local exit_code=$?
  if [ "$upgrade_completed" -ne 1 ] && [ "$env_version_updated" -eq 1 ]; then
    cp "$env_backup_file" "$config_file"
    echo "Upgrade failed; restored original DATE_POSTGRESQL_VERSION in $config_file"
  fi
  if [ "$exit_code" -ne 0 ] && [ -n "$backup_dump_path" ]; then
    echo "Backup dump preserved at: $backup_dump_path"
  fi
  if [ "$exit_code" -ne 0 ] && [ -n "$backup_manifest_path" ]; then
    echo "Backup manifest preserved at: $backup_manifest_path"
  fi
  rm -f "$env_backup_file"
  exit "$exit_code"
}

trap cleanup EXIT

backup_output="$("${SCRIPT_DIR}/scripts/backup_postgres.sh" "$config_file")"
echo "$backup_output"

backup_dump_path="$(printf '%s\n' "$backup_output" | sed -n 's/^BACKUP_DUMP_PATH=//p' | tail -n 1)"
backup_manifest_path="$(printf '%s\n' "$backup_output" | sed -n 's/^BACKUP_MANIFEST_PATH=//p' | tail -n 1)"

if [ -z "$backup_dump_path" ] || [ ! -f "$backup_dump_path" ]; then
  echo "Backup script did not produce a valid dump path"
  exit 1
fi

docker_compose up -d db

if ! ensure_db_running; then
  echo "This is often caused by an invalid PostgreSQL image version or container startup failure."
  exit 1
fi

if ! validate_data_directory_is_persisted; then
  exit 1
fi

source_table_count="$(read_public_table_count)"
if ! [[ "$source_table_count" =~ ^[0-9]+$ ]] || [ "$source_table_count" -eq 0 ]; then
  echo "Source database validation failed: expected at least one public table before upgrade"
  exit 1
fi

source_migration_count="$(read_django_migration_count)"

# Stop container and remove volumes
docker_compose down --volumes

# Update the PostgreSQL image version in the env file
DATE_POSTGRESQL_VERSION=$version
sed -i "s/DATE_POSTGRESQL_VERSION=.*/DATE_POSTGRESQL_VERSION=${DATE_POSTGRESQL_VERSION}/" "$config_file"
env_version_updated=1

# Start the container with the new version
docker_compose up -d db

if ! ensure_db_running; then
  echo "The new PostgreSQL container did not become ready."
  exit 1
fi

if ! validate_data_directory_is_persisted; then
  exit 1
fi

# Restore the database dump to new container
docker_compose exec -T db psql -v ON_ERROR_STOP=1 -U "$db_user" -d "$db_name" < "$backup_dump_path"

echo "Validating restored database"
docker_compose exec -T db psql -v ON_ERROR_STOP=1 -U "$db_user" -d "$db_name" -c "SELECT 1;" >/dev/null

restored_table_count="$(docker_compose exec -T db psql -U "$db_user" -d "$db_name" -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")"
if ! [[ "$restored_table_count" =~ ^[0-9]+$ ]] || [ "$restored_table_count" -eq 0 ]; then
  echo "Restore validation failed: no public tables found after restore"
  exit 1
fi

if [ "$restored_table_count" -lt "$source_table_count" ]; then
  echo "Restore validation failed: source had $source_table_count public tables, restored database has $restored_table_count"
  exit 1
fi

restored_migration_count="$(read_django_migration_count)"
if [ -n "$source_migration_count" ] && ! [[ "$source_migration_count" =~ ^[0-9]+$ ]]; then
  source_migration_count=""
fi
if [ -n "$restored_migration_count" ] && ! [[ "$restored_migration_count" =~ ^[0-9]+$ ]]; then
  restored_migration_count=""
fi

if [ -n "$source_migration_count" ] && [ -n "$restored_migration_count" ] && [ "$restored_migration_count" -lt "$source_migration_count" ]; then
  echo "Restore validation failed: source had $source_migration_count applied Django migrations, restored database has $restored_migration_count"
  exit 1
fi

upgrade_completed=1

echo "PostgreSQL upgrade restore completed successfully."
echo "Backup dump: $backup_dump_path"
if [ -n "$backup_manifest_path" ]; then
  echo "Backup manifest: $backup_manifest_path"
fi

# Stop container
docker_compose down
