# DaTe Website 2.0

DaTe Website 2.0 powers [Datateknologerna vid Åbo Akademi rf](https://date.abo.fi)'s public site, membership tools, alumni portal, polls, and other seasonal apps. The stack is Django 5.2 running on Python 3.13 inside Docker Compose with Celery workers, Channels/Daphne, PostgreSQL, Valkey (Redis compatible), and S3-compatible storage.

> Active development happens on `develop`. The `main` branch mirrors production releases, so branch off `develop` when you start new work.


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
source env.sh dev               # loads .env and registers helper aliases
date-start-detached             # builds containers, runs migrations, collects static files
date-createsuperuser            # creates your admin account
open http://localhost:8000      # admin lives at /admin
```

Prefer SSH? Add your key to GitHub following their [SSH setup guide](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account), then clone with `git clone git@github.com:datateknologerna-vid-abo-akademi/date-website.git`.

Need sample content? Run `scripts/clean-init.sh` to wipe the dev database and load the fixtures from `initialdata.json`. The script must be executed with Bash (`/bin/bash scripts/clean-init.sh`) if your shell complains about `illegal option`.

Working on features that touch S3-compatible storage? Run a local [MinIO](https://min.io/) container and point `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, and `S3_SECRET_KEY` in `.env` to it. This keeps uploads, ACLs, and presigned URLs testable without external dependencies.

## Environment configuration & helper aliases

`env.sh` centralises environment loading:

- `source env.sh dev` uses `.env` (falling back to `.env.example`) and sets `DATE_DEVELOP=True`, which in turn selects `docker-compose.yml`.
- `source env.sh prod` prefers `.env.prod`, flips `DATE_DEVELOP=False`, and switches aliases to `docker-compose.prod.yml`.
- `source env.sh path/to/custom.env` lets you provide an explicit file (relative or absolute path).

The script exports `COMPOSE_FILE_PATH` and defines the `date-*` aliases used throughout this README:

| Command | Description |
| --- | --- |
| `date-start` / `date-start-detached` | Pull images, rebuild, apply migrations, collect static files, and start the stack (foreground or detached). |
| `date-stop` | Shut down the Compose stack. |
| `date-manage <cmd>` | Run `python manage.py <cmd>` inside the web container. |
| `date-makemigrations`, `date-migrate`, `date-collectstatic`, `date-createsuperuser` | Convenience wrappers around common `manage.py` commands. |
| `date-test [labels]` | Execute the Django test suite using the isolated `core.settings.test` configuration. |
| `date-pull` | Pull the defined Docker images. |

Reload `env.sh` whenever you edit the `.env` files so the aliases pick up your changes.

## Database, migrations, and seed data

- Use `date-makemigrations` and `date-migrate` for schema changes. Commit the generated migration files; do not rewrite published migrations.
- `scripts/clean-init.sh` drops and recreates the development database volumes, then loads `initialdata.json`. **All local data will be deleted.**
- To inspect data manually, open a shell in the container: `docker compose run --rm web python manage.py shell`.
- Re-run `date-createsuperuser` after resetting the database so you keep admin access.

## Tests & QA

The CI and reviewer expectation is that `python manage.py test` (or the `date-test` alias) passes before you open a pull request. The test settings mock external services, so no Redis or PostgreSQL on the host is required.

Examples:

```bash
date-test                   # run the full suite inside Docker
date-test members.tests     # run a specific module
date-manage check           # static checks (migrations, settings sanity)
```

Manually verify user-facing flows (forms, Celery tasks, Channels endpoints) when implementing a feature; many branches in the git history pair automated tests with quick manual smoke tests.

## Documentation & app guides

The `docs/` directory contains both developer notes (`docs/dev/*.md`) and content-editor guides (`docs/admin/*.md`). The folder is published via GitHub Pages, so any Markdown file you update on `develop` is deployed automatically after merging. Keep the relevant guide in sync whenever you touch an app such as `events`, `lucia`, or `members`.

## Deployment (`docker-compose.prod.yml`)

The production stack relies on the published container image at `ghcr.io/datateknologerna-vid-abo-akademi/date-website:${DATE_IMG_TAG}` plus managed PostgreSQL/Valkey volumes. Typical flow:

1. Place your production secrets in `.env.prod` (or pass a custom env file to `env.sh`).
2. Ensure the external Docker network referenced by the compose file exists once:
   ```bash
   docker network create web
   ```
3. Load the production env vars: `source env.sh prod`.
4. Deploy: `docker compose -f docker-compose.prod.yml up -d`.

The stack brings up the `web` (Gunicorn), `asgi` (Daphne/Channels), `celery`, `db`, `redis`, and `nginx` services. Rolling deploys usually build a new GHCR image in CI, update `DATE_IMG_TAG`, then restart `web`, `asgi`, and `celery`.

## Updating PostgreSQL volumes

Only use `update-postgres.sh` for **major** PostgreSQL version upgrades. The script wipes the `date_postgres_data` volume after creating a dump, so back up before running it.

1. Set `DATE_POSTGRESQL_VERSION` to the **current** version in your `.env`.
2. Run `./update-postgres.sh <target_version> [env_file]`.
3. Re-source your env (`source env.sh dev`) and restart the stack.

For minor upgrades, change `DATE_POSTGRESQL_VERSION` and recreate the containers without touching volumes.

## Troubleshooting

- `date-start` fails with "docker: permission denied": add your user to the `docker` group (`sudo usermod -aG docker $USER`) and reopen the terminal.
- Shell complains about `clean-init.sh`: run it explicitly with Bash (`/bin/bash scripts/clean-init.sh`).
- Services restarted but settings not updated: ensure you re-run `source env.sh dev|prod` after editing `.env` files so `COMPOSE_FILE_PATH` and aliases refresh.

## License

All content in this repository is released under [CC0 1.0](LICENSE).
