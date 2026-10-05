# Members Development Notes

## Custom User Model
- `Member` extends `AbstractBaseUser` + `PermissionsMixin` with `username` as the `USERNAME_FIELD`.
- Fields include contact info, `membership_type` FK, `year_of_admission`, and helper props (`is_staff`, `full_name`, `active_payment`).
- `MemberManager` (see `members/managers.py`) handles user creation.
- `membership_type.permission_profile` ties into other apps for access control.
- `NON_VOTING_MEMBER` is an ordinary-member profile minus voting: members with it are treated like ordinary members for member content, archive, events, and membership-restricted publications (a publication allowlist containing any ordinary-profile type admits them), but `polls` rejects them for `Endast ordinarie medlemmar` and `Endast röstberättigade medlemmar` questions. SF maps its `Extra medlem` type to this profile.
- `archive_access_eligible` records completion of an association-specific duty or pass. It is only required for archive access when `ARCHIVE_ACCESS_REQUIRES_ELIGIBILITY` is enabled, and the admin forms only expose the checkbox when that setting is on (currently SF).

## Membership & Payments
- `Subscription`: defines pricing and renewal cadence (`renewal_scale` + `renewal_period`).
- `SubscriptionPayment`: links members to subscriptions, stores payment/expiry dates, and exposes `is_active` + `expires` properties. `SubscriptionPaymentForm.save()` auto-calculates `date_expires` using `dateutil.relativedelta`.

## Functionaries
- Functionary roles and assignments live in the `functionaries` app. `members.urls` keeps the old `/members/functionary/` and `/members/functionaries/` routes for compatibility.

## Forms
- `MemberCreationForm` validates usernames via `USERNAME_VALIDATOR` (letters, underscores, hyphens). `AdminMemberUpdateForm` uses `ReadOnlyPasswordHashField` and disables password editing unless explicitly changed.
- `SignUpForm` collects data for `/members/signup/`, including captcha validation and manual activation flow.
- Associations can limit public signup fields with `MEMBERS_SIGNUP_FIELDS` and membership names with `MEMBERSHIP_TYPE_NAMES`, and override the city field label with `MEMBERS_SIGNUP_CITY_LABEL`. SF collects username, email, first and last name, city (labeled `Hemort`), a membership type selector (`Ordinarie medlem` / `Evig SF:are` / `Extra medlem`), admission year, and password; `MEMBERS_SIGNUP_DEFAULT_MEMBERSHIP_TYPE` still applies as a fallback when an association hides the selector. SF does not expose contact address, postcode, phone, or country.
- `CustomPasswordResetForm` overrides `send_mail` to push messages through `send_email_task` (Celery-backed).

## Views
- `UserinfoView`: GET shows profile form; POST saves the `MemberEditForm` and redirects.
- `CertificateView`: renders a fun membership certificate with a daily icon.
- `signup`: handles public registrations, enforces captcha, sets user inactive, and emails the board for approval using `account_activation_token`.
- `activate`: clicks from the activation email mark the user active.
- Password views subclass Django’s built-ins to use the custom templates/forms.

## Emails & Tokens
- Emails are queued via Celery. Request-side enqueue points that depend on fresh database state should go through `core.utils.enqueue_task_on_commit()` so jobs are only published after the surrounding transaction commits.
- Activation tokens use `members/tokens.py` (standard Django token generator) and base64-encoded user IDs.
- Plain-text email bodies use `.txt` template names, including activation and password-reset messages. Django template tags work independently of the filename extension; `.txt` keeps these message bodies out of djlint, whose HTML reformatter can otherwise change meaningful indentation and blank lines. Use `.html` only for actual HTML email alternatives.

