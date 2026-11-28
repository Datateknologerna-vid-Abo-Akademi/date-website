# Klotterplanket Development Notes

## Responsibility
The `klotterplanket` app owns the public "klotterplanket" (scribble board) page: a list of anonymous posts plus a form for adding new posts. Posts are written with a pseudonym, never linked to a member account.

## Models
- `Post` stores `pseudonym` (max 50 chars), `content` (max 1000 chars), and `created_at` (`auto_now_add`). Default ordering is newest first.

## Forms & Views
- `PostForm` is a simple `ModelForm` that adds Bootstrap classes to both fields.
- `klotterplanket.views.index` renders the post list and the form on one page:
  - On POST, the form is saved only when valid **and** the Cloudflare Turnstile check passes (`core.utils.validate_captcha` on `request.POST['cf-turnstile-response']`).
  - A successful save sets a `success` message and redirects back (PRG pattern).
  - The page lists at most `MAX_POSTS` (100) posts.

## Captcha / Spam Protection
- Reuses the site-wide Cloudflare Turnstile integration: `CAPTCHA_SITE_KEY` context processor and the `cf-turnstile` widget markup, same as the harassment and event signup forms.
- When `TURNSTILE_SECRET_KEY` is empty (e.g. local dev), `validate_captcha` accepts submissions, matching the behavior of the other public forms.

## Admin
- `PostAdmin` shows pseudonym, content preview, and creation time, with filtering and search. Posts can be deleted from admin if moderation is needed.

## Routing & Association Scope
- Registered as `klotterplanket` in `core/settings/sf.py` and routed at `/klotterplanket/` in `core/urls/sf.py`. Only the SF site variant installs the app; add it to another association's settings module to enable it there.
- Because the app is not part of the DaTe app set, `date-test` skips its tests (the module raises `SkipTest` when `klotterplanket` is not installed, keeping the default suite green). Run them explicitly with the SF settings module:
  ```bash
  DJANGO_SETTINGS_MODULE=core.settings.sf python manage.py test klotterplanket
  ```

## Extending
- Add rate limiting per IP if the public form sees abuse.
- Add an `approved` moderation state if pre-publication review is wanted.
