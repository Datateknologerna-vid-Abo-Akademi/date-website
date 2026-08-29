# Instagram Development Notes

## Responsibility
The `instagram` app owns the Instagram post URLs used by the home page embed area.

## Models
- `IgUrl` stores a post `url` and Instagram `shortcode`.

## Integrations
- `date.views.index` reads `IgUrl` rows for the front page context.
- `instagram/igupdate.py` is the standalone Instagram updater: a long-running
  scheduler that fetches the latest ~40 posts for the hardcoded
  `kemistklubben` profile via instaloader once per day at 00:00 and rewrites
  `IgUrl`. `social/igupdate.py` remains as a thin compatibility import.

## Running the updater

The updater is not part of the web/worker runtime: `instaloader` and
`schedule` live in the optional `instagram` dependency group, so a default
image cannot run it.

```bash
uv sync --extra instagram
python instagram/igupdate.py
```

The script calls `django.setup()` itself and defaults to
`core.settings.date`; set `PROJECT_NAME` (or `DJANGO_SETTINGS_MODULE`) when
running it for another association.

The current production runner lives outside this repository (operator
deployment or host cron); it must install the `instagram` extra in whatever
environment executes the script.

Caveats:

- The profile is hardcoded to `kemistklubben`; there is no configuration.
- `IgUrl.objects.all().delete()` runs before the fetch, so a failed fetch
  (rate limiting, 2FA, network) leaves the embed area empty until the next
  successful run. The Celery task that replaced this script historically
  replaced rows only on success; the standalone script does not.

## Migration Notes
- Data was split out from `social.IgUrl` into `instagram.IgUrl`.
- The split migration preserves primary keys and drops the legacy `social_igurl` table after copying.
- Legacy `social` Instagram URL permissions continue to grant equivalent admin access while stale content types are being migrated.
