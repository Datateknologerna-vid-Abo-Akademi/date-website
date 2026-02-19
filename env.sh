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

DATE_COMPOSE_FILE="${SCRIPT_DIR}/${COMPOSE_FILE_PATH}"
DATE_PROJECT_STATE_FILE="${SCRIPT_DIR}/.date-active-project"
DATE_LEGACY_OVERRIDE_FILE="${SCRIPT_DIR}/.tmp.legacy-visual.override.yml"

for _date_helper_alias in \
    date \
    date-start \
    date-start-both \
    date-start-detached \
    date-stop-both \
    date-stop \
    date-logs \
    date-ps \
    date-backend-shell \
    date-manage \
    date-init-demo \
    date-frontend-shell
do
    unalias "${_date_helper_alias}" 2>/dev/null || true
done
unset _date_helper_alias

_date_is_known_association() {
    case "${1:-}" in
        date|kk|biocum|on|demo)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

_date_parse_project_arg() {
    DATE_PROJECT_OVERRIDE=""
    if [ "${1:-}" = "--project" ] || [ "${1:-}" = "-p" ]; then
        if [ -z "${2:-}" ]; then
            echo "Missing value for ${1}." >&2
            return 1
        fi
        DATE_PROJECT_OVERRIDE="$2"
        shift 2
    elif _date_is_known_association "${1:-}"; then
        DATE_PROJECT_OVERRIDE="$1"
        shift
    fi
    DATE_REMAINING_ARGS=("$@")
    return 0
}

_date_effective_project() {
    if [ -n "${1:-}" ]; then
        printf '%s\n' "$1"
        return 0
    fi
    if [ -n "${PROJECT_NAME:-}" ]; then
        printf '%s\n' "$PROJECT_NAME"
        return 0
    fi
    printf '%s\n' "date"
}

_date_set_recorded_project() {
    if [ -n "${1:-}" ]; then
        printf '%s\n' "$1" > "$DATE_PROJECT_STATE_FILE"
    fi
}

_date_get_recorded_project() {
    if [ -f "$DATE_PROJECT_STATE_FILE" ]; then
        head -n 1 "$DATE_PROJECT_STATE_FILE"
    fi
}

_date_detect_live_project() {
    if ! command -v curl >/dev/null 2>&1; then
        return 1
    fi
    local app_origin="${NEXT_PUBLIC_APP_ORIGIN:-http://localhost:8080}"
    local meta_url="${app_origin%/}/api/v1/meta/site"
    local body
    body="$(curl -fsS --max-time 4 "$meta_url" 2>/dev/null)" || return 1
    local project_name
    project_name="$(printf '%s' "$body" | sed -n 's/.*"project_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"
    [ -n "$project_name" ] || return 1
    printf '%s\n' "$project_name"
}

_date_is_prod_mode() {
    if [ "${REQUESTED_MODE:-}" = "prod" ]; then
        return 0
    fi
    case "${COMPOSE_FILE_PATH:-}" in
        *prod*)
            return 0
            ;;
    esac
    case "${DATE_DEVELOP:-}" in
        false|False|FALSE|0|no|No|NO)
            return 0
            ;;
    esac
    return 1
}

_date_confirm_prod_reset() {
    local target_project="$1"
    local live_project="$2"
    local assume_yes="${3:-0}"

    if [ "$assume_yes" -eq 1 ] || [ "${DATE_INIT_DEMO_ASSUME_YES:-}" = "1" ]; then
        return 0
    fi

    if [ ! -t 0 ]; then
        echo "Refusing prod reset in non-interactive mode without --yes." >&2
        echo "Run with: date-init-demo --reset --allow-prod-reset --yes" >&2
        return 1
    fi

    echo "PROD RESET CONFIRMATION"
    echo "Target association: ${target_project}"
    if [ -n "$live_project" ]; then
        echo "Currently running: ${live_project}"
    fi
    echo "This will flush database data."
    printf "Type WIPE to continue: "
    local confirmation
    read -r confirmation
    if [ "$confirmation" != "WIPE" ]; then
        echo "Confirmation failed. Aborting reset." >&2
        return 1
    fi
    return 0
}

