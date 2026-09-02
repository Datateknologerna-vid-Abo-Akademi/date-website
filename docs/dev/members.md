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
- Member-valued autocomplete fields on other apps (`Flag.solver`, `Event.author`, `Functionary.member`, `EventInvoice.participant`, `Post.author`, ...) work for editors who can add/change the referring object even when they lack `members.view_member`. `core.admin.ReferringObjectAutocompleteJsonView` (installed via `FixedLanguageAdminSite.autocomplete_view`) widens Django's default check, which otherwise requires view permission on the *related* model and returns an empty "no results" dropdown. `UserAdmin.get_queryset` still filters the returned rows, so `MEMBER_ADMIN_RESTRICTED_GROUP`/`MEMBER_ADMIN_RESTRICTED_MEMBERSHIP_TYPE` restrictions keep applying.

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
