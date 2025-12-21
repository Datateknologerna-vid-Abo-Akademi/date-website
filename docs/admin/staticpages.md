# Static Pages Admin Guide

## Purpose
Manage the informational pages and navigation links that live under the "About", "Föreningen", etc. sections of the site.

## Key Concepts
- **Static Page Nav** – top-level navigation categories (e.g., "Föreningen"). Each category can optionally point visitors straight to a custom URL.
- **Static Page** – rich-text content (CKEditor) that lives at `/s/<slug>/`. Pages can be limited to logged-in members.
- **Static URL** – manual links that appear under a category’s dropdown (can point anywhere, not just static pages).

## Manage Navigation Categories
1. In admin go to **Staticpages › Static page navs** (`/admin/staticpages/staticpagenav/`).
2. Click **Add** or edit an existing category.
3. Fields:
   - **Kategori** – visible name in the menu.
   - **Nav element** – manual ordering number (use increments of 10 to leave room).
   - **Använd kategorins URL** – if checked, visitors clicking the category go directly to the URL below instead of showing dropdown entries.
   - **Url** – external/internal destination used when the checkbox above is ticked.
4. Save, then use the inline table to add **Static URLs** (dropdown entries). Drag handles in the inline list to reorder.

## Create/Update Static Pages
1. Open **Staticpages › Static pages** (`/admin/staticpages/staticpage/`).
2. Click **Add**.
3. Fill in:
   - **Titel** – shown as page header and used for SEO.
   - **Slug** – auto-generated, stays in the final URL. Keep lowercase without spaces.
   - **Innehåll** – write/edit content using the CKEditor toolbar.
   - **Kräv inloggning** – tick if only members may read the page; anonymous visitors will be redirected to the login screen.
4. Save. The `Modifierad` timestamp updates automatically when you edit later.

## Add Dropdown Links (Static URLs)
1. Inside a category edit page, use the inline table:
   - **Titel** – link text.
   - **Url** – destination (can be `/s/<slug>/`, `/members/...`, or an external site).
   - **Visa endast åt inloggade användare** – hide the link from anonymous visitors.
   - **#** – ordering token; increments of 10 keep the list tidy.
2. Save the category to persist link changes.

## Tips for Editors
- If a page should be linked from navigation, create the Static Page first, copy its slug, then create a Static URL entry that points to `/s/<slug>/`.
- Use the preview icon in CKEditor to check layout before publishing.
- Keep `members_only` pages organized; add “(endast medlemmar)” to their titles so visitors know why they might need to log in.
