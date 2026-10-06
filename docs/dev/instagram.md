# Instagram Development Notes

## Responsibility
The `instagram` app owns the Instagram post URLs used by the home page embed area.

## Models
- `IgUrl` is one slider post: an uploaded `image` (admin-managed posts) or an image `url` (posts fetched by the updater), plus the post's Instagram `shortcode`, used to link to it.
- `clean()` accepts a pasted post link (`/p/`, `/reel/` or `/tv/`, with or without a username or query string, and with any host casing) and stores just the shortcode, and requires either an image or a URL.
- `image_url` returns the uploaded image when there is one, otherwise `url`. `image` is a `core.fields.PublicFileField`, so uploads go to public storage on S3.
- New uploads must be real images at least `MIN_IMAGE_HEIGHT` (300 px) tall: the slider shows posts 150 px tall, and high-density screens need twice that to stay sharp. Only new uploads are checked, so editing a post never re-reads its stored file.
- Rows are ordered newest first (`-id`).

## Integrations
- `date.views.index` passes the `IgUrl` rows to the front page as `posts`.
- `templates/common/date/components/instagram.html` is the shared scrolling slider; kk and impuls include it. It renders nothing when there are no posts. Each site styles it in its own `date/css/homepage.css`.
- Impuls's posts are managed in the admin only (no `INSTAGRAM_USERNAME`).

## Updating the posts

`python manage.py update_instagram` fetches the latest 40 posts of the site's `INSTAGRAM_USERNAME` with instaloader and replaces the previously fetched posts; posts with an uploaded image are never touched. Run it from a checkout where the `instagram` extra is installed (see below); the web/worker image is built without that extra, so `date-manage update_instagram` fails with `CommandError: instaloader is not installed`. The new posts are only written once the whole fetch has succeeded, so a failed run keeps the current ones. `INSTAGRAM_USERNAME` is an association capability setting: `kemistklubben` for kk, empty (updater disabled) elsewhere.

`instagram/igupdate.py` is a long-running scheduler that runs the command daily at 00:00 and logs failures; like `manage.py`, it picks the settings from `PROJECT_NAME`. `social/igupdate.py` remains as a thin compatibility import.

Both need the optional `instagram` dependency group, which the web/worker image does not include:

```bash
uv sync --extra instagram
PROJECT_NAME=kk python manage.py update_instagram
```

**As of 2026-08, no runner is wired anywhere**: neither this repository (compose services, chart, Celery tasks, workflows) nor the operator infrastructure (CronJobs, host cron, systemd) runs the updater, so the posts only change when someone runs it manually. If the slider should stay fresh, wire a runner (e.g. a chart CronJob) that installs the `instagram` extra and runs `python manage.py update_instagram` daily.

Caveats:

- The updater replaces every row that has no uploaded image, so a row created in the admin without an image is deleted on the next run. The `url` field is updater-owned: leave it empty on posts whose image is uploaded in the admin.
- Instagram rate-limits anonymous requests. A request from a development machine on 2026-10-06 got `429 Too Many Requests` on the very first profile lookup, so expect fetches to fail; the stored posts are kept when they do.
- The stored image URLs are Instagram CDN links that expire, so the slider needs regular refreshes to keep showing images.

## Migration Notes
- Data was split out from `social.IgUrl` into `instagram.IgUrl`.
- The split migration preserves primary keys and drops the legacy `social_igurl` table after copying.
- Legacy `social` Instagram URL permissions continue to grant equivalent admin access while stale content types are being migrated.
