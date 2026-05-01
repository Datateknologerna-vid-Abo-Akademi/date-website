# Social Admin Guide

## Purpose
Manage Instagram embeds on the home page and process harassment reports submitted via the public form.

## Instagram Links
1. In `/admin`, open **Social › Ig urls**.
2. Each row stores:
   - **URL** – full Instagram post URL.
   - **SHORTCODE** – the concise identifier used by the front page component.
3. Add new entries for posts you want highlighted. Remove old ones to prevent stale embeds.

## Harassment Reports
1. Submitted via `/social/harassment/`. The form saves a record and emails the configured recipients.
2. Review submissions under **Social › Harassments**:
   - Use the list to track follow-ups. Each entry stores an optional email address plus the message (max 1500 chars).
   - Mark reports as handled by adding admin notes or exporting the text (no status field exists yet).
3. To change who receives notifications, edit **Social › Harassment email recipients** and add/remove addresses.

## Email Workflow
- When a new report arrives, every recipient gets an email with a direct link to the admin detail page (`/admin/social/harassment/<id>/`). Use that page to update internal case notes.

## Tips
- For privacy, never add reporter comments to public channels. Use secure messaging when forwarding details outside the platform.
- If spam becomes an issue, confirm the Cloudflare Turnstile captcha keys are active (the form checks `cf-turnstile-response`).
