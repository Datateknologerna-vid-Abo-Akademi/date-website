# Feedback Admin Guide

## Purpose
Review feedback submitted through the public form at `/forms/`, and maintain the notification recipient list. This is separate from harassment reports - see the Harassment Admin Guide for those.

## Feedback Submissions
1. Review submissions under **Social & Ads › Feedback**.
2. Each entry stores an optional email address plus the message, capped at 1500 characters.
3. Reading submissions requires staff access plus the `feedback.view_feedbacksubmission` permission (superusers have everything). The notification email links to `/admin/feedback/feedbacksubmission/<id>/`, which needs at least that permission to open: a recipient whose account is not staff, or whose group lacks the permission, gets a permission error from the link even though the email arrived.

## Feedback Recipients
1. Open **Social & Ads › Feedback Recipients**.
2. Add or remove recipient email addresses.
3. Every recipient receives an email when a new feedback submission is saved.
4. If no recipients are configured, submissions are still saved - they just don't trigger an email. Check the submission list periodically if you'd rather not set up recipients.
5. The form asks the visitor to accept the terms and conditions before an email address is accepted. That consent is checked by the server when the form is submitted and is not stored with the submission, so it does not appear in this list.

## Email Workflow
- New feedback submissions enqueue a notification email after the database transaction commits, linking to `/admin/feedback/feedbacksubmission/<id>/`.
- If no recipient is configured the submission is still saved and no email is sent; the server logs a warning (`No feedback recipients configured`) so a misconfigured association is visible to operators.

## Feedback Settings
1. Open **Social & Ads › Feedback Settings** to edit the introduction text shown above the form on `/forms/`. This needs staff access plus the `feedback.view_feedbackformsettings`/`feedback.change_feedbackformsettings` permissions.
2. There is only one settings row that matters: the one with the lowest id, seeded by a migration when the site is deployed. The list shows only that row and the change page only lets you edit it, because that is the row the public page reads. A row created outside the admin at a higher id is ignored and does not appear in the admin.
3. The admin page won't let you add or delete the settings row.
4. If the site has the multilingual UI enabled (`ENABLE_LANGUAGE_FEATURES`), the change form shows a tab per language so each translation of the text can be edited separately. That flag defaults to off and means the site runs Swedish only: the change form then shows a single **Introduktionstext** field, the Swedish column (`intro_text_sv`) the public page actually reads. Edit that field; any other `intro_text` column the admin used to list was not the one taking effect.

## Deployment
- Configure the Turnstile keys per association: `CAPTCHA_SITE_KEY` and `TURNSTILE_SECRET_KEY`. `core/utils.validate_captcha` treats an empty `TURNSTILE_SECRET_KEY` as "captcha disabled" and accepts every submission, so an association that never configured the secret gets no bot protection on this form (or on the harassment form or member signup, which share the same check). That fail-open default is deliberate and used by development and the test suite, so treat it as a deployment setting to verify, not as a bug in the form.
- Make the form reachable before announcing it: nothing in the site links to `/forms/` at runtime. Navigation is database driven, so an editor adds a static URL entry (or a link from a static page) pointing at `/forms/` in the admin. `scripts/generate_dynamic_fixtures.py` seeds a **Feedback** navigation entry for local development only; dev fixtures are not loaded in production, so the entry has to be created per association.

## Tips
- There is one feedback form for the whole site - it always has the same fields (a message, an optional email, and the terms consent). There is no way to add custom fields or create additional feedback forms from the admin.
- If spam becomes an issue, confirm the Cloudflare Turnstile captcha keys are active.