_date_compose() {
    local project_name="$1"
    shift
    if [ -n "$project_name" ]; then
        PROJECT_NAME="$project_name" docker compose -f "${DATE_COMPOSE_FILE}" "$@"
    else
        docker compose -f "${DATE_COMPOSE_FILE}" "$@"
    fi
}

_date_write_legacy_override() {
    cat > "${DATE_LEGACY_OVERRIDE_FILE}" <<'YAML'
services:
  backend:
    environment:
      LEGACY_TEMPLATE_ROUTES_ENABLED: "True"
    ports:
      - "8001:8000"
YAML
}

_date_compose_with_legacy() {
    local project_name="$1"
    shift
    _date_write_legacy_override || return 1
    if [ -n "$project_name" ]; then
        PROJECT_NAME="$project_name" docker compose -f "${DATE_COMPOSE_FILE}" -f "${DATE_LEGACY_OVERRIDE_FILE}" "$@"
    else
        docker compose -f "${DATE_COMPOSE_FILE}" -f "${DATE_LEGACY_OVERRIDE_FILE}" "$@"
    fi
}

date() {
    _date_compose "" "$@"
}

date-project() {
    if [ $# -lt 2 ]; then
        echo "Usage: date-project <project_name> <docker-compose args...>" >&2
        return 1
    fi
    local project_name="$1"
    shift
    _date_compose "$project_name" "$@"
}

date-start() {
    _date_parse_project_arg "$@" || return 1
    local target_project
    target_project="$(_date_effective_project "$DATE_PROJECT_OVERRIDE")"
    _date_compose "$DATE_PROJECT_OVERRIDE" up --build "${DATE_REMAINING_ARGS[@]}" &&
        _date_set_recorded_project "$target_project"
}

date-start-both() {
    _date_parse_project_arg "$@" || return 1
    if _date_is_prod_mode; then
        echo "date-start-both is disabled in prod mode." >&2
        return 1
    fi

    local target_project
    target_project="$(_date_effective_project "$DATE_PROJECT_OVERRIDE")"
    _date_compose_with_legacy "$DATE_PROJECT_OVERRIDE" up -d --build "${DATE_REMAINING_ARGS[@]}" &&
        _date_set_recorded_project "$target_project"
    local compose_exit=$?
    if [ "$compose_exit" -eq 0 ]; then
        local app_origin="${NEXT_PUBLIC_APP_ORIGIN:-http://localhost:8080}"
        echo "Decoupled frontend: ${app_origin%/}/"
        echo "Legacy templates:   http://localhost:8001/"
        echo "Association:        ${target_project}"
    fi
    return "$compose_exit"
}

date-start-detached() {
    _date_parse_project_arg "$@" || return 1
    local target_project
    target_project="$(_date_effective_project "$DATE_PROJECT_OVERRIDE")"
    _date_compose "$DATE_PROJECT_OVERRIDE" up -d --build "${DATE_REMAINING_ARGS[@]}" &&
        _date_set_recorded_project "$target_project"
}

date-stop-both() {
    _date_parse_project_arg "$@" || return 1
    _date_compose_with_legacy "$DATE_PROJECT_OVERRIDE" down "${DATE_REMAINING_ARGS[@]}"
}

date-stop() {
    _date_parse_project_arg "$@" || return 1
    _date_compose "$DATE_PROJECT_OVERRIDE" down "${DATE_REMAINING_ARGS[@]}"
}

date-logs() {
    _date_parse_project_arg "$@" || return 1
    _date_compose "$DATE_PROJECT_OVERRIDE" logs -f "${DATE_REMAINING_ARGS[@]}"
}

date-ps() {
    _date_parse_project_arg "$@" || return 1
    _date_compose "$DATE_PROJECT_OVERRIDE" ps "${DATE_REMAINING_ARGS[@]}"
}

date-backend-shell() {
    _date_parse_project_arg "$@" || return 1
    _date_compose "$DATE_PROJECT_OVERRIDE" exec backend sh "${DATE_REMAINING_ARGS[@]}"
}

date-manage() {
    _date_parse_project_arg "$@" || return 1
    if [ "${#DATE_REMAINING_ARGS[@]}" -eq 0 ]; then
        echo "Usage: date-manage [--project <name>|<known-association>] <manage.py args...>" >&2
        return 1
    fi
    _date_compose "$DATE_PROJECT_OVERRIDE" exec backend python /code/manage.py "${DATE_REMAINING_ARGS[@]}"
}

date-init-demo() {
    _date_parse_project_arg "$@" || return 1
    local -a project_args=()
    local -a seed_args=()
    local reset_mode="auto"
    local allow_prod_reset=0
    local assume_yes=0
    local no_reset_reason=""
    local arg

    for arg in "${DATE_REMAINING_ARGS[@]}"; do
        case "$arg" in
            --reset)
                reset_mode="always"
                ;;
            --no-reset|--keep-db)
                reset_mode="never"
                ;;
            --allow-prod-reset)
                allow_prod_reset=1
                ;;
            --yes|-y)
                assume_yes=1
                ;;
            *)
                seed_args+=("$arg")
                ;;
        esac
    done

    local target_project
    target_project="$(_date_effective_project "$DATE_PROJECT_OVERRIDE")"
    local live_project
    live_project="$(_date_detect_live_project 2>/dev/null || true)"
    local recorded_project
    recorded_project="$(_date_get_recorded_project)"
    local project_changed=0

    if [ -n "$live_project" ]; then
        [ "$live_project" != "$target_project" ] && project_changed=1
    elif [ -n "$recorded_project" ]; then
        [ "$recorded_project" != "$target_project" ] && project_changed=1
    else
        project_changed=1
    fi

    if [ -z "$live_project" ] || [ "$live_project" != "$target_project" ]; then
        echo "Starting stack for association '$target_project'..."
        _date_compose "$target_project" up -d --build --force-recreate backend asgi celery frontend proxy || return 1
    fi

    if [ -n "$DATE_PROJECT_OVERRIDE" ]; then
        project_args=(--project "$DATE_PROJECT_OVERRIDE")
    fi

    local do_reset=0
    case "$reset_mode" in
        always)
            do_reset=1
            ;;
        never)
            do_reset=0
            ;;
        auto|*)
            do_reset="$project_changed"
            ;;
    esac

    if _date_is_prod_mode && [ "$reset_mode" = "auto" ]; then
        do_reset=0
        no_reset_reason="prod safety: auto-reset disabled"
    fi

    if _date_is_prod_mode && [ "$do_reset" -eq 1 ]; then
        if [ "$allow_prod_reset" -ne 1 ] && [ "${DATE_ALLOW_PROD_RESET:-}" != "1" ]; then
            echo "Refusing database reset in prod mode." >&2
            echo "To force reset explicitly, use: date-init-demo --reset --allow-prod-reset" >&2
            return 1
        fi
        _date_confirm_prod_reset "$target_project" "$live_project" "$assume_yes" || return 1
    fi

    if [ "$do_reset" -eq 1 ]; then
        echo "Association change detected (or unknown state). Seeding demo with database reset."
        if date-manage "${project_args[@]}" migrate --noinput &&
            date-manage "${project_args[@]}" seed_visual_demo --reset "${seed_args[@]}"; then
            _date_set_recorded_project "$target_project"
        else
            echo "Reset seed failed, retrying once after short wait..."
            sleep 3
            date-manage "${project_args[@]}" migrate --noinput &&
                date-manage "${project_args[@]}" seed_visual_demo --reset "${seed_args[@]}" &&
                _date_set_recorded_project "$target_project"
        fi
    else
        if [ -n "$no_reset_reason" ]; then
            echo "Seeding demo without database reset (${no_reset_reason})."
        else
            echo "Association unchanged. Seeding demo without database reset. Use --reset to force reset."
        fi
        date-manage "${project_args[@]}" migrate --noinput &&
            date-manage "${project_args[@]}" seed_visual_demo "${seed_args[@]}" &&
            _date_set_recorded_project "$target_project"
    fi
}

date-frontend-shell() {
    _date_parse_project_arg "$@" || return 1
    _date_compose "$DATE_PROJECT_OVERRIDE" exec frontend sh "${DATE_REMAINING_ARGS[@]}"
}

date-test-backend() {
    date exec backend python /code/manage.py test "$@"
}

date-test-frontend() {
    date exec frontend npm run lint "$@"
}

date-qa-associations() {
    python "${SCRIPT_DIR}/scripts/association_qa.py" "$@"
}
