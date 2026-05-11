# Exam Bank Development Notes

## Scope
The `exambank` app owns exam archive collections and exam files. It replaced the previous `archive.Collection(type="Exams")` plus `archive.Document` rows used for exams.

## Models
- `ExamArchive` stores the archive title, publication date, and migrated `hide_for_gulis` flag.
- `ExamFile` stores the uploaded file and display title.
- Upload paths stay compatible with the previous archive layout: `Exams/<year>/<archive>/<filename>`.

## Migration Notes
- `exambank.0002_copy_archive_exams` copies legacy `archive.Collection(type="Exams")` rows into `exambank_examarchive` and related `archive.Document` rows into `exambank_examfile`.
- Primary keys are preserved where possible.
- The migration does not delete legacy archive rows; `archive.0008_remove_picture_collection_delete_examcollection_and_more` removes old exam proxy models from Django state without dropping legacy tables.

## Routing
Public routes are still exposed through `archive.urls` under `/archive/exams/...` with the existing `archive:exams`, `archive:exams_detail`, `archive:exam_upload`, and `archive:exam_archive_upload` names.
