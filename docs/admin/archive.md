# Archive Admin Guide

## Purpose
Manage document archives and public files. Photo galleries are managed in **Gallery › Albums** and exam libraries are managed in **Exam bank › Exam archives**.

## Document Collections
1. Open **Archive › Document collections**.
2. Create a collection with title and publication date. The publication date uses the shared calendar/time picker.
3. Use the inline table to upload one or many files.
4. Save. Files are stored under `media/documents/<year>/<slug>/`.

## Public Files (S3 only)
When `USE_S3=True`, **Public collections** appear in admin. Manage them like document collections, but uploads go through `PublicFileField` so they are web-accessible without authentication.

## Tips
- Use consistent naming and pub dates so archives stay orderly.
- Deleting a collection also deletes its directory inside `MEDIA_ROOT`, so double-check before removing.
- Public browsing still uses the `/archive/...` URL area even though photos and exams are managed by separate apps.
