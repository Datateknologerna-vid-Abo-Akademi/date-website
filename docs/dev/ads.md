# Ads Development Notes

## Data Model
- `AdUrl` (`ads/models.py`) stores two URLs: `ad_url` (required banner asset) and `company_url` (optional landing page). The `__str__` representation is the ad URL, so lists in admin show the image source.

## Views and Templates
- `ads.views.adsIndex` loads all `AdUrl` rows and renders them with `ads/adsindex.html`.
- The front page (`date/views.py:index`) also pulls `AdUrl.objects.all()` to display banners globally, so changes here surface across the public site.

## Admin Integration
- Admin registers `AdUrl` with default settings (`ads/admin.py`). There is no custom form logic, so any validation or upload handling must happen before saving URLs.

## Extending the App
- To support file uploads instead of external URLs, swap the `ad_url` field for `models.ImageField` and update templates to use `ad_url.url`.
- If rotation or scheduling is required, add datetime fields (e.g., `start_at`, `end_at`) and filter in `adsIndex` and the home page query.
- For analytics, add a click‑tracking view that redirects to the external URL after recording a metric, and update templates to point to that view.
