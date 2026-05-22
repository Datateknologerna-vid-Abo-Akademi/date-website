# Harassment Development Notes

## Responsibility
The `harassment` app owns the public harassment report form, stored submissions, recipients, and notification email flow.

The old public route and reverse name stay available as `/social/harassment/` and `social:harassment` through `social.urls`.

## Models
- `Harassment` captures anonymous or attributed reports with optional email plus a free-text message.
- `HarassmentEmailRecipient` stores the notification recipient list.

## Forms & Views
- `HarassmentForm` is a simple `ModelForm` that adds Bootstrap classes. The captcha token is read directly from `request.POST['cf-turnstile-response']`.
- `harassment.views.harassment_form` handles the PRG flow:
  - Shows the success page once when the `harass_submitted` session flag is set.
  - On POST with valid form and captcha, saves the report, schedules notification email after commit, sets the session flag, and redirects back to itself.

## Email Template
- `templates/social/harassment_admin_email.html` receives `harassment` and `harassment_url`.
- `harassment_url` points at `/admin/harassment/harassment/<id>/`.

## Migration Notes
- Data was split out from `social.Harassment` and `social.HarassmentEmailRecipient`.
- The split migration preserves primary keys and drops the legacy social tables after copying.

## Extending
- Add status fields such as `is_reviewed` or `assigned_to` here if case management becomes more formal.
- Add throttling or rate limiting if the public form sees abuse.
