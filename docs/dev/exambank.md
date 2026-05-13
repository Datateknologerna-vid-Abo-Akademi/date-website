# Exam Bank Development Notes

## Scope
The `exambank` app owns exam archive collections and exam files. It replaced the previous `archive.Collection(type="Exams")` plus `archive.Document` rows used for exams.

## Models
- `ExamArchive` stores the archive title, publication date, and migrated `hide_for_gulis` flag.
- `ExamFile` stores the uploaded file and display title.
- Upload paths stay compatible with the previous archive layout: `<year>/<archive>/<filename>`.

## Migration Notes
- `archive.0008_remove_picture_collection_delete_examcollection_and_more` copies legacy `archive.Collection(type="Exams")` rows into `exambank_examarchive` and related `archive.Document` rows into `exambank_examfile`.
- Primary keys are preserved where possible.
- `archive.0008_remove_picture_collection_delete_examcollection_and_more` removes old exam proxy models from Django state after copying data and drops the copied legacy exam collection rows after the replacement rows exist in `exambank`.

## Routing
Public routes are still exposed through `archive.urls` under `/archive/exams/...` with the existing `archive:exams`, `archive:exams_detail`, `archive:exam_upload`, and `archive:exam_archive_upload` names.

The app intentionally renders the shared `archive/...` templates so the public archive pages keep their historical layout while the data ownership lives in `exambank`.
