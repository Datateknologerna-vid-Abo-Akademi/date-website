# Publications Development Notes

## Data Model (`publications/models.py`)
- `PDFFile` captures metadata, upload, and access flags. `slug` auto-fills from title if left blank and is guaranteed unique by `generate_unique_slug()`.
- `file` uses `PublicFileField`, which supports S3/alternative storage. When `USE_S3` is false, `delete()` removes the local file manually.
- `is_public` and `requires_login` are independent flags; a PDF can be hidden entirely or visible-but-gated.

## Admin (`publications/admin.py`)
- Custom `PDFFileAdmin` prepopulates slugs for new objects, exposes access controls, and locks the `file` field when editing to avoid accidental replacements.
- Fieldsets group metadata, access control, and timestamps for clarity.

## Views/URLs (`publications/views.py`)
- `pdf_list` paginates 10 items per page, filtering by login status:
  - Anonymous users: `is_public=True` and `requires_login=False`.
  - Authenticated users: any `is_public=True` file (even if `requires_login=True`).
- `pdf_view` enforces the same checks and redirects unauthenticated users to `login` if necessary. Non-public files always return HTTP 403.

## Templates
- `publications/list.html` expects `page_obj` and drives pagination controls.
- `publications/viewer.html` embeds the PDF via `pdf_url`.

## Extending
- For download tracking, introduce a `PDFDownload` model and increment in `pdf_view` before rendering.
- To support categories/tags, relate `PDFFile` to a taxonomy model and extend filters inside `pdf_list`.
- Consider caching `pdf_list` output if the library grows large; current implementation hits the database on every request.
