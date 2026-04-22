#!/usr/bin/env bash

date_resolve_env_file() {
    local project_root="$1"
    local mode="$2"
    local -a candidates=()

    case "$mode" in
        dev)
            candidates=(
                "${project_root}/.env"
                "${project_root}/.env.example"
            )
            ;;
        prod)
            candidates=(
                "${project_root}/.env.prod"
                "${project_root}/.env"
                "${project_root}/.env.example"
            )
            ;;
        *)
            if [ -f "$mode" ]; then
                echo "$mode"
                return 0
            fi

            if [ -f "${project_root}/$mode" ]; then
                echo "${project_root}/$mode"
                return 0
            fi

            echo "Environment file '$mode' not found" >&2
            return 1
            ;;
    esac

    local candidate
    for candidate in "${candidates[@]}"; do
        if [ -f "$candidate" ]; then
            echo "$candidate"
            return 0
        fi
    done

    echo "No suitable environment file found for mode '$mode'" >&2
    return 1
}

date_resolve_env_mode() {
    local requested_mode="$1"
    local config_path="$2"
    local config_name
    config_name="$(basename "$config_path")"

    case "$requested_mode" in
        prod|dev)
            echo "$requested_mode"
            ;;
        *)
            case "$config_name" in
                .env.prod)
                    echo "prod"
                    ;;
                .env)
                    echo "dev"
                    ;;
                *)
                    echo "custom"
                    ;;
            esac
            ;;
    esac
}

date_apply_env_mode() {
    local resolved_mode="$1"

    case "$resolved_mode" in
        prod)
            export DATE_DEVELOP="${DATE_DEVELOP:-False}"
            ;;
        dev)
            export DATE_DEVELOP="${DATE_DEVELOP:-True}"
            ;;
    esac
}

date_resolve_compose_file() {
    local resolved_mode="${1:-}"
    local compose_file_override="${2:-}"

    if [ -n "$compose_file_override" ]; then
        echo "$compose_file_override"
    elif [ "$resolved_mode" = "prod" ]; then
        echo "docker-compose.prod.yml"
    else
        echo "docker-compose.yml"
    fi
}

date_read_env_value() {
    local config_file="$1"
    local env_name="$2"

    (
        unset "$env_name"
        set -a
        # shellcheck disable=SC1090
        source "$config_file"
        set +a
        printf '%s' "${!env_name:-}"
    )
}
