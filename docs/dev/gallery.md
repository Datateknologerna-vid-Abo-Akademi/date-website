# Gallery Development Notes

## Scope
The `gallery` app owns photo albums and uploaded photos. It replaced the previous `archive.Collection(type="Pictures")` and `archive.Picture` responsibility.

## Models
- `Album` stores the album title, publication date, and `hide_for_gulis` access flag.
- `Photo` stores image files and compresses newly uploaded images to 1600px-wide JPEGs in `Photo.save()`.
- Upload paths stay compatible with the previous archive layout: `<year>/<album>/<filename>`.
- `AlbumAdminForm` creates multi-uploaded photos in its `save_m2m()` callback so new albums are inserted before their photos reference them.
- `compress_image()` (`gallery/models.py`) raises `ImageProcessingError` for uploads Pillow can't decode (corrupt files, unsupported formats, decompression bombs) instead of letting the exception crash the request. Both `AlbumAdminForm._save_m2m()` and the public `gallery.views.upload` view catch it per file, skip the bad upload, and keep the rest of the batch; skipped filenames are surfaced via `django.contrib.messages` (admin: `AlbumAdmin.save_related`, public view: a warning message shown on redirect) and `form.skipped_images` for tests.
- `pillow-heif` is registered via `GalleryConfig.ready()` (`gallery/apps.py`), so `PIL.Image.open()`, `compress_image()`, and Django's own `ImageField` validation can decode HEIC/HEIF uploads (the default photo format on iPhones).

## Migration Notes
- `archive.0008_remove_picture_collection_delete_examcollection_and_more` copies legacy `archive.Collection(type="Pictures")` rows into `gallery_album` and related `archive.Picture` rows into `gallery_photo`.
- Primary keys are preserved where possible so existing links and admin references stay predictable.
- `archive.0008_remove_picture_collection_delete_examcollection_and_more` removes the old models from Django state after copying data and drops the copied legacy picture collection rows and the old `archive_picture` table after the replacement rows exist in `gallery`.

## Routing
Public routes are still exposed through `archive.urls` under `/archive/pictures/...` with the existing `archive:years`, `archive:pictures`, `archive:detail`, and `archive:upload` names.

The app intentionally renders the shared `archive/...` templates so the public gallery pages keep their historical layout while the data ownership lives in `gallery`.

When `ARCHIVE_ACCESS_REQUIRES_ELIGIBILITY` is enabled for SF, the shared `Member.has_archive_access()` check protects the gallery year index, yearly album index, and album detail. Both SF membership types require the individual `archive_access_eligible` flag; superusers remain allowed. Associations without the setting retain the historical permission-profile behavior.

## Admin Permissions
Legacy picture-collection permissions grant the same module and inline photo access in classic admin and Unfold during the permission migration period.
