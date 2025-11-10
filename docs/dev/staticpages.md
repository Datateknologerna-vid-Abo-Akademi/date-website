# Static Pages Development Notes

## Models
- `StaticPageNav` stores menu categories. `use_category_url` shortcuts the category click to a custom `url`. `nav_element` defines ordering. 
- `StaticPage` is the CKEditor‑backed page content. `members_only` gates access, and `slug` is unique (max 50 chars). `update()` stamps `modified_time`.
- `StaticUrl` represents dropdown entries linked to a `StaticPageNav`. The overridden `save()` auto‑assigns `dropdown_element` in steps of 10 so the admin ordering widget works.

## Views & Routing
- `StaticPageView` (`staticpages/views.py`) is the only view. It loads the page by slug, checks `members_only`, and either renders `staticpages/staticpage.html` or redirects unauthenticated users to `/members/login`.
- Navigation menus are built in templates using `StaticPageNav` + `StaticUrl`. There is no dedicated API layer.

## Admin/Ordering
- `StaticPageNavAdmin` allows inline management of `StaticUrl` rows using `admin-ordering`. Dragging rows updates the `dropdown_element`.
- `StaticPageAdmin` lists pages with `members_only` badge for quick auditing.

## Extending the App
- To add versioning, introduce a `StaticPageRevision` model storing snapshots when `update()` runs.
- To support scheduling, add `publish_at`/`unpublish_at` fields and filter in the view before rendering.
- Consider caching navigation structures if menu lookups become expensive; currently everything hits the database on each request.
