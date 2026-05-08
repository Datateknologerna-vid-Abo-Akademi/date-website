# Agent Guide

Guidance for AI coding agents working in this repository.

## Project Snapshot

DaTe Website 2.0 is a Django 6.0 / Python 3.14 project for the Datateknologerna vid Abo Akademi public site, member tooling, alumni flows, polls, events, publications, and association-specific variants.

The runtime stack is Docker Compose in development and production, with PostgreSQL, Valkey/Redis, Celery, Channels/Daphne, Gunicorn, optional S3-compatible storage, and optional shared Prometheus/Grafana monitoring.

Mainline development happens on `main`. QA and production are promoted image environments, not long-lived branches.

## First Places To Read

- `README.md`: local setup, helper aliases, Compose workflow, tests, deployment, backups, PostgreSQL upgrades, and i18n.
- `CONTRIBUTING.md`: branch, review, docs, and squash-merge expectations.
- `CHANGELOG.md`: notable changes and release history.
- `docs/index.md`: published documentation index.
- `docs/dev/*.md`: implementation notes for each app and cross-cutting system.
- `docs/admin/*.md`: editor/admin behavior that code changes must preserve.
- `docs/dev/operations.md`: maintenance scripts, fixture reset, backups, multi-association stack, and operator checklist.
- `docs/dev/translations.md`: translation architecture and workflow.
- `docs/dev/templates.md`: association-specific template override rules.
- `docs/dev/kubernetes.md`: Helm/k3s deployment notes.

If you change app behavior, update the matching `docs/dev/<app>.md` and, when admin/editor workflows change, the matching `docs/admin/<app>.md`. If you add or rename docs, update `docs/index.md`.

## Local Workflow

Use Bash-compatible commands from the repository root.

```bash
cp .env.example .env
source env.sh
date-start-detached
date-createsuperuser
```

Common helpers after `source env.sh`:

- `date <docker compose args>`: project-aware wrapper around `docker compose`.
- `date-start` / `date-start-detached`: build/start, migrate, collect static.
- `date-stop`: stop the stack.
- `date-manage <cmd>`: run `python manage.py <cmd>` in the web container.
- `date-makemigrations`, `date-migrate`, `date-collectstatic`, `date-createsuperuser`.
- `date-test [labels]`: run tests with `core.settings.test`.
- `date-setup`: install the `.githooks/` pre-push hook path.
- `date-cleaninit`: destructive local reset, fixture load, generated sample media, and default passwords.

Use `date-cleaninit` only for disposable local data. It recreates the dev database and can delete local media.

For cross-association visual checks, use `docker-compose.dev-all.yml` or the `date-all-*` aliases. Ports are:

- biocum: `http://localhost:8001`
- date: `http://localhost:8002`
- kk: `http://localhost:8003`
- pulterit: `http://localhost:8004`

The dev-all stack runs migrations/`compilemessages` once in an `init` service with `PROJECT_NAME=date`. It intentionally skips `collectstatic`; debug mode uses WhiteNoise finders to serve static files directly from each association's `STATICFILES_DIRS`.

## Tests And Checks

Before finishing a code change, run the narrowest useful test first, then broaden when the change has shared impact.

```bash
date-test
date-test members.tests
date-manage check
python scripts/validate_translations.py
```

Use `python scripts/validate_translations.py` after translation-heavy work. Manually smoke-test user-facing flows when changing forms, registrations, background tasks, Channels/WebSocket behavior, templates, or language navigation.

`core.settings.test` always uses the DaTe app set, so apps that are not installed for `date` (notably `lucia`, which is kk-only) will not be picked up by a bare `date-test`. Run those tests with `DJANGO_SETTINGS_MODULE` set to a settings module that installs the app, or via `PROJECT_NAME` on a manual `manage.py test` invocation.

CI runs translation validation, `compilemessages`, the Django test suite, starts the Compose stack, and pings the web endpoint. There is no separate formatter/linter configured in `pyproject.toml`; follow the existing style and keep changes locally consistent.

