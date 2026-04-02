# Archive Development Notes

## Models
- `Collection` is the polymorphic base with `title`, `type`, `pub_date`, and `hide_for_gulis`. Proxy subclasses (`PictureCollection`, `DocumentCollection`, `ExamCollection`, `PublicCollection`) provide separate admin menus.
- `Picture` (ImageField) compresses uploads to JPEG via `compress_image` before saving. When `USE_S3=False`, deletions remove the underlying file manually.
- `Document` stores arbitrary files tied to a collection.
- `PublicFile` uses `PublicFileField` for S3/public storage.
- `TYPE_CHOICES` determines directory structure via `upload_to()`, producing tidy `/documents/<year>/<collection>/` paths, etc.

## Forms & Admin
- `PictureAdminForm`/`DocumentAdminForm`/`PublicAdminForm` add multi-upload widgets and iterate over `self.files.getlist()` to create associated objects after the collection saves.
- Admin classes filter `get_queryset()` by `type` so proxy models only show their relevant records. Inline previews use `mark_safe` to render thumbnails.

## Views
- Access control: decorators (`@user_passes_test(user_type)`) reject freshmen (permission profile 3) when needed and force login via `/members/login/`.
- `year_index`, `picture_index`, and `picture_detail` handle browsing and pagination for photo galleries. 2022 albums keep chronological order; others are reversed.
- `FilteredDocumentsListView` and `FilteredExamsListView` combine `django-filter` and `django-tables2` for searching by title/category.
- Upload helpers (`upload`, `exam_upload`, `exam_archive_upload`) require staff permissions and reuse the same forms as admin for bulk operations.

## Storage Considerations
- `Collection.delete()` removes the physical directory in `MEDIA_ROOT`. Ensure backups exist before mass deletions.
- Public files require `USE_S3=True` because `PublicFileField` expects a storage backend with signed URLs.

## Extending
- Add tagging or metadata (e.g., photographer, description) to `Picture` if Getty-style search is needed.
- Move compression to async tasks if uploads become slow; currently handled synchronously in `Picture.save()`.
- Replace manual `user_type` checks with Django permissions or groups for more flexibility.
