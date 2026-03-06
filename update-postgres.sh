#!/bin/bash

set -euo pipefail

# Script to update the database
# The script delegates dump creation to scripts/backup_postgres.sh
# The script is designed to have generous sleep times to not break on slower servers

# NB: IF YOU TRY STARTING THE WRONG MAJOR VERSION CONTAINER AT FIRST THE SCRIPT WILL CURRENTLY FAIL LEADING TO DATA LOSS

if [ -f /.dockerenv ]; then
  echo "This script cannot be run inside a docker container.";
  exit 1;
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

version=$1
requested_mode=${2:-prod}

if [ -z "$version" ]; then
  echo "Please provide the desired PostgreSQL version as the first argument"
  exit 1
fi

resolve_env_file() {
  local mode="$1"
  local -a candidates=()

  case "$mode" in
    dev)
      candidates=(
        "${SCRIPT_DIR}/.env"
        "${SCRIPT_DIR}/.env.example"
      )
      ;;
    prod)
      candidates=(
        "${SCRIPT_DIR}/.env.prod"
        "${SCRIPT_DIR}/.env"
        "${SCRIPT_DIR}/.env.example"
      )
      ;;
    *)
      if [ -f "$mode" ]; then
        echo "$mode"
        return 0
      elif [ -f "${SCRIPT_DIR}/$mode" ]; then
        echo "${SCRIPT_DIR}/$mode"
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

if [ "$config_file" = "${SCRIPT_DIR}/.env.example" ]; then
  echo "Resolved environment file is ${config_file}, which is not writable for upgrades."
  echo "Provide a writable env file or use a mode/path that resolves to one."
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

compose_path="${SCRIPT_DIR}/${compose_file}"

docker_compose() {
  docker compose -f "$compose_path" "$@"
}

# Check if the required environment variables are set
if [ -z "$DATE_POSTGRESQL_VERSION" ] || [ -z "$DATE_DB_PORT" ] || [ -z "$DATE_DB_PASSWORD" ] || [ -z "$COMPOSE_PROJECT_NAME" ]; then
  echo "Error: Required environment variables are not set"
  exit 1
fi

db_name="${DB_DATABASE:-postgres}"
db_user="${DB_USERNAME:-postgres}"

backup_output="$("${SCRIPT_DIR}/scripts/backup_postgres.sh" "$config_file")"
echo "$backup_output"

backup_dump_path="$(printf '%s\n' "$backup_output" | sed -n 's/^BACKUP_DUMP_PATH=//p' | tail -n 1)"

if [ -z "$backup_dump_path" ] || [ ! -f "$backup_dump_path" ]; then
  echo "Backup script did not produce a valid dump path"
  exit 1
fi

# Make sure website is stopped
docker_compose down && sleep 15 && docker_compose up -d db

# Wait for db to start
sleep 15

# Check if the container is stopped
db_container_id="$(docker_compose ps -q db)"
if [ -z "$db_container_id" ] || [ -z "$(docker ps -q --no-trunc | grep "$db_container_id")" ]; then
  echo "The container failed to start, This is probably because of wrong postgres version"
  exit 1
fi

# Check if any container is in a restart loop
if docker_compose exec db echo "Test command"; then
    echo "Test command ran successfully."
else
  echo "Test command failed to run."
  exit 1
fi

# Stop container and remove volumes
docker_compose down --volumes && sleep 15

# Update the PostgreSQL image version in the env file
DATE_POSTGRESQL_VERSION=$version
sed -i "s/DATE_POSTGRESQL_VERSION=.*/DATE_POSTGRESQL_VERSION=${DATE_POSTGRESQL_VERSION}/" "$config_file"

# Stat the container with the new version
docker_compose up -d db && sleep 15

# Restore the database dump to new container
docker_compose exec -T db psql -U "$db_user" -d "$db_name" < "$backup_dump_path"

# Stop container
docker_compose down
