# Expenses Development Notes

The `expenses` app lets a member claim reimbursement for a purchase they made on the association's behalf, attach the receipts, and get a PDF the treasurer can sign and file. It is installed for the `date` variant only.

## What it is not

There is no payment integration, no accounting export and no email notification. Approval records who decided and when; paying the money stays a manual bank transfer or cash handover. The signed PDF is the accounting record, so the app does not try to be one.

## Wiring

- `core/settings/date.py` lists `expenses` in its `get_installed_apps([...])` call. No other variant does.
- `core/urls/common.py` has the `expenses` route key, mounted at `expenses/`; `core/urls/date.py` passes that key to `build_urlpatterns(...)` unconditionally, next to `attendance`.
- There is no capability flag. Removing the app from a release is a code change, not an environment variable. If an off switch is ever needed, add `EXPENSES_ENABLED` beside `BOOKING_ENABLED` in `core/settings/common.py`, default it to `False`, turn it on in `core/settings/date.py`, and make `core/urls/date.py` conditional the way the booking key is.
- `core/tests/test_url_route_parity.py` pins the `expenses/` prefix and the `expenses:list` URL name for `date`, and lists `expenses:list` as forbidden for every other variant. Extend those lists when another variant adopts the app.

## Data model

`ExpenseClaim` is one submitted claim:

- `recipient_name`, `description`, `amount` (EUR, two decimals, `MinValueValidator(0.01)`), `payment_method` (`cash`/`bank`) and `bank_account` (IBAN).
- `submitted_by` (`members.Member`, `on_delete=CASCADE`) and `submitted_at`. The cascade matches `members.SubscriptionPayment`: the app holds operational claims, while the signed PDF is what survives outside the database.
- `status` (`pending`/`approved`/`rejected`), `reviewed_by` (`SET_NULL`, so deleting the reviewer keeps the decision) and `reviewed_at`.
- `treasurer_signature_date`, editable in the admin, for recording when the paper copy was signed.
- `pdf` and `pdf_generated_at`, written by the Celery task.

`ExpenseClaim.clean()` is the one place the IBAN is checked: for `bank` it rejects an empty value, validates the account with `schwifty`, and stores `IBAN.formatted`. The site form and the admin change form both run model validation, so the rule applies in both. A non-bank claim clears `bank_account`. Two database `CheckConstraint`s back the same rules: `amount > 0`, and a bank claim cannot have an empty account.

The model has `get_absolute_url()` (the member detail page), and `pdf_filename` is the download name, `kostnadsersattning-<pk>.pdf`.

`ExpenseReceipt` is one uploaded file. Its storage path is `expenses/receipts/<year>/<uuid>.<ext>`: the original name is never used, so a receipt cannot be guessed and a member's file name cannot leak into a URL. Only `jpg`, `jpeg`, `png`, `gif`, `webp` and `pdf` extensions are kept; anything else is dropped from the storage name. The model carries `FileExtensionValidator` and a size validator so an admin edit is checked too. `Meta.ordering` keeps receipts in upload order for the PDF.

Claims are ordered newest first. Deleting a claim cascades to its receipts; `django_cleanup` removes the stored files with the rows.

## Forms and upload limits

`expenses/forms.py` has one form, `ExpenseClaimForm`, and a multiple-file field:

- Up to `MAX_RECEIPTS` (10) files, at most `MAX_RECEIPT_BYTES` (10 MB) each and `MAX_TOTAL_BYTES` (30 MB) in total.
- Images are capped at `MAX_IMAGE_PIXELS` (40 megapixels, checked from the header before any decode) and PDFs at `MAX_PDF_PAGES` (50). Both keep a compressed file from expanding into a large allocation in the worker.
- The extension decides how a file is parsed and the parse decides whether it is accepted: images go through Pillow's `verify()`, PDFs through `pypdf` with the page tree forced so a truncated or password-protected file fails here rather than in the worker. The browser's `Content-Type` is not trusted; some devices send `application/octet-stream` for a good photo.
- Files are validated from the stream, not from a `read()` into memory. A 10 MB upload costs one stream, not a second copy.
- `MultipleFileInput` sets `allow_multiple_selected`, which Django honours in `FileInput.value_from_datadict`.

The view prefills `recipient_name` with the member's name on a GET. On a POST, claim and receipts are written in one `transaction.atomic`, and the PDF task is enqueued on commit with a local helper, so the worker cannot read a claim whose receipts are not committed yet. The helper logs and swallows a broker error: the claim is already committed, and a queue outage must not turn a saved submission into an error page. The admin action can rebuild the PDF later.

## Views and access

All views use `@login_required`. `LOGIN_URL` is `members:login`.

- `expense_list` shows a member their own claims and staff every claim. The template shows the submitted-by column only to staff (`is_staff` in context).
- `expense_create` is the submission form and redirects to the new claim's detail page with a success message.
- `expense_detail` returns the claim only to its owner or to staff. Anyone else gets a 404, not a 403: the URL should not confirm that another member's claim exists.
- `receipt_file` serves one receipt to the claim's owner or staff, and sets `Cache-Control: private, no-store`. It always streams through Django (`FileResponse`) and never redirects to the storage URL. On S3 that costs one download through the web process, but the private bucket's URL is either unsigned or a one-hour presigned link depending on `AWS_S3_PRIVATE_CUSTOM_DOMAIN`, and neither is a guarantee a replayed link has to respect.
- `download_pdf` is staff-only and returns the generated PDF as an attachment named `kostnadsersattning-<pk>.pdf`. Members do not see the generated PDF; it is the treasurer's working copy.

