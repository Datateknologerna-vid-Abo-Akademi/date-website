# Members Development Notes

## Custom User Model
- `Member` extends `AbstractBaseUser` + `PermissionsMixin` with `username` as the `USERNAME_FIELD`.
- Fields include contact info, `membership_type` FK, `year_of_admission`, and helper props (`is_staff`, `full_name`, `active_payment`).
- `MemberManager` (see `members/managers.py`) handles user creation.
- `membership_type.permission_profile` ties into other apps for access control.

## Membership & Payments
- `Subscription`: defines pricing and renewal cadence (`renewal_scale` + `renewal_period`).
- `SubscriptionPayment`: links members to subscriptions, stores payment/expiry dates, and exposes `is_active` + `expires` properties. `SubscriptionPaymentForm.save()` auto-calculates `date_expires` using `dateutil.relativedelta`.

## Functionaries
- `FunctionaryRole` + `Functionary` capture yearly positions. Views in `members/functionary.py` aggregate data by role and year for the public page.

## Forms
- `MemberCreationForm` validates usernames via `USERNAME_VALIDATOR` (letters, underscores, hyphens). `AdminMemberUpdateForm` uses `ReadOnlyPasswordHashField` and disables password editing unless explicitly changed.
- `SignUpForm` collects data for `/members/signup/`, including captcha validation and manual activation flow.
- `FunctionaryForm` enforces uniqueness per (member, role, year) and sets `member` during save.
- `CustomPasswordResetForm` overrides `send_mail` to push messages through `send_email_task` (Celery).

## Views
- `UserinfoView`: GET shows profile form; POST saves the `MemberEditForm` and redirects.
- `CertificateView`: renders a fun membership certificate with a daily icon.
- `signup`: handles public registrations, enforces captcha, sets user inactive, and emails the board for approval using `account_activation_token`.
- `activate`: clicks from the activation email mark the user active.
- `FunctionaryView`: login-protected view for members to list/add/remove their own functionary entries.
- `FunctionariesView`: public filterable list using helpers in `functionary.py` to collect data.
- Password views subclass Django’s built-ins to use the custom templates/forms.

## Emails & Tokens
- Emails are queued via Celery (`send_email_task.delay`). Activation tokens use `members/tokens.py` (standard Django token generator) and base64-encoded user IDs.

## Admin Customizations
- `UserAdmin` inherits from `auth_admin.UserAdmin` but swaps in custom forms and ordering.
- Actions `activate_user`/`deactivate_user` bulk-toggle `is_active`.
- `SubscriptionPaymentAdmin` uses a custom `ModelChoiceField` to show human-readable member names.

## Extending
- Consider adding auditing (who edited a member) since current forms don’t track admin users.
- When migrating to Django 5+, review password reset email templates for compatibility.
- Tests are sparse; add coverage for signup + activation flows and functionary filtering.
