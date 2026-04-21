#!/usr/bin/env bash

DATE_WEBSITE_DIR="${DATE_WEBSITE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"

if [ -n "${1:-}" ]; then
    echo "Usage: source env.sh" >&2
    echo "COMPOSE_FILE in .env selects the stack; env.sh only registers helper aliases." >&2
    return 1 2>/dev/null || exit 1
fi

alias date="docker compose --project-directory \"${DATE_WEBSITE_DIR}\""
alias date-manage="date run web python /code/manage.py"
alias date-migrate="date-manage migrate --noinput"
alias date-makemigrations="date-manage makemigrations"
alias date-collectstatic="date-manage collectstatic"
alias date-cleaninit="\"${DATE_WEBSITE_DIR}/scripts/clean_init.sh\""
alias date-stop="date down"
alias date-start="date-pull; date-stop; date up --build"
alias date-start-detached="date-pull; date up -d --build"
alias date-createsuperuser="date-manage createsuperuser"
alias date-pull="date pull"
alias date-seed-gallery="date-manage seed_gallery"
alias date-seed-gallery-clear="date-manage seed_gallery --clear"

alias date-all="docker compose --project-directory \"${DATE_WEBSITE_DIR}\" -f \"${DATE_WEBSITE_DIR}/docker-compose.dev-all.yml\""
alias date-all-manage="date-all run web python /code/manage.py"
alias date-all-start="date-all up --build"
alias date-all-stop="date-all down"
alias date-all-cleaninit="COMPOSE_FILE_PATH=\"docker-compose.dev-all.yml\" \"${DATE_WEBSITE_DIR}/scripts/clean_init.sh\""
alias date-all-seed-gallery="date-all-manage seed_gallery"
alias date-all-seed-gallery-clear="date-all-manage seed_gallery --clear"

date-test() {
    docker compose --project-directory "${DATE_WEBSITE_DIR}" run -e TEST=1 web /bin/bash -c './wait-for-postgres.sh db:5432 && python /code/manage.py test "$@"' -- "$@"
}
