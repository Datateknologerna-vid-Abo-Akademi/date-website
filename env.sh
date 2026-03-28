#!/usr/bin/env bash
# shellcheck disable=SC1091

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/scripts/lib/date_env.sh"
DEFAULT_MODE="dev"
REQUESTED_MODE="${1:-$DEFAULT_MODE}"

if [ -n "${2:-}" ]; then
    echo "Usage: source env.sh [dev|prod|path/to/env]" >&2
    return 1 2>/dev/null || exit 1
fi

ENV_FILE="$(date_resolve_env_file "$SCRIPT_DIR" "$REQUESTED_MODE")" || {
    return 1 2>/dev/null || exit 1
}
ENV_MODE="$(date_resolve_env_mode "$REQUESTED_MODE" "$ENV_FILE")"

set -a
. "${ENV_FILE}"
set +a

date_apply_env_mode "$ENV_MODE"

export COMPOSE_FILE_PATH="$(date_resolve_compose_file)"

alias date="docker compose -f \"${COMPOSE_FILE_PATH}\""
alias date-manage="date run web python /code/manage.py"
alias date-migrate="date-manage migrate --noinput"
alias date-makemigrations="date-manage makemigrations"
alias date-collectstatic="date-manage collectstatic"
alias date-stop="date down"
alias date-start="date-pull; date-stop; date up --build"
alias date-start-detached="date-pull; date up -d --build"
alias date-createsuperuser="date-manage createsuperuser"
alias date-pull="date pull"

date-test() {
    docker compose run -e TEST=1 web /bin/bash -c './wait-for-postgres.sh db:5432 && python /code/manage.py test "$@"'
}
