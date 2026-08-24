# Instagram Development Notes

## Responsibility
The `instagram` app owns the Instagram post URLs used by the home page embed area.

## Models
- `IgUrl` stores a post `url` and Instagram `shortcode`.

## Integrations
- `date.views.index` reads `IgUrl` rows for the front page context.
- The home page embed (`templates/kk/date/components/instagram.html`) links each post to `https://www.instagram.com/p/<shortcode>/`.

## Refreshing posts
- `instagram.tasks.fetch_instagram_posts` is a Celery task that fetches the latest posts for `INSTAGRAM_PROFILE` (default `kemistklubben`) via `instaloader` and replaces the stored rows.
- Existing rows are only replaced when the fetch succeeds, so a transient Instagram error never wipes the feed.
- Optional credentials via `INSTAGRAM_USERNAME` / `INSTAGRAM_PASSWORD` are recommended: Instagram rate-limits anonymous scraping. Leave them empty for anonymous fetch.
- The task runs daily through the Celery beat schedule (`CELERY_BEAT_SCHEDULE` in `core/settings/common.py`). A beat process is required:
  - dev: `docker-compose.yml` `celery-beat` service
  - prod-shape preview: `docker-compose.prod.yml` `celery-beat` service
  - Kubernetes: `deployment-celery-beat.yaml` in the Helm chart (`celeryBeat` values block)
- The old standalone scheduler (`instagram/igupdate.py` with its own `schedule` loop, hardcoded profile, and wipe-then-refetch behavior) was removed.

## Migration Notes
- Data was split out from `social.IgUrl` into `instagram.IgUrl`.
- The split migration preserves primary keys and drops the legacy `social_igurl` table after copying.
