# Harassment Admin Guide

## Purpose
Review harassment reports submitted through the public form and maintain the notification recipient list.

## Harassment Reports
1. Reports are submitted via `/social/harassment/`.
2. Review submissions under **Social & Ads › Harassment Reports**.
3. Each entry stores an optional email address plus the message, capped at 1500 characters.
4. There is no workflow status field yet, so track follow-up outside the public site or add explicit status fields before relying on admin notes.

## Report Recipients
1. Open **Social & Ads › Report Recipients**.
2. Add or remove recipient email addresses.
3. Every recipient receives an email when a new report is saved.

## Email Workflow
- New reports enqueue notification email after the database transaction commits.
- The email links directly to `/admin/harassment/harassment/<id>/`.

## Tips
- For privacy, never add reporter comments to public channels.
- If spam becomes an issue, confirm the Cloudflare Turnstile captcha keys are active.
