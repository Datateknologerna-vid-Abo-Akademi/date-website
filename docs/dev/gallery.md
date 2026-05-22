# Gallery Development Notes

## Scope
The `gallery` app owns photo albums and uploaded photos. It replaced the previous `archive.Collection(type="Pictures")` and `archive.Picture` responsibility.

## Models
- `Album` stores the album title, publication date, and `hide_for_gulis` access flag.
- `Photo` stores image files and compresses newly uploaded images to 1600px-wide JPEGs in `Photo.save()`.
- Upload paths stay compatible with the previous archive layout: `<year>/<album>/<filename>`.

## Migration Notes
- `archive.0008_remove_picture_collection_delete_examcollection_and_more` copies legacy `archive.Collection(type="Pictures")` rows into `gallery_album` and related `archive.Picture` rows into `gallery_photo`.
- Primary keys are preserved where possible so existing links and admin references stay predictable.
- `archive.0008_remove_picture_collection_delete_examcollection_and_more` removes the old models from Django state after copying data and drops the copied legacy picture collection rows and the old `archive_picture` table after the replacement rows exist in `gallery`.

## Routing
Public routes are still exposed through `archive.urls` under `/archive/pictures/...` with the existing `archive:years`, `archive:pictures`, `archive:detail`, and `archive:upload` names.

The app intentionally renders the shared `archive/...` templates so the public gallery pages keep their historical layout while the data ownership lives in `gallery`.
