#!/usr/bin/env bash

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

set -a
. "${ENV_FILE}"
set +a

if [ "$REQUESTED_MODE" = "prod" ]; then
    export COMPOSE_FILE_PATH="docker-compose.prod.yml"
else
    export COMPOSE_FILE_PATH="docker-compose.yml"
fi

alias stack="docker compose -f \"${SCRIPT_DIR}/${COMPOSE_FILE_PATH}\""
alias stack-start="stack up --build"
alias stack-start-detached="stack up -d --build"
alias stack-stop="stack down"
alias stack-logs="stack logs -f"
alias stack-ps="stack ps"

alias stack-backend-shell="stack exec backend sh"
alias stack-backend-manage="stack exec backend python /code/manage.py"
alias stack-frontend-shell="stack exec frontend sh"

stack-test-backend() {
    stack exec backend python /code/manage.py test "$@"
}

stack-test-frontend() {
    stack exec frontend npm run lint "$@"
}

stack-qa-associations() {
    python "${SCRIPT_DIR}/scripts/association_qa.py" "$@"
}
