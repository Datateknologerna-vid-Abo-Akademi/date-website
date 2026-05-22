# Publications Admin Guide

## Purpose
Publish downloadable PDFs or external publication links (meeting minutes, magazines, Issuu links, etc.) inside admin-managed collections. Collections control whether visitors can see/open a group of publications.

## Access
1. Sign in to `/admin`.
2. Open **Publications › Publication collections** (`/admin/publications/publicationcollection/`) or **Publications › Pdf files** (`/admin/publications/pdffile/`).

## Create a Collection
1. Open **Publication collections** and click **Add publication collection**.
2. Complete the form:
   - **Title** – shown at `/publications/` and at the top of the collection page.
   - **Slug** – leave blank to auto-generate. This becomes the collection URL, for example `/publications/ao/`.
   - **Description** – optional intro text shown on the collection page.
   - **Cover image** – optional image shown for the collection on `/publications/`.
   - **Ordering** – lower numbers appear first on the collection index.
   - **Active** – uncheck to remove the collection from public access.
   - **Visibility** – controls who can see/open the collection:
     - **Public** – visible and open to everyone.
     - **Logged-in members** – visible/open only after login.
     - **Selected membership types** – visible/open only to logged-in users whose membership type is selected.
     - **Password protected** – visible on the index but requires the collection password before publications open.
     - **Hidden** – not listed and direct links return not found.
   - **Allowed membership types** – used only for selected-membership visibility.
   - **Password** / **Clear password** – set, replace, or remove the password. The plaintext password is not shown again.
3. Save.

## Add a New PDF
1. Click **Add pdf file**.
2. Complete the form:
   - **Collection** – choose the group where the publication should appear.
   - **Title** – shown on listings and in the viewer.
   - **Slug** – leave blank to auto-generate from the title. Together with the collection slug, this becomes the URL (`/publications/<collection>/<slug>/`).
   - **Publication Date** – used for sorting and filtering.
   - **Description** – short summary shown on the publication card.
   - **File** – upload the PDF (stored under `media/pdfs/<slug>/`) when the publication should use the internal reader.
   - **Redirect URL** – optional external reader link, such as an Issuu URL. When set, visitors are sent there instead of the internal reader. Use this instead of **File** for external-only publications.
   - **Cover image** – optional thumbnail shown in the publication list, useful for external-only publications.
   - **Public Access** – keep checked unless this individual publication should be hidden inside its collection.
   - **Requires Login** – forces a member login for this individual publication, in addition to the collection access rule.
3. Save. Upload time stamps are recorded automatically.

## Edit or Replace a PDF
- Editing shows read-only upload timestamps. To swap the actual file, create a new entry (or delete and re-create) so the file field becomes editable again.
- Updating metadata (title, description, access flags) is safe and immediate.

## Review Access Settings
- Review collection visibility first; this is the main access rule.
- List filters let you quickly find hidden PDFs (`Public Access = No`), PDF-level login requirements, or publications in a specific collection.
- Use the search bar to locate files by title or slug.

## Visitor Experience
- `/publications/` lists non-empty collections visible to the current visitor.
- `/publications/<collection>/` lists the publications in that collection with pagination.
- Clicking a PDF-backed item opens the internal viewer. Clicking an item with **Redirect URL** first opens the internal checked URL and then redirects to the external site after access is confirmed.
- Visitors without collection permission cannot access direct collection or publication links. Login-only collections redirect anonymous visitors to login, password collections show a password form, and hidden or wrong-membership links return not found.
