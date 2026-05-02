#!/usr/bin/env bash

if [ -n "${BASH_SOURCE[0]:-}" ]; then
    DATE_WEBSITE_SOURCE="${BASH_SOURCE[0]}"
elif [ -n "${ZSH_VERSION:-}" ]; then
    DATE_WEBSITE_SOURCE="${(%):-%x}"
else
    DATE_WEBSITE_SOURCE="$0"
fi

DATE_WEBSITE_DIR="${DATE_WEBSITE_DIR:-$(cd "$(dirname "$DATE_WEBSITE_SOURCE")" && pwd)}"

if [ -n "${1:-}" ]; then
    echo "Usage: source env.sh" >&2
    echo "COMPOSE_FILE in .env selects the stack; env.sh only registers helper aliases." >&2
    return 1 2>/dev/null || exit 1
fi

unalias date date-manage date-migrate date-makemigrations date-collectstatic \
    date-cleaninit date-stop date-start date-start-detached date-createsuperuser \
    date-pull date-seed-gallery date-seed-gallery-clear date-all date-all-manage \
    date-all-start date-all-stop date-all-cleaninit date-all-seed-gallery \
    date-all-seed-gallery-clear date-backup date-restore date-sync-dev-env \
    date-sync-prod-env date-setup 2>/dev/null || true

# Resolve the checkout to operate on. This lets globally installed helpers
# follow the current working directory while still having DATE_WEBSITE_DIR as a
# fallback when run outside any checkout.
_date_website_project_dir() {
    local dir
    dir="$PWD"

    while [ "$dir" != "/" ]; do
        if [ -f "$dir/env.sh" ] && [ -f "$dir/docker-compose.yml" ] && [ -f "$dir/manage.py" ]; then
            printf '%s\n' "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done

    if [ -n "${DATE_WEBSITE_DIR:-}" ] && [ -d "$DATE_WEBSITE_DIR" ]; then
        printf '%s\n' "$DATE_WEBSITE_DIR"
        return 0
    fi

    echo "Could not find a date-website checkout. cd into one or set DATE_WEBSITE_DIR." >&2
    return 1
}

date() {
    local project_dir
    project_dir="$(_date_website_project_dir)" || return
    docker compose --project-directory "$project_dir" "$@"
}

date-manage() {
    date run web python /code/manage.py "$@"
}

date-migrate() {
    date-manage migrate --noinput "$@"
}

date-makemigrations() {
    date-manage makemigrations "$@"
}

date-collectstatic() {
    date-manage collectstatic "$@"
}

date-cleaninit() {
    local project_dir
    project_dir="$(_date_website_project_dir)" || return
    "$project_dir/scripts/clean_init.sh" "$@"
}

date-stop() {
    date down "$@"
}

date-start() {
    date-pull
    date-stop
    date up --build "$@"
}

date-start-detached() {
    date-pull
    date up -d --build "$@"
}

date-createsuperuser() {
    date-manage createsuperuser "$@"
}

date-pull() {
    date pull "$@"
}

date-seed-gallery() {
    date-manage seed_gallery "$@"
}

date-seed-gallery-clear() {
    date-manage seed_gallery --clear "$@"
}

date-all() {
    local project_dir
    project_dir="$(_date_website_project_dir)" || return
    docker compose --project-directory "$project_dir" -f "$project_dir/docker-compose.dev-all.yml" "$@"
}

date-all-manage() {
    date-all run web python /code/manage.py "$@"
}

date-all-start() {
    date-all up "$@"
}

date-all-stop() {
    date-all down "$@"
}

date-all-cleaninit() {
    local project_dir
    project_dir="$(_date_website_project_dir)" || return
    COMPOSE_FILE_PATH="docker-compose.dev-all.yml" "$project_dir/scripts/clean_init.sh" "$@"
}

date-all-seed-gallery() {
    date-all-manage seed_gallery "$@"
}

date-all-seed-gallery-clear() {
    date-all-manage seed_gallery --clear "$@"
}

date-backup() {
    local project_dir
    project_dir="$(_date_website_project_dir)" || return
    "$project_dir/scripts/backup_postgres.sh" "$@"
}

date-restore() {
    local project_dir
    project_dir="$(_date_website_project_dir)" || return
    "$project_dir/scripts/restore_postgres.sh" "$@"
}

date-sync-dev-env() {
    local project_dir
    local env_file
    project_dir="$(_date_website_project_dir)" || return
    env_file="$project_dir/.env"

    if [ -f "$env_file" ] && [ "${DATE_FORCE_DEV_ENV_SYNC:-}" != "1" ]; then
        if grep -Eq '^[[:space:]]*COMPOSE_FILE=["'\'']?docker-compose\.prod\.yml|^[[:space:]]*DATE_DEVELOP=["'\'']?[Ff]alse|^[[:space:]]*DATE_DEBUG=["'\'']?[Ff]alse|^[[:space:]]*UNFOLD_ENVIRONMENT_LABEL=["'\'']?Production' "$env_file"; then
            echo "Refusing to sync development env over a production-looking .env." >&2
            echo "Use date-sync-prod-env for production, or set DATE_FORCE_DEV_ENV_SYNC=1 to override." >&2
            return 1
        fi
    fi

    "$project_dir/scripts/sync_env_from_template.sh" "$@" "$project_dir/.env.example" "$project_dir/.env"
}

date-sync-prod-env() {
    local project_dir
    project_dir="$(_date_website_project_dir)" || return
    "$project_dir/scripts/sync_env_from_template.sh" "$@" "$project_dir/.env.prod.example" "$project_dir/.env"
}

date-setup() {
    local project_dir
    project_dir="$(_date_website_project_dir)" || return

    if [ ! -f "$project_dir/.env" ]; then
        cp "$project_dir/.env.example" "$project_dir/.env"
        echo "Created .env from .env.example — edit it before continuing."
    else
        echo ".env already exists, skipping."
    fi

    git -C "$project_dir" config core.hooksPath .githooks
    echo "Git hooks installed."

    "$project_dir/scripts/clean_init.sh" --yes

    echo "Run 'date-start' or 'date-start-detached' to start the stack."
}

date-test() {
    local project_dir
    project_dir="$(_date_website_project_dir)" || return
    docker compose --project-directory "$project_dir" run -e TEST=1 web /bin/bash -c './wait-for-postgres.sh db:5432 && python /code/manage.py test "$@"' -- "$@"
}
