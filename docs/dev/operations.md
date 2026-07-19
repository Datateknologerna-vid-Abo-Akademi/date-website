# Operations & Maintenance Notes

## Purpose

This guide collects the repo's maintenance scripts and the situations where they should be used. Use it together with the main README for day-to-day operational work.

## Environment Assumptions

Most scripts assume:

- you run them from the repository root or via their documented path
- Docker is installed and available in `PATH`
- you are not running the script from inside a container
- `.env` exists in the repository root

Unless a script says otherwise, prefer running it from a Bash-compatible shell.

## Admin Theme

Set `USE_UNFOLD=True` in `.env` to run Django admin with the Unfold theme. Leave it unset or set it to `False` to use the classic Django admin.

Changing this value requires restarting or recreating the Django containers, because admin apps, widgets, templates, and static assets are selected when Django starts.

## Fixture Reset and Local Seed Data

### `date-cleaninit` / `scripts/clean_init.sh`

Use this when you want to reset local development data to a known starting point.

What it does:

- warns before destructive actions
- optionally deletes uploaded media under `media/archive` and `media/pdfs`
- uses the repository `.env` through Docker Compose
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
| pulterit    | http://localhost:8004 |
| sf          | http://localhost:8005 |
| impuls      | http://localhost:8006 |

The database is exposed on host port `5433` to avoid conflicting with the regular dev stack on `5432`.

#### Helpers (after `source env.sh` or adding them to your shell config)

The helpers use the nearest `date-website` checkout from your current directory, falling back to `DATE_WEBSITE_DIR` when you are outside a checkout.

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
- The `date-all-cleaninit` alias passes `COMPOSE_FILE_PATH=docker-compose.dev-all.yml` directly to `clean_init.sh` so it targets the dev-all stack.

## Backups and Database Upgrades

### `scripts/backup_postgres.sh`

Use this for routine PostgreSQL backups.

Typical usage:

```bash
./scripts/backup_postgres.sh [dev|prod|path/to/env] [output_dir]
```

Behavior:

- resolves an environment file with `scripts/lib/date_env.sh`
- keeps the old `./scripts/backup_postgres.sh [output_dir]` form for local ad-hoc backups
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
- verifies the current PostgreSQL data directory is on a mounted volume before removing anything
- tears down volumes
- updates `DATE_POSTGRESQL_VERSION`
- recreates the database container
- recreates the target database through `template1`, which also works when `DB_DATABASE=postgres`
- restores the SQL dump
- validates that the restored database is usable and still contains the expected schema footprint

The Compose db service also wraps the upstream Postgres entrypoint so existing volumes that were initialized with the legacy `/var/lib/postgresql/data` layout are moved into the configured `PGDATA` subdirectory on first boot.

This script is destructive if used incorrectly. Read the warnings in the README before running it.

## Project Variant Checks

### `scripts/check_project_variants.py`

Use this after shared settings, template/static path, URL configuration, or
cross-association app changes.

```bash
uv run python scripts/check_project_variants.py
```

It runs `manage.py check` for `date`, `kk`, `biocum`, and `pulterit`. Pass one
or more project names as arguments to narrow the run.

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

- `python manage.py import_wordpress_export <xml_path>`
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

### `import_wordpress_export`

Use this management command as a one-off migration helper for moving the SF association site from WordPress into the existing Django content apps. It is not intended to be a reusable generic WordPress importer; several defaults and parsing rules assume the SF export shape and `sfklubben.fi` upload paths.

It maps SF WordPress posts to `news.Post`, WordPress pages to `staticpages.StaticPage`, and the A&O/Politicus publication pages to `publications.PDFFile` rows grouped into their own publication collections. Other uploaded PDFs are copied as media and stay linked from imported pages, navigation, or app-specific importers such as `exambank`; they are not imported as publications. Local development writes to `MEDIA_ROOT`; when `USE_S3=True`, imported media uses the configured public media storage so links in imported CKEditor content remain public.

Typical SF import:

```bash
PROJECT_NAME=sf python manage.py import_wordpress_export sf-klubben.WordPress.2026-05-09.xml \
  --media-dir sfklubben-export-local/assets/sfklubben.fi \
  --author wp-import \
  --import-nav \
  --replace-nav \
  --import-gallery-redirects \
  --replace-gallery-redirects \
  --import-functionaries
```

Run `--dry-run` first to inspect planned counts. The command matches rows by slug; existing rows are skipped unless `--update-existing` is passed. Publications import reads Issuu links from the exported A&O page (`/ao/`) and stores them as external redirects with the table cover image as `cover_image` when that uploaded image is available. It also reads the exported Politicus page (`/politicus/`), stores Issuu years as external redirects, and stores older linked PDF years as local PDF-backed publications when the target PDF is available in imported media. A&O and Politicus each get their own publication collection and collection logo from the WordPress media library; pass `--skip-publications` to skip those rows. Navigation import reads the WordPress `actual` menu by default; use `--nav-menu <slug>` to import another exported menu. Gallery redirect import reads Google Photos/Drive links from the exported `bildgalleriet` and `gamla-bilder` pages and creates redirect-only `gallery.Album` rows. By default the importer also fetches each share URL's `og:image` preview and stores it as the album thumbnail; pass `--skip-gallery-thumbnails` to suppress those network calls (e.g. for offline imports). Albums that already have a thumbnail are left untouched, and fetch failures are logged and counted in the report rather than aborting the import. Pass `--import-exam-archive` to read the WordPress `tentarkiv` rtbs_tabs payload (a PHP-serialized list of subject tabs) and create one `exambank.ExamArchive` per tab, with one `exambank.ExamFile` per linked PDF (resolved to its already-imported storage path). Combine with `--replace-exam-archive` to clear existing exam archives first. Pass `--import-functionaries` to parse the WordPress `funktionarer` page into board `functionaries.FunctionaryRole` rows and name-only `functionaries.Functionary` rows; it preserves any existing matching member-linked functionary entries. Combine with `--replace-functionaries` only when you intentionally want to clear all existing functionaries first. It writes a JSON report next to the XML by default.

### `import_impuls_static_archive`

Use this one-off migration helper for the Impuls static WordPress archive stored in the repository root under `impuls/`. Unlike the SF importer, this reads the captured static tree: it prefers REST page JSON under `wp-json/wp/v2/pages/`, falls back to canonical HTML pages, parses the current blog listing into `news.Post` rows, imports referenced uploads into public media storage, and can recreate the captured WordPress navigation.

Run a dry-run first:

```bash
PROJECT_NAME=impuls python manage.py import_impuls_static_archive --dry-run --import-nav
```

Then import into a disposable or backed-up target database:

```bash
PROJECT_NAME=impuls python manage.py import_impuls_static_archive \
  --import-nav \
  --replace-nav \
  --author wp-import
```

The command matches pages and posts by slug. Existing rows are skipped unless `--update-existing` is passed. It writes `impuls/impuls-import-report.json` by default after a non-dry run.

## Recommended Operator Checklist

### After splitting apps

Before running `manage.py remove_stale_contenttypes` after this split, grant the replacement permissions for the new apps:

- `gallery.*` for photo albums and photos
- `exambank.*` for exam archives and files
- `instagram.*` for Instagram URLs
- `harassment.*` for harassment reports and recipients
- `functionaries.*` for functionary roles and assignments

The admin keeps temporary fallbacks to the old `archive`, `social`, and `members` permissions while the stale content types still exist. Those fallbacks disappear once stale content types and their permissions are removed.

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
