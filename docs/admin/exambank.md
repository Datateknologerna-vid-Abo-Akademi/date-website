# Exam Bank Admin Guide

## Purpose
Manage exam archives shown under `/archive/exams/`.

## Access Settings
Use **Exam bank › Åtkomst till tentarkiv** to choose how the public exam bank is protected.

- **Kräv inloggning** is enabled by default and keeps the historical behavior: visitors must sign in as members.
- When sign-in is disabled, an optional password can protect `/archive/exams/` and the related exam upload/detail routes. Leaving the password empty makes the exam bank public.
- The password is stored hashed; when editing an existing password, keep the placeholder value to leave it unchanged.

## Adding Exam Archives
1. Visit **Exam bank › Exam archives**.
2. Create an archive with a title and publication date. The publication date uses the shared calendar/time picker.
3. Use the inline table or multi-upload field to upload exam files.
4. Provide a descriptive **Namn** for each file.
5. Save. Files are stored under `media/<year>/<slug>/`.

## Notes
- Public URLs remain `/archive/exams/`.
- The **Städa upp media** admin link still points to the shared archive cleanup route.