The optional pre-push hook under `.githooks/` runs `uv run python manage.py test` when `uv` is available, falls back to Docker tests when Docker is available, and otherwise warns without blocking. `date-setup` installs this hook path.

## Dependencies

This project uses UV for Python dependency management. Do not default to hand-managed `venv`, `pip install`, or `requirements.txt` workflows.

Python dependencies are declared in `pyproject.toml` and locked in `uv.lock`. The Docker build runs `uv sync --frozen`, so commit lockfile updates together with dependency changes.

Use `uv run ...` for local Python commands when you are not using the Docker helpers. Use `uv add ...` / `uv lock` for dependency changes rather than editing only the lockfile or installing packages ad hoc.

Prefer adding dependencies only when they remove meaningful complexity. This app is Docker-first, so verify dependency changes through the container workflow rather than only in a local virtualenv.

## Environment Flags

Important settings come from `.env`:

- `PROJECT_NAME`: active association/site variant (`date`, `kk`, `biocum`, `demo`, `pulterit`, etc.).
- `ENABLE_LANGUAGE_FEATURES`: enables runtime language switching and translated admin tabs. Default/off means Swedish-only behavior.
- `USE_UNFOLD`: enables the Unfold admin theme. Restart/recreate containers after changing it.
- `USE_S3`: switches uploads from local disk to S3-compatible storage.
- `COMPOSE_FILE`: selects the Compose stack.

Do not commit real secrets, production bucket names, API keys, or filled production values. Keep examples in `.env.example`, `.env.prod.example`, and Helm values files generic.

## Architecture Notes

- `manage.py`, `core.wsgi`, `core.routing`, and Celery all derive the settings module from `PROJECT_NAME`, defaulting to `core.settings.date`.
- Running `python manage.py test` without an explicit `DJANGO_SETTINGS_MODULE` switches to `core.settings.test`, which uses the DaTe app set, in-memory SQLite, in-memory Channels, locmem cache, fast password hashing, and compiled translations.
- `core/settings/<variant>.py` selects settings by association. Shared defaults live in `core/settings/common.py`, with helper modules under `core/settings/dependencies/`.
- Installed apps differ by association. `date` includes the broadest app set, but `lucia` is only in `kk`; run migrations/checks with a `PROJECT_NAME` that installs the app you are touching.
- `core/urls/common.py` builds shared canonical public routes. Public URLs are normally unprefixed even when language features are enabled.
- URLconfs also differ by association. For example, `pulterit` disables archive routes via `ARCHIVE_ENABLED=False`, and signup visibility can depend on `MEMBERS_SIGNUP_ENABLED`.
- `templates/common/` contains shared templates. `templates/<association>/` overrides blocks by extending the same logical template path.
- `biocum` looks in `templates/biocum`, then `templates/date`, then common templates. Other associations generally go straight from their own template directory to common templates.
- Static assets are split by association under `static/<association>/` and shared assets under `static/common/`.
- Media storage can be local or S3-compatible; archive/publication public files expect the storage backend behavior documented in their guides.
- Celery remains the production background task backend. When tasks depend on saved database rows, enqueue after transaction commit.
- The Django admin is intentionally custom. `date.apps.DateAdminConfig` installs `core.admin.FixedLanguageAdminSite`, preserves optional 2FA enforcement, and re-installs that site when Unfold would otherwise replace it. Register admin models through normal `admin.site` imports after that setup has run.
- `AUTH_USER_MODEL` is `members.Member`. Staff status is group-based through `settings.STAFF_GROUPS` (plus superuser), not an `is_staff` database field.

## Storage And Files

- `USE_S3=False` uses local `media/` and plain filesystem storage.
- `USE_S3=True` switches default media to private S3 storage and adds a `public_media` storage for public assets.
- `core.fields.PublicFileField` picks public S3 storage only when `USE_S3=True`; otherwise it behaves like a normal file field.
- Public/archive/publication file deletion logic has local-vs-S3 branches. Check the app guide before changing delete behavior.
- Do not run `seed_gallery` with `USE_S3=True`; the command refuses because it would upload fake images to S3.

## Translations

