# Static Pages Admin Guide

## Purpose
Manage the informational pages and navigation links that live under the "About", "Föreningen", etc. sections of the site.

## Key Concepts
- **Static Page Nav** – top-level navigation categories (e.g., "Föreningen"). Each category can optionally point visitors straight to a custom URL.
- **Static Page** – rich-text content (CKEditor) that lives at `/pages/<slug>/`. Pages can be limited to logged-in members.
- **Static URL** – manual links that appear under a category’s dropdown (can point anywhere, not just static pages).

## Manage Navigation Categories
1. In admin go to **Staticpages › Static page navs** (`/admin/staticpages/staticpagenav/`).
2. Click **Add** or edit an existing category.
3. Fields:
   - **Kategori** – visible name in the menu.
   - **Nav element** – manual ordering number (use increments of 10 to leave room).
   - **Använd kategorins URL** – if checked, visitors clicking the category go directly to the URL below instead of showing dropdown entries. The URL is required in that case.
   - **Url** – external/internal destination used when the checkbox above is ticked. The field suggests the site's own pages while you type, but you can still type any external address or path.
4. Save, then use the inline table to add **Static URLs** (dropdown entries). Drag handles in the inline list to reorder.
5. Existing category and dropdown URLs show quick **Open** links so you can check destinations without leaving the admin workflow.

## Create/Update Static Pages
1. Open **Staticpages › Static pages** (`/admin/staticpages/staticpage/`).
2. Click **Add**.
3. Fill in:
   - **Titel** – shown as page header and used for SEO.
   - **Slug** – auto-generated, stays in the final URL. Keep lowercase without spaces.
   - **Innehåll** – write/edit content using the CKEditor toolbar.
   - **Bakgrundsbild** – optional background image. The form shows the local field or the public S3 field depending on how this deployment stores media, so there is only one image field to fill.
   - **Kräv inloggning** – tick if only members may read the page; anonymous visitors will be redirected to the login screen.
4. Save. The `Modifierad` timestamp updates automatically when you edit later.
5. Use the **Public page** link from the list or edit form to open the rendered page.
6. The **I menyn** row on the edit form shows which navigation entries point at this page and links to the category that owns them. A page that is not linked yet shows **Sidan finns inte i menyn** with a link to the navigation list.

## Add Dropdown Links (Static URLs)
1. Inside a category edit page, use the inline table:
   - **Titel** – link text.
   - **Url** – destination. Start typing and pick one of the site's own pages from the suggestions, or type `/members/...` or an external `https://` address by hand.
   - **Visa endast åt inloggade användare** – hide the link from anonymous visitors.
   - **#** – ordering token; increments of 10 keep the list tidy.
   - **Parent** – leave empty for a normal dropdown entry. Pick another entry to nest this link under it as a submenu item (see below); the link moves to that entry's category when saved.
2. Save the category to persist link changes.

### Submenus (nested links)
A link with a **Parent** appears under that parent instead of in the dropdown itself, on every association's site:
- On a computer, the submenu opens when the visitor hovers over the parent or reaches it with the keyboard. A parent without a **Url** also opens on click or tap, so give it no Url if the parent is only a heading for its children.
- A parent that has a **Url** still goes to that address when clicked, so tablet visitors who cannot hover reach its children only through the parent's own page. Prefer a parent without a Url when its children matter.
- In the narrow mobile menu every submenu is always shown, indented under its parent.
- Only one level is allowed: a link that is itself a child cannot be picked as a parent.
- A child without a **Url** is not shown, and a parent whose children are all hidden (no Url, or **Visa endast åt inloggade användare** for an anonymous visitor) shows as a normal link, or not at all if it has no Url either.
- A login link (`/members/login/`) turns into **Logga ut** for signed-in members, also when it is a child or a parent.

Urls must be a full address (`https://...`, `mailto:` or `tel:`) or an internal path starting with `/`. A bare relative path such as `pages/om-oss/` is rejected, because it would render as a broken link.

## Editor Options
The **Innehåll** field uses the shared CKEditor configuration (`core/settings/dependencies/ckeditor.py`), which offers:
- **Images** - insert, upload or link an image, set the alternative text, add a caption, and pick an alignment (left, right, center or side) or a size from the resize list. Use **No hover effect** on a linked image when the hover zoom is distracting.
- **Text alignment** - left, center, right and justify for paragraphs and headings.
- **Tables** - insert a table, add or remove its caption, merge cells, and set borders and background colors.
- **Lists** - bulleted, numbered and to-do lists, with bullet style, start number and reversed order.
- **Find and replace** - search the current field, which is quicker than scrolling on a long page.
- **Special characters** - insert characters that are awkward to type, such as section signs and typographic quotes.
- **Horizontal line**, **Show blocks** and **Source editing** for structure, and for fixing markup by hand.

Uploads accept jpg, jpeg, png, gif, bmp, webp and tiff. An image you add with **Insert image** is a block image, which is what the resize list works on: it keeps the size you pick, and one you leave alone is capped to a share of the viewport height so a single large photo cannot dominate the page. An image that arrives inline from pasted content is not resized by that list, because the site caps those at their natural size. Delete it and add it again with **Insert image** to get a resizable one. A table wider than the screen scrolls sideways on a phone instead of shifting the whole page.

## Tips for Editors
- If a page should be linked from navigation, create the Static Page first, then add a Static URL entry and pick the page from the URL suggestions; there is no need to copy the slug by hand.
- If translation features are enabled, category names and link labels can have per-language values. Check the translated fields before publishing multilingual navigation changes.
- CKEditor has no preview plugin here, so check the layout with the **Public page** link from the list or the edit form rather than from inside the editor.
- Keep `members_only` pages organized; add “(endast medlemmar)” to their titles so visitors know why they might need to log in.
