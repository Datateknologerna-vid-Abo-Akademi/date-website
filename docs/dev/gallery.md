# Gallery Development Notes

## Scope
The `gallery` app owns photo albums and uploaded photos. It replaced the previous `archive.Collection(type="Pictures")` and `archive.Picture` responsibility.

## Models
- `Album` stores the album title, publication date, and `hide_for_gulis` access flag.
- `Photo` stores image files and compresses newly uploaded images to 1600px-wide JPEGs in `Photo.save()`.
- Upload paths stay compatible with the previous archive layout: `<year>/<album>/<filename>`.

## Migration Notes
- `gallery.0002_copy_archive_pictures` copies legacy `archive.Collection(type="Pictures")` rows into `gallery_album` and related `archive.Picture` rows into `gallery_photo`.
- Primary keys are preserved where possible so existing links and admin references stay predictable.
- The migration does not delete legacy archive rows; `archive.0008_remove_picture_collection_delete_examcollection_and_more` removes the old models from Django state without dropping legacy tables.

## Routing
Public routes are still exposed through `archive.urls` under `/archive/pictures/...` with the existing `archive:years`, `archive:pictures`, `archive:detail`, and `archive:upload` names.
