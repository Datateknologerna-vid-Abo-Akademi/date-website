#!/bin/bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "WARNING! This will restore your project to an initial state."
echo "All database data will be permanently deleted."
read -p "Are you sure? y/n " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    [[ "$0" = "$BASH_SOURCE" ]] && exit 1 || return 1
fi

read -p "Also delete uploaded media files? y/n " -n 1 -r
echo
DELETE_MEDIA=false
if [[ $REPLY =~ ^[Yy]$ ]]; then
    DELETE_MEDIA=true
fi

source "$PROJECT_DIR/env.sh" dev
COMPOSE_PATH="$PROJECT_DIR/${COMPOSE_FILE_PATH:-docker-compose.yml}"

validate_fixtures() {
    echo "Validating fixtures..."
    local fixtures=(
        "fixtures/members.json"
        "fixtures/ads.json"
        "scripts/generate_dynamic_fixtures.py"
        "scripts/assets/dummy.svg"
        "scripts/assets/dummy.pdf"
    )
    for f in "${fixtures[@]}"; do
        if [[ ! -f "$PROJECT_DIR/$f" ]]; then
            echo "ERROR: Missing required fixture: $f"
            exit 1
        fi
    done
    echo "All required fixtures found."
}

wait_for_db() {
    echo "Waiting for database to be ready..."
    local max_attempts=30
    local attempt=0
    while [[ $attempt -lt $max_attempts ]]; do
        if docker compose -f "$COMPOSE_PATH" exec -T db pg_isready -U postgres -q 2>/dev/null; then
            echo "Database is ready."
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    echo "ERROR: Database did not become ready in time"
    exit 1
}

validate_fixtures

if [[ "$DELETE_MEDIA" == "true" ]]; then
    echo "Deleting media files..."
    rm -rf "$PROJECT_DIR/media/archive"/* 2>/dev/null || true
    rm -rf "$PROJECT_DIR/media/pdfs"/* 2>/dev/null || true
    echo "Media files deleted."
fi

echo "Shutting down containers..."
docker compose -f "$COMPOSE_PATH" down --remove-orphans

echo "Building required images and starting database container..."
docker compose -f "$COMPOSE_PATH" build db web
docker compose -f "$COMPOSE_PATH" up -d db

wait_for_db

echo "Recreating database..."
docker compose -f "$COMPOSE_PATH" exec -T db psql -U postgres -c "DROP DATABASE IF EXISTS temp;" 2>/dev/null || true
docker compose -f "$COMPOSE_PATH" exec -T db psql -U postgres -c "CREATE DATABASE temp;"
docker compose -f "$COMPOSE_PATH" exec -T db psql -U postgres -d temp -c "DROP DATABASE postgres;"
docker compose -f "$COMPOSE_PATH" exec -T db psql -U postgres -d temp -c "CREATE DATABASE postgres;"
docker compose -f "$COMPOSE_PATH" exec -T db psql -U postgres -c "DROP DATABASE temp;"

echo "Database cleared."

echo "Running migrations and loading fixtures..."
docker compose -f "$COMPOSE_PATH" run --rm web /bin/bash -c "
    ./wait-for-postgres.sh db:5432 && \
    python /code/manage.py migrate --noinput && \
    ./scripts/load_all_fixtures.sh && \
    python /code/manage.py shell -c \"
from members.models import Member
for username in ['admin', 'freshman', 'member']:
    u = Member.objects.get(username=username)
    u.set_password('admin')
    u.save()
print('Passwords set for all users.')
\"
"

docker compose -f "$COMPOSE_PATH" down --remove-orphans

echo ""
echo "============================================"
echo "Clean init completed successfully!"
echo "============================================"
echo ""
echo "Created users:"
echo "  - admin (superuser)    password: admin"
echo "  - freshman             password: admin"
echo "  - member               password: admin"
echo ""
echo "Login at: http://localhost:8000/admin"
echo ""
echo "Run 'date-start' or 'docker compose up -d' to start the server."