A missing file in storage produces a 404 on both file views and a log line under the `date` logger.

## The PDF task

`expenses/tasks.py` defines `generate_expense_pdf(expense_id)`, a Celery task discovered through `app.autodiscover_tasks()`. It runs once when a claim is submitted and again from the admin action "Generera PDF på nytt".

The document is built with ReportLab on A4:

1. Association name from `CONTENT_VARIABLES["ASSOCIATION_NAME_FULL"]`, then the claim number and a rule.
2. Submission date, recipient, the description wrapped to the page width, amount, payment method and, for a bank claim, the IBAN.
3. A signature block for the approver and the treasurer.
4. One page per image receipt, scaled to fit with the aspect ratio preserved.
5. PDF receipts appended afterwards with `pypdf`, one at a time, so the whole set is never held in memory together.

A receipt that cannot be read or embedded gets a readable stand-in page instead of a blank one, and the failure is logged with the receipt and claim identifiers. A new PDF is stored and its database reference committed before the previous object is deleted, so a failed regeneration leaves the working copy in place. Long descriptions are wrapped with reportlab's own string widths and continue on a new page instead of running off the bottom. The built-in Helvetica face is Latin-1, so characters it cannot draw are replaced with `?` rather than raising.

The PDF text is deliberately fixed Swedish, not translated: it is the paper form the treasurer signs, and it is generated by a worker with no request language. The web UI around it is fully translated.

## Admin

`ExpenseClaimAdmin` is registered through `core.admin_base.ModelAdmin` and `TabularInline`, so it picks up the Unfold base classes and the project's widget overrides when `USE_UNFOLD` is on. Receipts are a read-only inline whose cell links to the authenticated receipt view; the inline refuses both adds and deletes, because the signed PDF was built from exactly those files. The admin has no add permission: a claim is submitted from the site, and the add form could not set the read-only `submitted_by`.

The two decision actions update only the claims still `pending`, with `queryset.update(...)`, set `reviewed_by` to the acting staff member and `reviewed_at` to `timezone.localdate()`, and report how many rows were skipped because a decision already existed. They do not regenerate the PDF; the signed paper copy is printed from the existing one. "Generera PDF på nytt" queues one task per selected claim and reports a per-claim enqueue failure instead of returning a 500 after some tasks were queued.

The editor-facing workflow is in `docs/admin/expenses.md`.

## Templates and static files

- `templates/common/expenses/list.html`, `create.html` and `detail.html`.
- `templates/common/expenses/partials/status_badge.html` is shared by the list and the detail page so the status labels and badge colours cannot drift.
- `static/common/expenses/css/expenses.css` carries the receipt thumbnail, the pre-wrapped description and the table text colour. The table selector is a class (`.expenses-table`), not an id, and the sheet follows the shared-CSS rules in `docs/dev/css.md`.

Receipts are rendered inline only for images; PDF receipts are a link. Both go through `expenses:receipt`, never a storage URL.

## Translations

Swedish is the source language, and every user-facing string has `sv`, `en` and `fi` entries in `locale/*/LC_MESSAGES/django.po`. The admin sidebar has an **Expenses** group for a reader holding `expenses.view_expenseclaim`; like the other app groups in `core/admin_ui.py`, it drops out when the permission or URL name does not resolve, so it is absent on an association that does not install the app.

After changing strings, run the commands in `docs/dev/translations.md` and `uv run python scripts/validate_translations.py`. The entries for this app were added to the catalogs by hand because regenerating them rewrapped the whole file; a future `makemessages` run is still the rule for new strings.

## Tests

```bash
uv run python manage.py test expenses
```

Through the Docker helper, after `source env.sh`:

```bash
date-test expenses
```

Both run with `core.settings.test` (in-memory SQLite, compiled translations). `expenses/tests.py` covers the model rules and the two check constraints, the form's file limits and content checks, every view's access rule and status code, the create flow including the on-commit task enqueue, the PDF task against image and PDF receipts, and the admin actions. Routing is covered by `core/tests/test_url_route_parity.py`.

## Finding the page

The page is not placed in a code-managed menu. Like `/attendance/`, the link belongs to the editor-managed navigation: add a Static Page Nav or Static URL entry pointing at `/expenses/`, and it disappears again when an editor removes it.

## Known limits

- A member can submit any number of claims and there is no rate limit. The form caps files and bytes, not submissions.
- The claim list is paginated at `CLAIMS_PER_PAGE` (50).
- There is no notification email to the treasurer and no reminder; the admin is the place to watch.
- A claim's `submitted_by` cascades, so deleting a member deletes their claims and receipt files. Export the signed PDFs first if a deletion request has to keep the financial record.
- The PDF is generated once and not regenerated when a receipt is added through the admin. Receipts cannot be added or removed in the admin, so the only path to a new receipt is a new claim; the action exists for a manual regeneration after a storage or rendering problem.
- In a `DEBUG` deployment Django serves `MEDIA_ROOT` under `MEDIA_URL`, so a receipt's UUID path is reachable without the login check. That is local development only; production does not serve private media that way, and the file views stream through Django regardless.
