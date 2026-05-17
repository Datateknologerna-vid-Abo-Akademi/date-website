# Publications Admin Guide

## Purpose
Publish downloadable PDFs (meeting minutes, magazines, etc.) with optional login requirements.

## Access
1. Sign in to `/admin`.
2. Open **Publications › Pdf files** (`/admin/publications/pdffile/`).

## Add a New PDF
1. Click **Add pdf file**.
2. Complete the form:
   - **Title** – shown on listings and in the viewer.
   - **Slug** – leave blank to auto-generate from the title. This becomes the URL (`/publications/<slug>/`).
   - **Publication Date** – used for sorting and filtering.
   - **Description** – short summary shown on the publication card.
   - **File** – upload the PDF (stored under `media/pdfs/<slug>/`) when the publication should use the internal reader.
   - **Redirect URL** – optional external reader link, such as an Issuu URL. When set, visitors are sent there instead of the internal reader. Use this instead of **File** for external-only publications.
   - **Cover image** – optional thumbnail shown in the publication list, useful for external-only publications.
   - **Public Access** – keep checked unless the file should be completely hidden.
   - **Requires Login** – forces a member login before the reader opens, while still letting you link to the page publicly.
3. Save. Upload time stamps are recorded automatically.

## Edit or Replace a PDF
- Editing shows read-only upload timestamps. To swap the actual file, create a new entry (or delete and re-create) so the file field becomes editable again.
- Updating metadata (title, description, access flags) is safe and immediate.

## Review Access Settings
- List filters let you quickly find hidden PDFs (`Public Access = No`) or those gated behind login.
- Use the search bar to locate files by title or slug.

## Visitor Experience
- `/publications/` lists all allowed PDFs with pagination.
- Clicking a PDF-backed item opens the internal viewer. Clicking an item with **Redirect URL** opens the external site. Visitors without permission see either a login redirect (if `Requires Login`) or a 403 message (if not public).
