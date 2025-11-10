# Social Development Notes

## Models
- `IgUrl` – stores `url` and `shortcode` for Instagram embeds used on the home page.
- `Harassment` – captures anonymous or attributed reports with optional email + free-text message.
- `HarassmentEmailRecipient` – mailing list for notifications.

## Forms & Views
- `HarassmentForm` is a simple `ModelForm` that adds Bootstrap classes. No captcha field is defined in the form; the view reads `cf-turnstile-response` directly from `request.POST`.
- `social.views.harassment_form` handles GET/POST:
  - Checks a session flag (`harass_submitted`) to show the success page once and then reset it.
  - On POST + valid captcha, saves the form, emails recipients via `core.utils.send_email_task`, sets the session flag, and redirects to self (PRG pattern).
- `socialIndex` currently renders a placeholder template.

## Email Template
- `templates/social/harassment_admin_email.html` receives `harassment` and `harassment_url`. The URL targets the admin detail view so staff can respond.

## Admin
- All models registered with default `ModelAdmin` for quick CRUD. Consider adding filters/search if the list grows.

## Integrations
- Email sending relies on Celery (`send_email_task.delay`). Ensure the worker is running; otherwise submissions will queue indefinitely.
- `settings.CONTENT_VARIABLES['SITE_URL']` must be configured so the email includes a correct absolute link.

## Extending
- Add status fields (e.g., `is_reviewed`, `assigned_to`) to `Harassment` for better case management.
- For IG embeds, consider fetching metadata automatically via Instagram Basic Display API instead of manual shortcodes.
- Add throttling or rate limiting if the harassment form sees abuse.
