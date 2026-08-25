# Gallery Admin Guide

## Purpose
Manage photo albums shown under `/archive/pictures/`.

## Adding A Photo Gallery
1. Visit **Gallery › Albums**.
2. Click **Add album**.
3. Fill in:
   - **Namn**: gallery title, also used in media folder paths.
   - **Pub date**: determines which year bucket the gallery appears under and uses the shared calendar/time picker.
   - **Göm för gulisar**: hide sensitive albums from freshmen.
4. Upload photos in the inline table or with the multi-upload field.
5. Save. With direct uploads enabled, images are compressed client-side before upload; otherwise the server compresses them to 1600px width for performance.

## Notes
- Public URLs remain `/archive/pictures/<year>/...`.
- The **Städa upp media** admin link still points to the shared archive cleanup route.
- iPhone photos (HEIC/HEIF) are supported and get converted to JPEG like any other upload.
- If a file can't be read as an image (corrupted upload, unsupported format), it's skipped and a warning naming the file is shown after saving — the rest of the uploaded photos still save normally.
