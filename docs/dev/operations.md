# Operations & Maintenance Notes

## Purpose

This guide collects the repo's maintenance scripts and the situations where they should be used. Use it together with the main README for day-to-day operational work.

## Environment Assumptions

Most scripts assume:

- you run them from the repository root or via their documented path
- Docker is installed and available in `PATH`
- you are not running the script from inside a container
- the environment is resolved through `env.sh` or the same helper logic used by `scripts/lib/date_env.sh`

Unless a script says otherwise, prefer running it from a Bash-compatible shell.

## Fixture Reset and Local Seed Data

### `date-cleaninit` / `scripts/clean_init.sh`

Use this when you want to reset local development data to a known starting point.

What it does:

- warns before destructive actions
- optionally deletes uploaded media under `media/archive` and `media/pdfs`
- loads the development environment through `env.sh dev`
- rebuilds and starts the database service
- recreates the PostgreSQL database from scratch
- runs migrations
- loads fixture data through `scripts/load_all_fixtures.sh`
- resets the passwords for `admin`, `freshman`, and `member` to `admin`

Use this for:

- onboarding a new developer
- recovering from broken local test data
- smoke-testing content-heavy features against a predictable fixture set

Do not use this on environments that contain real data.

### `scripts/load_all_fixtures.sh`

This is the fixture loader used by `clean_init.sh`.

It loads:

- `fixtures/members.json`
- `fixtures/ads.json`
- generated dynamic fixtures from `scripts/generate_dynamic_fixtures.py`

Treat the generated fixture output as disposable development data.

## Multi-Association Dev Stack

### `docker-compose.dev-all.yml` / `date-all-*` aliases

Use this when you need to run all associations simultaneously for style comparison or cross-association testing.

Each association gets its own web container on a dedicated port, sharing one PostgreSQL database and one Redis instance:

| Association | URL                   |
|-------------|-----------------------|
| biocum      | http://localhost:8001 |
| date        | http://localhost:8002 |
| kk          | http://localhost:8003 |
| on          | http://localhost:8004 |
| pulterit    | http://localhost:8005 |

The database is exposed on host port `5433` to avoid conflicting with the regular dev stack on `5432`.

#### Aliases (after `source env.sh`)

```bash
date-all-start       # build and start all containers
date-all-stop        # tear everything down
date-all-cleaninit   # reset to fixture data against the dev-all stack
```

#### How it works

An `init` container runs once on startup — it waits for PostgreSQL, then runs `migrate`, `collectstatic`, and `compilemessages` using `PROJECT_NAME=date`. All web containers wait for `init` to complete before accepting requests.

The `web` service (port 8002) is named `web` specifically so `clean_init.sh` can target it when running `date-all-cleaninit`.

#### Notes

- Static files are collected once by `init` at startup. If you change CSS or JS, restart with `date-all-start` to pick up the changes.
- The `date-all-cleaninit` alias passes `COMPOSE_FILE_PATH=docker-compose.dev-all.yml` before sourcing `env.sh`, which `clean_init.sh` preserves to avoid being overridden.

## Backups and Database Upgrades

### `scripts/backup_postgres.sh`

Use this for routine PostgreSQL backups.

Typical usage:

```bash
./scripts/backup_postgres.sh [dev|prod|path/to/env] [output_dir]
```

Behavior:

- resolves the environment file with the same lookup rules as `env.sh`
- starts the `db` service if needed
- waits for PostgreSQL readiness
- creates a plain SQL dump
- writes a JSON manifest next to the dump
- includes a SHA-256 checksum in the manifest

Use this before risky schema or infrastructure work, and especially before any major PostgreSQL version upgrade.

For Kubernetes deployments, the Helm chart provides a PostgreSQL backup CronJob that can upload compressed dumps to Backblaze B2. See [Kubernetes and k3s Deployment Notes](kubernetes.md) for the k3s backup workflow.

### `update-postgres.sh`

Use this only for major PostgreSQL version upgrades.

It:

- validates the target env file
- runs `scripts/backup_postgres.sh`
- tears down volumes
- updates `DATE_POSTGRESQL_VERSION`
- recreates the database container
- restores the SQL dump
- validates that the restored database is usable

This script is destructive if used incorrectly. Read the warnings in the README before running it.

## Translation Maintenance

### `scripts/validate_translations.py`

Use this to validate locale completeness before merging translation-heavy work.

```bash
python scripts/validate_translations.py
```

It checks each required locale catalog for:

- missing `django.po` files
- fuzzy entries
- untranslated entries

This is useful after `makemessages`, after large translation edits, and before release branches.

## Data Import / Export Helpers

These scripts are more task-specific and should usually be run only by someone familiar with the target app and data shape:

- `scripts/import_alumni.py`
- `scripts/export_subscription_status.py`
- `scripts/export_ctf_guesses.py`
- `scripts/merge_events.py`
- `scripts/bulk_send_confirmation.py`
- `scripts/resend_signup_emails.py`
- `scripts/mass_upload.py`
- `scripts/s3_upload.py`
- `scripts/s3_populate_db.py`
- `scripts/create_album.py`

Before using one of these on shared or production-like data:

- inspect the script first
- verify the target environment file
- confirm whether the script is idempotent
- make a backup if the script mutates stored data

## Recommended Operator Checklist

### Before destructive operations

1. Confirm which env file you are targeting.
2. Make a backup.
3. Verify whether the script mutates local-only data, shared data, or production data.
4. Make sure containers are using the expected compose file.

### After maintenance work

1. Restart the relevant services.
2. Run a minimal smoke test on the public site and admin.
3. If translations were touched, run the translation validator and preview one translated locale.
4. Update the docs if the workflow changed.
