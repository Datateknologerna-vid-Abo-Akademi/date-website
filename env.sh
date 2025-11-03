#!/usr/bin/env bash
# shellcheck disable=SC1091

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_MODE="dev"
REQUESTED_MODE="${1:-$DEFAULT_MODE}"

if [ -n "${2:-}" ]; then
    echo "Usage: source env.sh [dev|prod|path/to/env]" >&2
    return 1 2>/dev/null || exit 1
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

ENV_FILE="$(resolve_env_file "$REQUESTED_MODE")" || {
    return 1 2>/dev/null || exit 1
}

case "$REQUESTED_MODE" in
    dev|prod)
        ENV_MODE="$REQUESTED_MODE"
        ;;
    *)
        ENV_MODE="custom"
        ;;
esac

set -a
. "${ENV_FILE}"
set +a

if [ "$ENV_MODE" = "prod" ]; then
    export DATE_DEVELOP="False"
elif [ "$ENV_MODE" = "dev" ]; then
    export DATE_DEVELOP="${DATE_DEVELOP:-True}"
fi

if [ "${DATE_DEVELOP:-True}" = "False" ]; then
    export COMPOSE_FILE_PATH="docker-compose.prod.yml"
else
    export COMPOSE_FILE_PATH="docker-compose.yml"
fi

alias date="docker-compose -f \"${COMPOSE_FILE_PATH}\""
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
    docker-compose run -e TEST=1 web /bin/bash -c './wait-for-postgres.sh db:5432 && python /code/manage.py test "$@"'
}
