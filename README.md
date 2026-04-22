# DaTe Website 2.0

DaTe Website 2.0 powers [Datateknologerna vid Åbo Akademi rf](https://date.abo.fi)'s public site, membership tools, alumni portal, polls, and a handful of seasonal or one-off apps. The stack is Django 6.0 running on Python 3.13 inside Docker Compose with Celery workers, Channels/Daphne, PostgreSQL, Valkey (Redis compatible), and S3-compatible storage.

> Active development happens on `develop`. The `master` branch mirrors production releases, so branch off `develop` when you start new work.


## Requirements

- Docker 24+ plus the Docker Compose plugin (`docker compose`). Follow Docker's official guides for [Ubuntu](https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository) or [Debian](https://docs.docker.com/engine/install/debian/#install-using-the-repository) to install both the engine and the Compose plugin.
- Bash-compatible shell (the helper script `env.sh` defines aliases such as `date-start`)
- Access to `docker` without sudo (add yourself to the `docker` group if needed)
- Local `django-admin` (e.g., via `pipx install django`) when editing translations outside the container

> Windows developers should run the project inside WSL 2 to match the expected Linux tooling: sourcing `env.sh`, running Bash scripts, and keeping LF line endings all work reliably there. Follow Microsoft's [WSL installation guide](https://learn.microsoft.com/windows/wsl/install) first, then install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (which automatically connects Docker to your default WSL distro).

## Quick start (development)

```bash
git clone https://github.com/datateknologerna-vid-abo-akademi/date-website.git
cd date-website
git checkout develop
cp .env.example .env            # adjust passwords, ports, S3, etc.
source env.sh                   # registers helper aliases
date-start-detached             # builds containers, runs migrations, collects static files
date-createsuperuser            # creates your admin account
open http://localhost:8000      # admin lives at /admin
```

Prefer SSH? Add your key to GitHub following their [SSH setup guide](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account), then clone with `git clone git@github.com:datateknologerna-vid-abo-akademi/date-website.git`.

Need sample content? Run `date-cleaninit` (or `/bin/bash ./scripts/clean_init.sh`) to wipe the dev database, reload the fixture set, generate sample media, and reset the default local user passwords. It is the quickest way to get back to a known-good local setup.

Working on features that touch S3-compatible storage? Run a local [MinIO](https://min.io/) container and point `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, and `S3_SECRET_KEY` in `.env` to it. This keeps uploads, ACLs, and presigned URLs testable without external dependencies.

## Platform notes

The main workflow in this README is Linux-first. On Windows and macOS, the easiest path is still to follow the same Bash-based commands and only adapt the host-specific pieces below.

### Windows (WSL 2)

- Use WSL 2 with Ubuntu or Debian, and run the repo from inside the Linux filesystem rather than from `C:\...`.
- Install Docker Desktop and enable WSL integration for your distro so `docker compose` works directly inside WSL.
- Open the project in your editor through WSL if possible. This avoids line-ending, path, and permission oddities.
- Run the same commands as the Linux quick start from your WSL shell:

```bash
cd ~/code/date-website
source env.sh
date-start-detached
```

- To open the site from WSL, use `explorer.exe http://localhost:8000` or open the URL manually in your browser.
- If a script behaves strangely, first confirm it is being run by Bash inside WSL and not by PowerShell or `cmd.exe`.

### macOS

- Install Docker Desktop for Mac so `docker compose` is available.
- Use Terminal, iTerm2, or another shell that can run Bash-compatible commands. `zsh` is fine; `source env.sh` works.
- The rest of the workflow is the same as Linux: clone the repo, copy `.env.example`, source `env.sh`, and use the `date-*` aliases.
- The `open http://localhost:8000` command from the quick start already works on macOS.

### Linux

- The quick start above is written for Linux shells directly.
- If Docker requires `sudo`, fix your Docker group membership first rather than rewriting the commands with `sudo`.

## Environment configuration & helper aliases

Docker Compose reads `.env` automatically. Create it once from `.env.example`, then edit it for your local or deployed environment.

`env.sh` is only for helper aliases. Compose file selection lives in `.env` through `COMPOSE_FILE`.

- `.env.example` sets `COMPOSE_FILE=docker-compose.yml`.
- `.env.prod.example` sets `COMPOSE_FILE=docker-compose.prod.yml`.
- `source env.sh` registers the `date-*` aliases without loading or changing app configuration.
- The helpers use the nearest `date-website` checkout from your current directory, so globally installed helpers follow whichever clone you are working in. When you are outside a checkout, they fall back to `DATE_WEBSITE_DIR`.

If you use these helpers often, install them into your shell config:

```bash
./scripts/install_shell_aliases.sh
```

The installer writes the current checkout path as `DATE_WEBSITE_DIR`, which is only used as the fallback target when your shell is not inside a checkout.

Or add them manually and adjust the path to wherever you cloned the repository:

```bash
export DATE_WEBSITE_DIR="/path/to/date-website"
source "$DATE_WEBSITE_DIR/env.sh"
```

Important environment flags:

- `PROJECT_NAME` selects the active association/site variant (`date`, `kk`, `biocum`, `demo`, `pulterit`, `sf`, ...).
- `ENABLE_LANGUAGE_FEATURES=True` enables the language switcher, translated admin tabs, and runtime selection between the languages configured for the active association on unprefixed URLs. DaTe currently uses Swedish and English at runtime; some other associations also expose Finnish. When omitted or false, the project runs Swedish-only.
- `USE_S3` toggles whether uploads use local disk storage or the configured S3-compatible backend.

The script defines the `date-*` aliases used throughout this README:

| Command | Description |
| --- | --- |
| `date-start` / `date-start-detached` | Pull images, rebuild, apply migrations, collect static files, and start the stack (foreground or detached). |
| `date-stop` | Shut down the Compose stack. |
| `date-manage <cmd>` | Run `python manage.py <cmd>` inside the web container. |
| `date-makemigrations`, `date-migrate`, `date-collectstatic`, `date-createsuperuser` | Convenience wrappers around common `manage.py` commands. |
| `date-test [labels]` | Execute the Django test suite using the isolated `core.settings.test` configuration. |
| `date-pull` | Pull the defined Docker images. |
| `date-cleaninit` | Reset local data and reload the development fixtures plus generated sample media. |

Recreate or restart containers after editing `.env` so Docker Compose passes the updated values into services.

Once the aliases are registered, the `date-*` commands are the normal way to work with the project.

## Database, migrations, and seed data

- Use `date-makemigrations` and `date-migrate` for schema changes. Commit the generated migration files; do not rewrite published migrations.
- `date-cleaninit` (alias for `./scripts/clean_init.sh`) drops and recreates the development database volumes, loads the local fixture set, generates sample media, and resets the `admin`, `freshman`, and `member` passwords to `admin`. **All local data will be deleted.**
- If your shell does not expose aliases, run `/bin/bash ./scripts/clean_init.sh` directly.
- To inspect data manually, open a shell in the container: `docker compose run --rm web python manage.py shell`.
- Re-run `date-createsuperuser` after resetting the database so you keep admin access.

The fixture reset flow uses `scripts/load_all_fixtures.sh` and `scripts/generate_dynamic_fixtures.py`, so treat generated media and sample content as disposable local data rather than checked-in source material.

## Tests & QA

The CI and reviewer expectation is that `python manage.py test` (or the `date-test` alias) passes before you open a pull request. The test settings mock external services, so no Redis or PostgreSQL on the host is required.

Examples:

```bash
date-test                   # run the full suite inside Docker
date-test members.tests     # run a specific module
date-manage check           # static checks (migrations, settings sanity)
```

Manually verify user-facing flows (forms, background jobs, Channels endpoints) when implementing a feature; a lot of work in this repo still benefits from a quick human smoke test after the automated checks pass.

If you touch translations, templates, or language-aware navigation, also smoke-test the default Swedish site plus at least one non-default language selected through the language switcher with `ENABLE_LANGUAGE_FEATURES=True`.

## Documentation & app guides

The `docs/` directory contains both developer notes (`docs/dev/*.md`) and content-editor guides (`docs/admin/*.md`). The folder is published via GitHub Pages, so any Markdown file you update on `develop` is deployed automatically after merging. If you change behavior in an app such as `events`, `lucia`, or `members`, update the matching guide in the same branch while the details are still fresh.

Use [docs/index.md](docs/index.md) as the landing page for the published documentation site. Update it when you add a new app guide or rename an existing one.
For translation architecture and workflow, see [docs/dev/translations.md](docs/dev/translations.md).

## Deployment (`docker-compose.prod.yml`)

The production stack relies on the published container image at `ghcr.io/datateknologerna-vid-abo-akademi/date-website:${DATE_IMG_TAG}` plus managed PostgreSQL/Valkey volumes. Typical flow:

1. Copy `.env.prod.example` to `.env` on the deployment host and replace every placeholder.
2. Ensure the external Docker network referenced by the compose file exists once:
   ```bash
   docker network create web
   ```
3. Deploy: `docker compose up -d` or run `source env.sh` once and use `date up -d`.

The stack brings up the `web` (Gunicorn), `asgi` (Daphne/Channels), `celery`, `db`, `redis`, and `nginx` services. Rolling deploys usually build a new GHCR image in CI, update `DATE_IMG_TAG`, then restart `web`, `asgi`, and `celery`.

CI image publishing and release tagging are now separate on purpose:

- Pushes to `develop` publish moving `develop` images plus a commit-SHA tag.
- Pushes to `master` publish moving `master` images plus a commit-SHA tag.
- Release tags are created manually through `.github/workflows/release_tag.yaml` with `patch` as the default bump and optional `minor` / `major` overrides.
- When a release tag is created, CI reuses the already-published `master` image for that commit and adds the SemVer tags to the same image instead of rebuilding.

For production rollouts, prefer a release tag in `DATE_IMG_TAG` instead of the moving `master` tag.

Although Django 6 ships with the new Tasks framework, this project still uses Celery for production background work. The current task dispatch points defer enqueuing until after successful database commits where that matters, so new code should preserve that behavior.

`docker-compose.prod.yml` also reads `ENABLE_LANGUAGE_FEATURES`, so multilingual public/admin behavior must be enabled explicitly in production if you want language switching outside Swedish.

## Deployment (`k3s` / Helm)

The Kubernetes deployment path uses the Helm chart in `charts/date-website/`. The current target is k3s on Hetzner Cloud with Traefik ingress, `hcloud-volumes` for PostgreSQL, and Backblaze B2 through the S3-compatible API for media and PostgreSQL backups.

Use these values files together:

```bash
helm upgrade --install date-website charts/date-website \
  --namespace date-website \
  --create-namespace \
  -f charts/date-website/values-hetzner.yaml \
  -f charts/date-website/values-backblaze-b2.example.yaml \
  --set secret.existingSecret=date-website-prod-secrets \
  --set image.tag='<release-tag>'
```

Do not commit real production bucket names, app keys, or Django secrets in values files. Create a Kubernetes Secret first and pass it through `secret.existingSecret`.

For the full operator notes, required Secret keys, B2 bucket model, backup CronJob behavior, and smoke checks, see [docs/dev/kubernetes.md](docs/dev/kubernetes.md).

## Updating PostgreSQL volumes

Only use `update-postgres.sh` for **major** PostgreSQL version upgrades. The script wipes the `date_postgres_data` volume after creating a dump, so back up before running it.

1. Set `DATE_POSTGRESQL_VERSION` to the **current** version in your `.env`.
2. Run `./update-postgres.sh <target_version> [env_file]`.
3. Restart the stack.

The script now refuses same-major upgrades, verifies that PostgreSQL is storing data inside a mounted volume before it removes anything, and compares the restored schema against the source database before declaring success.

For Compose-based deployments, the db service now keeps `PGDATA` under the mounted volume and migrates older volume layouts into the `pgdata/` subdirectory on first start, so existing stacks do not lose access to pre-change database files.

For minor upgrades, change `DATE_POSTGRESQL_VERSION` and recreate the containers without touching volumes.

## Troubleshooting

- `date-start` fails with "docker: permission denied": add your user to the `docker` group (`sudo usermod -aG docker $USER`) and reopen the terminal.
- Shell complains about `clean_init.sh`: run it explicitly with Bash (`/bin/bash scripts/clean_init.sh`).
- Services restarted but settings not updated: recreate the affected containers after editing `.env`.

## Internationalization

Shared locale catalogs in this project

- sv (default)
- en
- fi

Active public/admin languages depend on the current association settings.

DaTe currently uses:

- sv
- en

Some other associations also expose:

- fi

### Translation scope

Swedish site copy should match the established wording from `develop` unless there is an explicit content decision to change it. In practice, Swedish is the source of truth for the site's established voice.

Use these rules when updating translations:

- Keep shared UI labels translated per locale, for example `Language`, `Address`, and error page titles.
- Keep proper names and intentional fixed labels unchanged across locales when that reflects the intended site copy.
- Treat Swedish as the source of truth for existing association wording and only introduce new translations where the text is meant to vary by language.

Current fixed terms that should not be translated just because they are user-facing:

- `Datateknologerna`
- `vid Åbo Akademi rf`
- `Joke`

### Translations

As the default language is `sv`, Swedish copy should be reviewed against the site itself when strings are extracted into locale files.

The project uses unprefixed public URLs. Language is resolved from the language cookie first, then the default `sv`. Associations can opt into browser `Accept-Language` detection with `USE_ACCEPT_LANGUAGE_HEADER=True`. When linking to internal pages from templates or stored nav items, prefer Django URL reversing or the `localized_url` template filter so links stay on the canonical unprefixed path.

To generate the translation file, called `django.po`
is done by executing the following command **in the root directory of the project**

```bash
$ django-admin makemessages -l en -l fi -l sv
```

This creates/updates the `django.po` 
in `date-website/locale/<language>/LC_MESSAGES`.

Add translations to the empty fields or use a third party translation software,
such as `Poedit`.

To compile the translations to `django.mo`, use the following command

```bash
$ django-admin compilemessages
``` 

### Django modeltranslations (translation of dynamic content)

The library django-modeltranslations was added to allow translating existing dynamic data (eg. events title and description)

If there is ever the need to provide a translated version of an existing field:

1. Add a file called translation.py to the app in question.
2. Create classes for each of the models for which fields will be translated and register the fields for translation.
3. Start the django app and apply the new database migration that will be automatically created by django-modeltranslations

Example to illustrate the above:

I want to provide translated variants of the title field in Events. The shared schema includes the stable modeltranslation language set, so it can still include `title_fi` for associations that use Finnish even when DaTe only exposes `sv` and `en` at runtime.

- Create the file translation.py under the events directory
- Create a new class called EventTranslationOptions that inherits from TranslationOptions (provided by django-modeltranslations)
- In the newly created class you register which fields should be translated by defining a variable called "fields"
- For the events example: `fields = ('title',)`

From "/events/translation.py":
```python
from core.modeltranslation import get_translation_languages
from modeltranslation.translator import register, TranslationOptions
from events.models import Event, EventAttendees, EventRegistrationForm

TRANSLATION_LANGUAGES = get_translation_languages()


@register(Event)
class EventTranslationOptions(TranslationOptions):
    fields = ('title', 'content',)
    languages = TRANSLATION_LANGUAGES
```

In this case, the newly created title_sv will not contain the data from what was previously just "title",
to fix this, run the command `docker compose run web python manage.py update_translation_fields`

### Using django-modeltranslations for non-standard field-types (eg. CKEditor5 instead of models.TextField)

Django-modeltranslations naturally does not play well with creating translations of external field types.

See https://django-modeltranslation.readthedocs.io/en/latest/installation.html#modeltranslation-custom-fields for more

Example solution:

1. add the field class to settings.py:

```python 
MODELTRANSLATION_CUSTOM_FIELDS = (
    'CKEditor5Field',
)
```

2. Change the field model to a standard TextField (or whatever suits your need)
3. Override the TextField with CKEditor5Field (or the corresponding field types for your case) in admin.py like this:

```python
    formfield_overrides = {
        TextField: {'widget': CKEditor5Widget},
    }
```

## Database backups

Use the dedicated backup script for routine PostgreSQL backups:

```bash
./scripts/backup_postgres.sh [dev|prod|path/to/env] [output_dir]
```

If no env argument is provided, the script resolves `prod`, which checks `.env.prod`, then `.env`, then `.env.example`.
You can also pass `dev` or a specific env file path.
If no `output_dir` is provided, backups are written to `./backups`.

Each run creates two timestamped files that a collector script can scan across many similar repos:

- `backups/<project>-<timestamp>.sql`
- `backups/<project>-<timestamp>.json`

The JSON manifest contains a stable machine-readable contract:

- `project_name`
- `project_label` when `PROJECT_NAME` is set
- `created_at_utc`
- `dump_filename`
- `dump_format`
- `database_engine`
- `database_service`
- `database_name`
- `database_user`
- `postgres_version`
- `postgres_major_version`

## Updating the database

### Warning

##### Only use the script for major version upgrades
For minor version upgrades change the `DATE_POSTGRESQL_VERSION` environment variable.

This script will wipe out __ALL__ data from the volume \
MAKE SURE YOU HAVE PROPER BACKUPS BEFORE ATTEMPTING THIS

If the dump command fails all data may be lost.

### How to upgrade major version

Run

#### Make sure `DATE_POSTGRESQL_VERSION` is set to the CURRENT version before running the following command

```bash
./update-postgres.sh target_version [dev|prod|path/to/env]
```

The upgrade helper now calls `./scripts/backup_postgres.sh` first and reuses the generated SQL dump during restore.
If no env argument is provided, it resolves `prod` first using the backup script's lookup order.
For upgrades, the resolved env file must be writable; the script will not modify `.env.example`.

Restart the stack afterward so containers use the updated `.env`.

## License

All content in this repository is released under [CC0 1.0](LICENSE).