## Admin Customizations
- Admin-created members require a password of at least eight characters. Changing a payment to a non-expiring subscription clears any expiry date left by the previous subscription.
- `UserAdmin` inherits from `auth_admin.UserAdmin` but swaps in custom forms and ordering.
- Actions `activate_user`/`deactivate_user` bulk-toggle `is_active`.
- SF exposes the `Gulispass utfört` archive eligibility checkbox in member add/change forms; other associations do not see the field because it is gated on `ARCHIVE_ACCESS_REQUIRES_ELIGIBILITY`. Its post-migration provisioning creates or updates `Ordinarie medlem`, `Evig SF:are`, and `Extra medlem`: the first two with the ordinary permission profile and `Extra medlem` with the non-voting profile (`NON_VOTING_MEMBER`), which behaves like ordinary everywhere except polls restricted to ordinary or voting-entitled members, without deleting historical membership types. It also creates a yearly 15 euro subscription for `Ordinarie medlem`, a non-expiring 40 euro subscription for `Evig SF:are`, and a yearly 15 euro subscription for `Extra medlem`, and synchronizes `styrelse`, `skattis`, `sekre`, `Inauta`, `webbansvarig`, and `admin` permissions repeatably.
- SF `styrelse` receives all local app model permissions except the complete `members` app. `skattis`, `sekre`, `webbansvarig`, and `admin` receive all local app model permissions without superuser status. `Inauta` receives full permissions outside `members`, plus only view/change/delete permission for members whose type is `Evig SF:are`; it cannot access membership products or payments, create members, change membership types, or change member groups. Superusers remain unrestricted.
- `SubscriptionPaymentAdmin` uses a custom `ModelChoiceField` to show human-readable member names.
- Deleting a member cascades into that member's `LogEntry` rows, because the admin audit log points at the user model with a CASCADE foreign key, and the log admin is deliberately read-only. `UserAdmin.get_deleted_objects` drops the log entry from Django's related-object permission check, since otherwise the read-only log admin would refuse every member deletion, superusers included. The other cascade targets (payments, votes, authored content) still have to pass their own delete permissions, so a non-superuser needs the matching delete permissions for each registered related model that would be removed.
- Member-valued autocomplete fields on other apps (`Flag.solver`, `Event.author`, `Functionary.member`, `EventInvoice.participant`, `Post.author`, ...) work for editors who can add/change the referring object even when they lack `members.view_member`. `core.admin.ReferringObjectAutocompleteJsonView` (installed via `FixedLanguageAdminSite.autocomplete_view`) widens Django's default check, which otherwise requires view permission on the *related* model and returns an empty "no results" dropdown. `UserAdmin.get_queryset` still filters the returned rows, so `MEMBER_ADMIN_RESTRICTED_GROUP`/`MEMBER_ADMIN_RESTRICTED_MEMBERSHIP_TYPE` restrictions keep applying.

## Two-Factor Authentication & Passkeys
- 2FA is built on `django-otp` + `django-two-factor-auth` (TOTP authenticator apps, static backup tokens) plus `django-otp-webauthn` 0.10.3 for passkeys. Custom views live in `members/two_factor.py` (mounted at `/members/two-factor/`); passkey API views live in `members/webauthn.py` and are mounted at `/members/webauthn/` (namespace `otp_webauthn`) for every association.
- `django-two-factor-auth`'s own `two_factor.plugins.webauthn` was not used: its Django 6 support is unreleased, it is second-factor only, does not create discoverable credentials, and pins py_webauthn below 3 (which conflicts with `django-otp-webauthn`).
- `member_has_2fa(user)` is true when the member has any confirmed non-static device (TOTP or passkey); backup tokens alone don't count. It drives `should_redirect_to_two_factor_setup`, the profile 2FA links (`two_factor_context`), `FixedLanguageAdminSite.has_permission` (`core/admin.py`), the GitHub `GITHUB_MFA_POLICY` check, the passkey registration enrolment check, and the admin `has_two_factor` column (a TOTP-or-passkey `Exists` annotation).

### Passkey settings
- `WEBAUTHN_RP_ID` → `OTP_WEBAUTHN_RP_ID`: the relying-party domain (e.g. `example.com`). It is pinned rather than derived from the request host. **Treat it as permanent**: changing it (or switching between apex and `www.`) invalidates every registered passkey.
- `WEBAUTHN_ALLOWED_ORIGINS` → `OTP_WEBAUTHN_ALLOWED_ORIGINS`: JSON list of exact origins (`https://example.com`, `https://www.example.com`). Kept separate from `ALLOWED_ORIGINS`/`CSRF_TRUSTED_ORIGINS`, which may contain plain-http or wildcard entries.
- With `DEBUG` on and both unset, they default to `localhost` / `["http://localhost:8000"]` (browsers treat localhost as a secure context; RP ID `localhost` works on any port, but each port must be listed as an origin).
- `PASSKEYS_ENABLED` is derived: true only when both are set. When false, the passkey UI is hidden, the passkey endpoints and `/members/two-factor/passkeys/` return 404, the library's own checks `otp_webauthn.E010`/`E030` are silenced, and `members.W001` warns instead, so unconfigured sites still deploy.
- `members/checks.py` errors when enabled and an origin contains a wildcard (`members.E001`), is not https unless its host is `localhost` (`members.E002`), or is not the RP ID or a subdomain of it (`members.E003`).
- `PASSKEY_REGISTRATION_MAX_AUTH_AGE` (default 600 s): how recent the session's last sign-in/verification must be to register a passkey.

