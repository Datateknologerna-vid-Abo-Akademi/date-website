# Alumni Admin Guide

## Purpose
Handle registrations and contact updates for ARG (the alumni association). Submissions are stored in Google Sheets and notification emails are sent to the designated recipients.

## Daily Workflow
1. Share the public signup form at `/alumni/signup/` with prospective alumni.
2. Monitor your inbox for two types of messages:
   - **New member** confirmations (`ARG - Ny medlem …`), sent to the distribution list configured in settings.
   - **Update requests** containing a token link that members use to edit their details.
3. Signups are also logged in the Google Sheet defined by `ALUMNI_SETTINGS` (usually the `members` worksheet). Use the sheet to process membership fees and status.

## Managing Update Tokens
1. Alumni who want to update their data visit `/alumni/update/` and enter their email plus captcha.
2. The system emails them a time-limited link containing a token.
3. After the alumni submits the update form, the token is invalidated automatically. No manual action is required unless the email bounces.

## Troubleshooting
- **Duplicate email** – if someone gets "Email already registered", ask them to use the update flow instead of the signup form.
- **Token expired** – tokens last 24 hours. Direct the alumni back to `/alumni/update/` to request a fresh email.
- **Captcha failing** – ensure Cloudflare Turnstile keys are valid in the environment; otherwise the form will keep reloading.

## Data Exports
- All data lives in Google Sheets. Filter by the `audit_log` worksheet to review historical actions (CREATE/UPDATE) if you need to audit changes.