Swedish (`sv`) is the default language and source of truth for established site copy. Shared locale catalogs exist for `sv`, `en`, and `fi`; DaTe runtime currently exposes `sv` and `en`, while some association variants expose Finnish.

Static UI translations use Django locale files in `locale/<lang>/LC_MESSAGES/`. Dynamic editor content uses `django-modeltranslation` and language-specific columns such as `title_sv`, `title_en`, and `title_fi`.

When adding translated model fields:

1. Add or update the app's `translation.py`.
2. Register fields with `TranslationOptions`.
3. Create and commit migrations for generated language columns.
4. Backfill existing values with `python manage.py update_translation_fields` when needed.

For internal links, prefer `reverse(...)`, `{% url %}`, or the `localized_url` template filter for stored paths (load it with `{% load localized_urls %}` from the `staticpages` tag library). Do not localize external URLs, `mailto:`, `tel:`, anchors, or JavaScript URLs.

Translation commands:

```bash
django-admin makemessages -l sv -l en -l fi
django-admin makemessages -l sv -l en -l fi -d djangojs -i "**/vendor/**" -i "core/static/**"
django-admin compilemessages
```

## App Map

- `ads`: banner URLs used on the ads page and homepage.
- `alumni`: Google Sheets-backed alumni signup/update flow, Celery side effects, token emails.
- `archive`: photo/document/exam/public-file collections, bulk uploads, access checks.
- `billing`: event invoices and reference-number generation behind the event billing integration.
- `ctf`: seasonal CTFs, flags, guesses, and solving flow.
- `date`: homepage composition, calendar data, language switching, middleware, error views.
- `events`: events, dynamic registration forms, capacity/sign-up windows, passcodes, captcha, child events, WebSocket attendee updates.
- `lucia`: candidate pages and admin-managed seasonal content.
- `members`: custom user model, membership/subscription state, functionaries, auth, two-factor, GitHub login.
- `news`: posts, categories, feeds, homepage/news listing behavior.
- `polls`: questions, choices, votes, membership-aware vote validation.
- `publications`: PDF metadata, access controls, viewer/list pages.
- `social`: Instagram embeds and harassment report form/email flow.
- `staticpages`: CKEditor pages, dropdown navigation, stored internal URLs.

Read the corresponding `docs/dev/<app>.md` before changing app internals.

## Safety Rules

- Preserve user data. Make backups before destructive database or media operations.
- Never use `update-postgres.sh` for minor PostgreSQL upgrades. It is only for major upgrades and is destructive if misused.
- Do not rewrite published migrations. Add new migrations.
- Generate migration files with Django (`date-makemigrations` / `python manage.py makemigrations`) unless the migration needs custom data movement or another operation Django cannot infer automatically.
- Keep branch changes focused. Update docs/config examples when behavior or setup changes.
- Do not add secrets to source, fixtures, docs, or Helm values.
- Be careful with admin/editor flows; many features are operated by non-developers through Django admin.
- When touching association-specific templates, make shared block slots in `templates/common/` instead of relying on child-only blocks.
- When touching sign-up, billing, email, or alumni flows, preserve transaction-commit task enqueueing so workers do not process unsaved or rolled-back rows.

## Deployment Notes

Compose production uses `docker-compose.prod.yml` and the GHCR image selected by `DATE_IMG_TAG`. Prefer immutable commit SHA or release tags for production rollouts. `qa`, `prod`, and `latest` are moving aliases managed by workflows.

Kubernetes deployment uses the Helm chart in `charts/date-website/`. Run one Helm release per association because each release needs its own `PROJECT_NAME`, settings, static/template paths, hostnames, media prefixes, database, and backup prefix.

Shared monitoring is in `monitoring/` plus the `docker-compose.monitoring.yml` app overlay. Keep Prometheus/Grafana bound to localhost unless there is a trusted authenticated access path.

## PR Expectations

- Branch from `main`, open PRs into `main`, and squash merge.
- Run relevant tests/checks and mention anything not run.
- Update docs and config examples together with code behavior.
- Keep `main` history clean and readable.
