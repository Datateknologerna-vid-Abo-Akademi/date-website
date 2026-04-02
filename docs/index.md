# DaTe Website Documentation

This directory is published directly via GitHub Pages (branch -> `docs/` folder). Push an updated Markdown file to the tracked branch and the public documentation site refreshes automatically.

Use the sections below to jump to either editor-facing instructions or implementation notes.

## Start Here

- Working on local setup, Docker, migrations, translations, or deployments? Start with the repository [README](../README.md).
- Editing content in Django admin? Use the `Admin & Content Editors` guides below.
- Changing code, templates, models, or routing? Use the `Developers` guides below.
- Adding a new app or major feature? Update both the relevant app guide and this index so the published docs stay navigable.

## Project-wide Notes

- The project can run multiple association/site variants via `PROJECT_NAME`.
- Language-prefixed routes and the language switcher are controlled by `ENABLE_LANGUAGE_FEATURES`.
- The public docs are meant to complement the README, not replace it. Keep operational commands in the README and app-specific behavior in these guides.

## Admin & Content Editors

- [Ads Admin Guide](admin/ads.md)
- [Alumni Admin Guide](admin/alumni.md)
- [Archive Admin Guide](admin/archive.md)
- [Billing Admin Guide](admin/billing.md)
- [CTF Admin Guide](admin/ctf.md)
- [Site Shell (date app) Admin Guide](admin/date.md)
- [Events Admin Guide](admin/events.md)
- [Lucia Admin Guide](admin/lucia.md)
- [Members Admin Guide](admin/members.md)
- [News Admin Guide](admin/news.md)
- [Polls Admin Guide](admin/polls.md)
- [Publications Admin Guide](admin/publications.md)
- [Social Admin Guide](admin/social.md)
- [Static Pages Admin Guide](admin/staticpages.md)
- [Translation Editor Guide](admin/translations.md)

## Developers

- [Ads Development Notes](dev/ads.md)
- [Alumni Development Notes](dev/alumni.md)
- [Archive Development Notes](dev/archive.md)
- [Billing Development Notes](dev/billing.md)
- [CTF Development Notes](dev/ctf.md)
- [Site Shell (date app) Development Notes](dev/date.md)
- [Events Development Notes](dev/events.md)
- [Lucia Development Notes](dev/lucia.md)
- [Members Development Notes](dev/members.md)
- [News Development Notes](dev/news.md)
- [Operations & Maintenance Notes](dev/operations.md)
- [Polls Development Notes](dev/polls.md)
- [Publications Development Notes](dev/publications.md)
- [Social Development Notes](dev/social.md)
- [Static Pages Development Notes](dev/staticpages.md)
- [Translation System Notes](dev/translations.md)

## Maintenance

- Keep app guides focused on responsibilities, data model expectations, important admin behavior, and extension gotchas.
- When routing, language handling, or deployment behavior changes, update the README and any affected development guide in the same branch.
- If a guide becomes mostly obsolete, rewrite it instead of layering more historical notes on top.

Need to add or update a guide? Create or edit the Markdown file in the appropriate subfolder, then commit and push. GitHub Pages will redeploy automatically.
