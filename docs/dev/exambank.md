# Exam Bank Development Notes

## Scope
The `exambank` app owns exam archive collections and exam files. It replaced the previous `archive.Collection(type="Exams")` plus `archive.Document` rows used for exams.

## Models
- `ExamArchive` stores the archive title, publication date, and migrated `hide_for_gulis` flag.
- `ExamBankAccessSettings` is a singleton configuration row for the whole public exam bank. It defaults to member sign-in, can disable sign-in, and can store an optional hashed shared password.
- `ExamFile` stores the uploaded file and display title.
- Upload paths stay compatible with the previous archive layout: `<year>/<archive>/<filename>`.

## Access Control
Exam views use the `exambank.views.exam_bank_access_required` gate instead of URL-level `login_required`. This keeps the same policy on the index, detail, and upload routes whether they are mounted through `archive.urls`, `exambank.archive_urls`, or `exambank.urls`.

When `require_sign_in=True`, access follows the historical member check. When it is false and a password is configured, successful password entry stores the current password hash in the session so changing the password invalidates existing grants. When sign-in is disabled and no password is configured, the exam bank routes are public.

Failed password submissions are rate-limited per session: after `EXAM_BANK_PASSWORD_ATTEMPT_LIMIT` (5) failures the gate returns HTTP 429 and refuses further attempts for `EXAM_BANK_PASSWORD_LOCKOUT_SECONDS` (15 minutes). A successful entry clears the counter.

## Admin
`ExamBankAccessSettings` is edited through an **Åtkomstinställningar** tool link on the `ExamArchiveAdmin` changelist. The singleton settings model is hidden from the app index/sidebar so editors manage exams and their access policy from one exam-bank entry point.

## Migration Notes
- `archive.0008_remove_picture_collection_delete_examcollection_and_more` copies legacy `archive.Collection(type="Exams")` rows into `exambank_examarchive` and related `archive.Document` rows into `exambank_examfile`.
- Primary keys are preserved where possible.
- `archive.0008_remove_picture_collection_delete_examcollection_and_more` removes old exam proxy models from Django state after copying data and drops the copied legacy exam collection rows after the replacement rows exist in `exambank`.

## Routing
Public routes are still exposed through `archive.urls` under `/archive/exams/...` with the existing `archive:exams`, `archive:exams_detail`, `archive:exam_upload`, and `archive:exam_archive_upload` names.

Association variants that install `exambank` without the full `archive` app, such as Pulterit, mount `exambank.archive_urls` under `/archive/` so the exam-only compatibility routes keep the same public paths and URL names.

The app intentionally renders the shared `archive/...` templates so the public archive pages keep their historical layout while the data ownership lives in `exambank`.

## Navigation Visibility
The `staticpages.context_processors._visible_urls_queryset` and `get_categories` helpers hide nav entries whose URL starts with `/archive/` when `ARCHIVE_ENABLED=False`. When `exambank` is in `INSTALLED_APPS`, entries under `/archive/exams/` are kept visible so the exam compatibility routes remain reachable from the menu. The trailing slash is significant — only `/archive/exams/...` is exempted, not unrelated prefixes such as `/archive/examined/`.
