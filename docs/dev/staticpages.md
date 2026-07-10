# Static Pages Development Notes

## Models
- `StaticPageNav` stores menu categories. `use_category_url` shortcuts the category click to a custom `url`. `nav_element` defines ordering.
- `StaticPage` is the CKEditor-backed page content. `members_only` gates access, and `slug` is unique (max 50 chars). `update()` stamps `modified_time`.
- `StaticUrl` represents dropdown entries linked to a `StaticPageNav`. `logged_in_only` hides links from anonymous users, and `dropdown_element` controls ordering for the admin ordering widget.

## Views & Routing
- `StaticPageView` (`staticpages/views.py`) is the only view. It loads the page by slug, checks `members_only`, and either renders `staticpages/staticpage.html` or redirects unauthenticated users to `/members/login`.
- Navigation menus are built in templates using `StaticPageNav` + `StaticUrl`; `staticpages.context_processors` injects both querysets into every template.
- Language-aware internal links should go through the `localized_url` template filter (`staticpages/templatetags/localized_urls.py`) so stored URLs keep the current locale prefix when language features are enabled.
- Routes are wrapped by the shared localized URL builder in `core/urls/common.py`, so static pages can live under language prefixes without duplicating route declarations.

## Admin/Ordering
- `StaticPageNavAdmin` allows inline management of `StaticUrl` rows using `admin-ordering`. Dragging rows updates the `dropdown_element`; category and dropdown URLs render quick open links for checking destinations.
- `StaticPageAdmin` lists pages with `members_only` badge, per-language translation coverage, and public-page links for quick auditing. The slug field is prepopulated from the title on new pages. When language features are enabled, the local language tabs show one translated title/content version at a time without relying on an external JavaScript CDN.

## Extending the App
- Distinguish between external URLs and internal paths when adding menu links. External URLs should remain absolute; internal paths should stay relative so `localized_url` can rewrite them.
- If you add more visibility rules, update both the model fields and the shared navigation template logic together.
- To add versioning, introduce a `StaticPageRevision` model storing snapshots when `update()` runs.
- To support scheduling, add `publish_at`/`unpublish_at` fields and filter in the view before rendering.
- Consider caching navigation structures if menu lookups become expensive; currently everything hits the database on each request.
