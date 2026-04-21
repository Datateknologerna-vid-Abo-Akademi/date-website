#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_MODE="dev"
REQUESTED_MODE="${1:-$DEFAULT_MODE}"

if [ -n "${2:-}" ]; then
    echo "Usage: source env.sh [dev|prod|path/to/compose.yml]" >&2
    return 1 2>/dev/null || exit 1
fi

case "$REQUESTED_MODE" in
    dev)
        export COMPOSE_FILE_PATH="docker-compose.yml"
        ;;
    prod)
        export COMPOSE_FILE_PATH="docker-compose.prod.yml"
        ;;
    *)
        export COMPOSE_FILE_PATH="$REQUESTED_MODE"
        ;;
esac

if [[ "$COMPOSE_FILE_PATH" = /* ]]; then
    DATE_COMPOSE_FILE="$COMPOSE_FILE_PATH"
else
    DATE_COMPOSE_FILE="${SCRIPT_DIR}/${COMPOSE_FILE_PATH}"
fi

alias date="docker compose --project-directory \"${SCRIPT_DIR}\" -f \"${DATE_COMPOSE_FILE}\""
alias date-manage="date run web python /code/manage.py"
alias date-migrate="date-manage migrate --noinput"
alias date-makemigrations="date-manage makemigrations"
alias date-collectstatic="date-manage collectstatic"
alias date-cleaninit="\"${SCRIPT_DIR}/scripts/clean_init.sh\""
alias date-stop="date down"
alias date-start="date-pull; date-stop; date up --build"
alias date-start-detached="date-pull; date up -d --build"
alias date-createsuperuser="date-manage createsuperuser"
alias date-pull="date pull"
alias date-seed-gallery="date-manage seed_gallery"
alias date-seed-gallery-clear="date-manage seed_gallery --clear"

alias date-all="docker compose --project-directory \"${SCRIPT_DIR}\" -f \"${SCRIPT_DIR}/docker-compose.dev-all.yml\""
alias date-all-manage="date-all run web python /code/manage.py"
alias date-all-start="date-all up --build"
alias date-all-stop="date-all down"
alias date-all-cleaninit="COMPOSE_FILE_PATH=\"docker-compose.dev-all.yml\" \"${SCRIPT_DIR}/scripts/clean_init.sh\""
alias date-all-seed-gallery="date-all-manage seed_gallery"
alias date-all-seed-gallery-clear="date-all-manage seed_gallery --clear"

date-test() {
    docker compose --project-directory "${SCRIPT_DIR}" -f "${DATE_COMPOSE_FILE}" run -e TEST=1 web /bin/bash -c './wait-for-postgres.sh db:5432 && python /code/manage.py test "$@"'
}
