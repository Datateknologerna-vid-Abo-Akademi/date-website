# Instagram Development Notes

## Responsibility
The `instagram` app owns the Instagram post URLs used by the home page embed area.

## Models
- `IgUrl` stores a post `url` and Instagram `shortcode`.

## Integrations
- `date.views.index` reads `IgUrl` rows for the front page context.
- `instagram/igupdate.py` keeps the existing scheduled updater entry point. `social/igupdate.py` remains as a thin compatibility import.

## Migration Notes
- Data was split out from `social.IgUrl` into `instagram.IgUrl`.
- The split migration preserves primary keys and drops the legacy `social_igurl` table after copying.
