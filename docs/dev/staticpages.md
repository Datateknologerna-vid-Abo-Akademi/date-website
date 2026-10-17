# Static Pages Development Notes

## Models
- `StaticPageNav` stores menu categories. `use_category_url` shortcuts the category click to a custom `url`. `nav_element` defines ordering.
- `StaticPage` is the CKEditor-backed page content. `members_only` gates access, and `slug` is unique (max 50 chars). `update()` stamps `modified_time`.
- `StaticUrl` represents dropdown entries linked to a `StaticPageNav`. `logged_in_only` hides links from anonymous users, and `dropdown_element` controls ordering for the admin ordering widget. A `parent` self-relation lets a `StaticUrl` carry nested children.
- Nested navigation is rendered by `templates/common/core/header_nav_items.html` only when the header include passes `show_submenus=True` (pulterit, sf, impuls). Associations enabling it also need submenu styles in their header CSS, since the shared `core/css/header.css` has none.

## Views & Routing
- `StaticPageView` (`staticpages/views.py`) is the only view. It loads the page by slug, checks `members_only`, and either renders `staticpages/staticpage.html` or redirects unauthenticated users to `/members/login`.
- Policy pages (`equality_plan_view`, `registration_terms_view`) 404 unless the matching capability is enabled: `EQUALITY_PLAN_ENABLED` / `REGISTRATION_TERMS_ENABLED` (both set for `date` in its settings module; defaults are False in `core/settings/common.py`).
- Navigation menus are built in templates using `StaticPageNav` + `StaticUrl`; the merged `staticpages.context_processors.navigation` injects `categories` and `urls` into every template in a single load (3 queries). Anonymous navigation is cached per project/language/archive-mode and invalidated on `StaticUrl`/`StaticPageNav` saves or deletes; development uses the dummy cache, so caching is off there. The legacy `get_categories`/`get_urls` names remain as thin wrappers.
- Language-aware internal links should go through the `localized_url` template filter (`staticpages/templatetags/localized_urls.py`) so stored URLs keep the current locale prefix when language features are enabled.
- Routes are wrapped by the shared localized URL builder in `core/urls/common.py`, so static pages can live under language prefixes without duplicating route declarations.

## Rendering CKEditor Content
- CKEditor 5 stores image alignment and resizing as classes (`.image.image-style-align-left`, `.image.image_resized`, `figure.table`), so rendering its HTML needs the rules that act on those classes. They live in `static/common/core/css/ck-content.css`, linked from `templates/common/staticpages/staticpage.html`.
- The element wrapping the content must carry the `ck-content` class, otherwise none of the stylesheet matches. `static/common/staticpages/css/staticpage.css` is the page's own (currently empty) hook and is not where these rules belong.
- `ck-content.css` is a hand-kept subset of the `.ck-content` section of the bundled `django_ckeditor_5/dist/styles.css`. The bundled file is 230 kB, includes the editor chrome, and sets the font, size and line height of `.ck-content`, which would replace the site typography on every content page. Re-check the subset when `django-ckeditor-5` is upgraded; `core/tests/test_ckeditor.py` parses the stylesheet and fails if one of the image rules loses the declaration that places the image.
- An association template that overrides `extra_head` must call `{{ block.super }}`. `templates/pulterit/staticpages/staticpage.html` used not to, which dropped both stylesheets on pulterit pages.
- The association `base.css` files cap content images with `.content img { width: auto !important; height: auto !important; max-height: 35vh }`. `ck-content.css` releases all three for an image inside `.image.image_resized`, because the width the editor stored on the figure would otherwise be ignored and the aspect ratio squashed once the width is forced. The cap still applies to every other content image.
- A resized inline image is the one case left broken. CKEditor stores that width on the `img` element itself, and `.content img { width: auto !important }` outranks an inline style, so the stored width is ignored. No rule in `ck-content.css` can bring it back, because CSS cannot read the inline value again once an important rule has won. Dropping the two `!important` flags from the `.content img` block in every association `base.css` and in `static/common/lucia/css/style.css` fixes it; measured on layout that changes nothing except the inline case, but the selector reaches every rich text page on every site, so it wants its own change. Only pasted or source edited content can hold an inline image, because the toolbar does not offer the inline image style.
- `news/article.html`, `ctf/*`, `lucia/*` and `events/detail.html` render CKEditor HTML through a plain `.content` wrapper, so alignment, resizing and tables there still fall back to the unaligned defaults. They each need the `ck-content` class and a stylesheet link to render like the editor does. `events/detail.html` also wraps the content in a `<p>`, which makes the parser hoist `figure` and `table` out of the paragraph.

## Admin/Ordering
- `StaticPageNavAdmin` allows inline management of `StaticUrl` rows using `admin-ordering`. Dragging rows updates the `dropdown_element`; category and dropdown URLs render quick open links for checking destinations.
- `StaticPageAdmin` lists pages with `members_only` badge, per-language translation coverage, and public-page links for quick auditing. The slug field is prepopulated from the title on new pages. When language features are enabled, the local language tabs show one translated title/content version at a time without relying on an external JavaScript CDN.

## Extending the App
- Distinguish between external URLs and internal paths when adding menu links. External URLs should remain absolute; internal paths should stay relative so `localized_url` can rewrite them.
- If you add more visibility rules, update both the model fields and the shared navigation template logic together.
- To add versioning, introduce a `StaticPageRevision` model storing snapshots when `update()` runs.
- To support scheduling, add `publish_at`/`unpublish_at` fields and filter in the view before rendering.
- Consider caching navigation structures if menu lookups become expensive; currently everything hits the database on each request.
