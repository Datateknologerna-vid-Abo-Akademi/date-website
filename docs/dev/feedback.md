# Feedback Development Notes

## Responsibility
The `feedback` app owns `/forms/`: a single, fixed public feedback form. There is no admin-configurable form builder and no per-form slug - one form, one URL, same shape for every association. This is a separate app from `harassment` - the two forms live at their own URLs, save to their own models, and are reviewed in their own admin sections; there is no shared page or shared model between them.

## Models
- `FeedbackSubmission` captures a feedback submission with an optional email plus a free-text message (max 1500 chars).
- `FeedbackEmailRecipient` stores the feedback notification recipient list, structurally the same idea as `harassment.HarassmentEmailRecipient` but a completely separate table - harassment reports still notify `harassment.HarassmentEmailRecipient`s.
- `FeedbackFormSettings` is a singleton row (`get_solo()`, `pk=1`, mirrors `exambank.ExamBankAccessSettings`'s pattern) holding the small amount of copy an admin can edit without a code change - currently just `intro_text`, the paragraph shown above the form. `feedback.translation.py` registers `intro_text` with `django-modeltranslation`, so it gets `intro_text_sv`/`intro_text_en`/`intro_text_fi` columns like any other translated content field (see the Translations section in `AGENTS.md`); the form template just reads `{{ intro_text }}` and modeltranslation resolves the active language.

## Forms & Views
- `FeedbackSubmissionForm` is a simple `ModelForm` that adds Bootstrap classes to its fields. The captcha token is read directly from `request.POST['cf-turnstile-response']`.
- `feedback.views.feedback_form` follows the same PRG (Post-Redirect-Get) pattern as `harassment.views.harassment_form`: on a valid POST (`form.is_valid()` before `validate_captcha(...)`, so an invalid submission never triggers the outbound Cloudflare call) it saves the submission, enqueues a notification email after commit if any recipients are configured, sets a one-shot session flag, and redirects back to `/forms/`; the next GET consumes that flag and renders the thank-you page instead of the form. It also calls `FeedbackFormSettings.get_solo()` on every GET/re-render to pass `intro_text` into the template context.

## URL Routing
- Registered as the `'forms'` entry in `core.urls.common.ROUTES`, mounted at `forms/` with a single route (`''`, i.e. the form lives directly at `/forms/`).
- Each association opts in individually via its own `core/urls/<variant>.py`'s `build_urlpatterns(...)` call, same pattern as `'pages'`. Also listed in each variant's `INSTALLED_APPS` (next to `'staticpages'`) and in `core/tests/test_url_route_parity.py`'s `EXPECTED_PREFIXES`.

## Email Template
- `templates/common/feedback/feedback_admin_email.txt` receives `submission` and `submission_url`.
- Plain-text `.txt` template, same reasoning as `harassment`'s: djlint does not rewrite meaningful email whitespace in `.txt` files.

## Admin
- `FeedbackSubmissionAdmin` and `FeedbackEmailRecipientAdmin` are both plain `ModelAdmin`s - no inlines, no per-form scoping, since there's only one feedback form.
- `FeedbackFormSettingsAdmin` locks the row count to one: `has_add_permission` refuses once a row exists, `has_delete_permission` always refuses. When `ENABLE_LANGUAGE_FEATURES` is on it uses the same `ActiveLanguageTranslationAdminMixin` + `LanguageTabbedTranslationAdmin` combination as `functionaries.FunctionaryRoleAdmin`, so the change form shows per-language tabs for `intro_text`; otherwise it falls back to a plain `ModelAdmin`.
- All three are surfaced in the custom sidebar (`core/admin_ui.py`'s `SIDEBAR_NAVIGATION`) under **Social & Ads**, as **Feedback**, **Feedback Recipients**, and **Feedback Settings**, alongside the separate Harassment entries.

## History
- Earlier iterations of this app explored admin-created forms addressable by slug (`FeedbackForm`, `/forms/<slug>/`), and later a single page combining feedback with the harassment report form as two switchable panels. Both were dropped before shipping in favor of a plain, standalone form - there's no migration history to preserve either way.

## Extending
- Add throttling or rate limiting if the form sees abuse, same consideration as `harassment`.
