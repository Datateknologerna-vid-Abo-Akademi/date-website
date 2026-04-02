# Alumni Development Notes

## Architecture Overview
- No traditional database tables for members; instead, we write to Google Sheets via `DateSheetsAdapter` (see `alumni/gsuite_adapter.py`).
- Celery tasks (`alumni/tasks.py`) handle all side effects—sheet writes, email dispatch, audit logging, and token emails.
- Two lightweight models live in Django:
  - `AlumniEmailRecipient` – list of admin recipients for notifications.
  - `AlumniUpdateToken` – UUID tokens for edit links with a 24h validity window.

## Forms & Views
- `AlumniSignUpForm` collects create/update data. The `operation` field defaults to `CREATE` but the same form class is reused for updates.
- `alumni.views.alumni_signup` validates captcha, checks duplicates against Sheets, and enqueues `handle_alumni_signup.delay()`.
- `alumni_update_verify` asks for an email, creates a token, and fires `send_token_email.delay()`.
- `alumni_update_form` verifies the token, pre-fills the form, and on POST triggers the same `handle_alumni_signup` task with `operation=UPDATE`.

## Task Flow
- `handle_alumni_signup` pattern-matches on `operation`:
  - **CREATE** → `handle_create` appends a row to the member sheet, generates a payment reference number, sends both alumni and admin emails, and logs to the audit sheet.
  - **UPDATE** → `handle_update` finds the row by email, updates only the editable columns, logs the action, and deletes the token.
- `send_token_email` verifies the request email actually exists in the sheet before sending a template-based message.

## Configuration
- `settings.ALUMNI_SETTINGS` must contain JSON with Google API credentials and sheet IDs. Missing/invalid settings are logged as errors and disable the integration.
- Email templates live under `templates/members/` and `templates/alumni/`.

## Extending
- To expose recipient management in admin, register `AlumniEmailRecipient` with a simple `ModelAdmin` (currently unregistered).
- Consider encrypting the token payload or adding rate limiting to avoid brute-force attempts.
- For better observability, persist audit logs inside Django in addition to Google Sheets.