### Passkey flows
- **Passwordless sign-in**: the login page's auth step shows "Sign in with a passkey". User verification is required for this anonymous ceremony. Success logs the member in through `django_otp_webauthn.backends.WebAuthnBackend` and marks the session OTP-verified, so it satisfies admin and `otp_required` views. The complete view reuses the login page's validated `next`/referer-inferred redirect.
- **Existing session**: if a member is already logged in (in practice only after GitHub login with `GITHUB_MFA_POLICY` `off`/`staff`), the library uses UV "discouraged", so a security-key touch verifies the session; GitHub was the first factor. The session key is rotated when an existing session becomes verified.
- **Passkey-only member + password or GitHub login**: two_factor's `default_device()` only knows TOTP-style devices, so `MemberLoginView.has_backup_step` uses `member_has_2fa` and `_begin_two_factor_login` jumps to the backup step. That step offers the passkey button or a backup token; there is no way to finish unverified.
- **Registration** (`/members/two-factor/passkeys/`): requires a sign-in/verification within `PASSKEY_REGISTRATION_MAX_AUTH_AGE` (timestamp set on `user_logged_in` and on passkey verification), and — if the member already has a second factor — a verified session. Registering marks the session verified and rotates the session key.
- **TOTP setup** (`two_factor:setup`): `MemberSetupView` sends an unverified session of a member who already has a second factor back to login. two_factor itself only skips setup for TOTP default devices, so without this an unverified session of a passkey-only member could enrol its own TOTP device and upgrade itself to verified.
- **Linking GitHub** (`members:github_connect`) also requires a recent sign-in, because a linked GitHub account can log in and refresh the recent-auth timestamp that gates passkey registration.
- **Rename/delete**: POST-only, `otp_required`, scoped to the member's own credentials (404 otherwise). Deleting the last real factor also deletes the backup-token device so the member isn't left half-enrolled.
- Adding or removing a passkey emails the member (`members/passkey_added_email.txt` / `passkey_removed_email.txt`) via `enqueue_task_on_commit` + `send_email_task`. Registration, sign-in, failures, deletion and the admin disable action are logged on the `date` logger.
- **Disable 2FA** (`two_factor:disable`) removes all devices, including passkeys.
- **Password reset intentionally keeps 2FA devices** so an email-account takeover does not also reset the second factor. Lockout recovery is the admin "Inaktivera 2FA" action.
- The member admin's **Passkeys** inline is read-only and cannot delete; removal goes through the guarded, logged "Inaktivera 2FA" action.
- If passkeys are later disabled (unset `WEBAUTHN_*`), existing passkeys still count as a second factor, so passkey-only members without backup tokens need the admin action to sign in again.

### Known gaps
- The passkey endpoints have no application-level rate limiting; throttle `members/webauthn/` at the ingress.
- py_webauthn rejects non-increasing sign counts, but the credential is not flagged or disabled and the member is not alerted (synced passkeys report 0 anyway).

## Extending
- Consider adding auditing (who edited a member) since current forms don’t track admin users.
- Django 6 is now in use. If you revisit background jobs, evaluate Django's built-in Tasks framework separately from Celery migration work rather than mixing both changes into a feature branch.
- Tests are sparse; add coverage for signup + activation flows.

## Verification (2026-08-25)
- Ran `uv run python manage.py test members.tests_sf_access members.tests gallery.tests.SFGalleryAccessTests exambank.tests.SFExamBankAccessTests`: 71 tests passed in 0.974 seconds, with no system-check issues. Django emitted the existing warning that `core/static/` does not exist.
- Ran `uv run python manage.py test`: 483 tests passed and 1 was skipped in 10.109 seconds, with no system-check issues.
- Ran full `ruff check`, `ruff format --check`, `djlint --check templates/`, and `mypy .` checks plus `git diff --check`; all passed.
- Ran `uv run python manage.py makemigrations --check --dry-run`: no model changes were missing. The command warned that the configured development host `db` could not resolve while checking migration history, but dry-run migration detection completed.
- [ ] Run an SF deployment smoke test after migration with representative staff accounts and production membership data.

## Verification (passkeys branch)
- [ ] Record test, lint, and manual passkey smoke-test results for the `feat/passkeys` branch before merge.
