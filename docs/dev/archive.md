# Archive Development Notes

## Scope
The `archive` app now owns document collections and public files only. Photo galleries live in `gallery`; exam archives live in `exambank`. The public `/archive/...` URL prefix remains the shared archive area for compatibility.

## Models
- `Collection` stores document/public-file collections with `title`, `type`, `pub_date`, and `hide_for_gulis`.
- `Document` stores arbitrary files tied to a document collection.
- `PublicFile` uses `PublicFileField` for S3/public storage.
- `TYPE_CHOICES` is limited to `Documents` and `PublicFiles`; legacy `Pictures`/`Exams` rows are copied into their new app tables by split migrations and left in place as rollback data.

## Views
- `FilteredDocumentsListView` combines `django-filter` and `django-tables2` for the document archive.
- `archive.urls` delegates picture routes to `gallery.views` and exam routes to `exambank.views` so existing `archive:*` URL names continue to work.
- `clean_media` remains here because it operates on the shared media root.

## Storage Considerations
- `Collection.delete()` removes the physical directory in `MEDIA_ROOT`. Ensure backups exist before mass deletions.
- Public files require `USE_S3=True` because `PublicFileField` expects a storage backend with signed URLs.
