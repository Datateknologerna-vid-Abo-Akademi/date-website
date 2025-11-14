# Billing Development Notes

## Models
- `EventInvoice`: FK to `events.EventAttendees`, stores invoice/reference numbers, invoice/due dates, amount, and currency.
- `EventBillingConfiguration`: one-to-one with `events.Event`, specifying due date, integration type (`BillingIntegrations` enum), base price(s), and optional `price_selector` pointing at a registration field name.

## Flow (`billing/handlers.py`)
1. `events.views.EventDetailView.form_valid()` calls `billing.handlers.handle_event_billing()` when the `event_billing` experimental feature is enabled.
2. `handle_event_billing` fetches the billing configuration for the event (parent fallback) and resolves the integration provider.
3. For invoice integration:
   - Generates a random invoice number (`generate_invoice_number`) and a checksum-protected reference number.
   - Computes the amount via `get_selection_price()`—either a fixed float or matched to a registration answer by name.
   - Creates the `EventInvoice` row (with retry recursion on failure).
   - Sends an invoice email using `billing/util.send_event_invoice()`.
   - If the price resolves to `0`, it sends a free-event confirmation email instead.

## Utility Functions
- `generate_reference_number()` implements the 7-3-1 checksum common in Finnish reference numbers.
- `get_selection_price()` reads `EventRegistrationForm.choice_list` to map answers to prices; mismatches raise `ValueError`.
- Email templates live in `templates/billing/`. Context merges `BILLING_CONTEXT` and `CONTENT_VARIABLES` from settings.

## Admin
- `EventBillingConfigurationAdmin` adds a custom URL (`/ref_numbers/`) to export invoice data as CSV. `ref_export` renders a button on each row.
- `EventInvoice` uses default admin registration.

## Extending
- Support additional integrations (e.g., Stripe) by adding new members to `BillingIntegrations` and branching in `handle_event_billing`.
- Persist audit logs (sent emails, retries) to help finance teams troubleshoot.
- Add constraints to prevent deleting an `EventAttendees` row that already has invoices unless cascading deletes are expected.
