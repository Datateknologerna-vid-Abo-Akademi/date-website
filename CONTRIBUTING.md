# Contributing

Follow the guidelines below to keep reviews straightforwardad and deployments uneventful.

## Workflow overview

1. **Discuss the change** – open or comment on a GitHub issue if the work is non-trivial so we can align on scope.
2. **Branch from `develop`** – `main` tracks the live deployment; feature work happens on `develop`.
3. **Name your branch clearly** – prefer `feature/<short-topic>`, `fix/<issue-number>-<topic>`, `docs/<area>`, or `chore/<task>`. Matching the prefixes already in the history keeps the branch list readable.
4. **Push and open a pull request into `develop`** – describe the change, list manual/automated tests you ran, and link any relevant docs updates.
5. **Address review feedback** – rebase or merge `develop` as needed, keeping the branch up to date before merge.

## Commit messages

- Use present-tense, descriptive summaries (50–72 characters). Examples from history: `docs: add admin and dev guides for all apps`, `fix: redis volume mount`.
- Reference the tracking issue or PR using `(#123)` or `Issue-123:` so GitHub links the work automatically.
- Group related changes together. Avoid “misc fixes” commits unless it’s truly a cleanup.

## Development environment

Follow the walkthrough in `README.md`. Key reminders:

- Run `source env.sh dev` in every new shell so the `date-*` helper aliases exist.
- `date-start`/`date-stop` manage the Docker Compose stack.
- Use `date-manage <command>` for `manage.py` commands and `date-test` for the Django test suite.
- If you change environment variables, reload them with `source env.sh dev` before restarting services.

## Testing expectations

- **Automated tests** – `date-test` (or `python manage.py test`) must pass before you open a PR. The command automatically switches to `core.settings.test`, so Redis/PostgreSQL mocks are configured for you.
- **Targeted runs** – you can narrow tests via labels (`date-test members.tests`). Add new unit tests next to the feature you are touching (models, forms, views, Celery tasks, Channels consumers, etc.).
- **System checks** – run `date-manage check` to ensure migrations, settings, and URLs are valid.
- **Manual verification** – exercise the UI path or admin workflow you changed. Mention the manual checks in your PR description.

## Database & migrations

- Generate migrations with `date-makemigrations`, inspect them, then run `date-migrate`.
- Never rewrite previously merged migrations; add follow-up migrations instead.
- When a change depends on new fixtures or default data, update `initialdata.json` or add a data migration.
- Use `scripts/clean-init.sh` to recreate the development database from scratch (wipes all volumes) and rerun `date-createsuperuser` afterward.

## Documentation

- Keep `README.md`, `docs/index.md`, and the relevant `docs/admin|dev/*.md` guide in sync with your change. GitHub Pages publishes straight from the `docs/` folder on `develop`/`main`.
- Add inline docstrings for non-obvious helpers, serializers, management commands, or Celery tasks.
- Update `.env.example`, `CHANGELOG.md`, or the Docker Compose files if your change affects configuration or deployment.

## Deployment considerations

- Production uses `docker-compose.prod.yml` with the published GHCR image. Changes to Dockerfiles, Compose files, or startup scripts should include instructions in the PR for updating `DATE_IMG_TAG` and recreating services.
- Only run `update-postgres.sh` for major PostgreSQL upgrades and call this out explicitly in the PR so operators can plan downtime.

## Pull-request checklist

- [ ] Branch is based on `develop` and up to date.
- [ ] Tests (`date-test`) and `date-manage check` pass locally.
- [ ] Database migrations (if any) are included and documented.
- [ ] Docs / README / `.env.example` / changelog updated when relevant.
- [ ] Screenshots or manual test notes are attached for UX changes.

Consistent workflows, thorough tests, and timely documentation keep the service reliable. Stick to the checklist above before handing work over for review.
