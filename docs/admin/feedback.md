# Feedback Admin Guide

## Purpose
Review feedback submitted through the public form at `/forms/`, and maintain the notification recipient list. This is separate from harassment reports - see the Harassment Admin Guide for those.

## Feedback Submissions
1. Review submissions under **Social & Ads › Feedback**.
2. Each entry stores an optional email address plus the message, capped at 1500 characters.

## Feedback Recipients
1. Open **Social & Ads › Feedback Recipients**.
2. Add or remove recipient email addresses.
3. Every recipient receives an email when a new feedback submission is saved.
4. If no recipients are configured, submissions are still saved - they just don't trigger an email. Check the submission list periodically if you'd rather not set up recipients.

## Email Workflow
- New feedback submissions enqueue a notification email after the database transaction commits, linking to `/admin/feedback/feedbacksubmission/<id>/`.

## Feedback Settings
1. Open **Social & Ads › Feedback Settings** to edit the introduction text shown above the form on `/forms/`.
2. There's only one settings row - it's created automatically the first time it's needed, and can't be deleted or duplicated.
3. If the site has multiple languages enabled, the change form shows a tab per language so each translation of the text can be edited separately.

## Tips
- There is one feedback form for the whole site - it always has the same two fields (optional email, a message). There is no way to add custom fields or create additional feedback forms from the admin.
- If spam becomes an issue, confirm the Cloudflare Turnstile captcha keys are active.
