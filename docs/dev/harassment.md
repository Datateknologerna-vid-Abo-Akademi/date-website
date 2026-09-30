# Harassment Development Notes

## Responsibility
The `harassment` app owns the public harassment report form, stored submissions, recipients, and notification email flow.

The old public route and reverse name stay available as `/social/harassment/` and `social:harassment` through `social.urls`.

## Models
- `Harassment` captures anonymous or attributed reports with optional email plus a free-text message.
- `HarassmentEmailRecipient` stores the notification recipient list.

## Admin Log Redaction
- `Harassment.__str__` returns a content-free label from `harassment.redaction.report_label`, for example `Trakasserianmälan #12`. Never make it return `self.message`.
- The reason is `django_admin_log`: Django stores `str(obj)[:200]` in `LogEntry.object_repr` for every add, change, and delete, and the admin log page (Admin › Log entries) is readable by staff who are not report recipients. The same value reaches the admin success message, which the messages framework keeps in the session and the cookie.
- The label is not translated, because it is stored as an audit record and must not vary with the language active when the row was written. That also lets the cleanup command recognise an already-redacted row exactly.
- `harassment/migrations/0002_redact_admin_log_reports.py` rewrites report text that earlier releases stored in `object_repr`. Rows keep the report id, so the audit trail still shows which report was touched. It covers `harassment.harassment` and the pre-split `social.harassment` content type; both are listed in `harassment.redaction.REPORT_CONTENT_TYPES`.
- `python manage.py redact_harassment_logs` applies the same rewrite on demand and is idempotent. Migrations run before the application rolls, and a blue-green standby shares the database with the live release, so a pod running the older image can write one more content-bearing row after the migration has passed. Run the command once the old pods are gone (it is a release step, see `operations.md`), and again after any release that touched report logging. Pre-deploy database dumps still contain the text; redacting them needs the operator's backup policy, not application code.
- Keep `message_preview` on `HarassmentAdmin` as the place where authorised staff read a report, and keep the full message out of `list_display`, admin actions, and logging.

## Forms & Views
- `HarassmentForm` is a simple `ModelForm` that adds Bootstrap classes. The captcha token is read directly from `request.POST['cf-turnstile-response']`.
- `harassment.views.harassment_form` handles the PRG flow:
  - Shows the success page once when the `harass_submitted` session flag is set.
  - On POST with valid form and captcha, saves the report, schedules notification email after commit, sets the session flag, and redirects back to itself.

## Email Template
- `templates/social/harassment_admin_email.txt` receives `harassment` and `harassment_url`.
- `harassment_url` points at `/admin/harassment/harassment/<id>/`.
- Notification bodies are plain-text `.txt` templates so djlint does not rewrite meaningful email whitespace. Django template variables and tags work normally in `.txt` files; use `.html` only for an actual HTML message body.

## Migration Notes
- Data was split out from `social.Harassment` and `social.HarassmentEmailRecipient`.
- The split migration preserves primary keys and drops the legacy social tables after copying.
- Legacy `social` harassment and recipient permissions continue to grant equivalent admin access while stale content types are being migrated.

## Extending
- Add status fields such as `is_reviewed` or `assigned_to` here if case management becomes more formal.
- Add throttling or rate limiting if the public form sees abuse.
