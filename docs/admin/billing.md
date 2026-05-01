# Billing Admin Guide

## Purpose
Automate invoicing for paid events. When an attendee signs up, the Billing app can generate an invoice, assign reference numbers, and email payment instructions.

## Event Billing Configuration
1. Go to **Billing › Event billing configurations** (`/admin/billing/eventbillingconfiguration/`).
2. Click **Add event billing configuration**.
3. Fields:
   - **Event** – select the corresponding event (each event can only have one configuration).
   - **Due date** – invoice due date sent to participants.
   - **Integration type** – currently only "Invoice" is implemented.
   - **Price** – either a single numeric price or a comma-separated list if you use dynamic pricing (see below).
   - **Price selector** – optional. Set to the exact name of an event registration field; the system will pick the matching price from the comma-separated list above.
4. Save. From now on, every new signup for that event will trigger invoice generation.

## Generated Invoices
- View them under **Billing › Event invoices**. Each record links to the participant, lists invoice/reference numbers, dates, amount, and currency (EUR).
- Use the changelist filters to find invoices for a specific event.

## Export Reference Numbers
1. In the billing configuration list, click the **Exportera data** button.
2. A CSV download begins with columns: name, email, invoice number, reference number, invoice/due dates, amount, currency.
3. Share the file with your accounting system or bank as needed.

## Price Selector Example
- Suppose an event has a registration field named `Biljett typ` with options `Standard,Student`.
- Set **Price** to `35,20` and **Price selector** to `Biljett typ`.
- When someone picks "Standard", they get €35; "Student" receives €20.

## Tips
- Configure billing **before** opening registrations. Existing attendees will not receive invoices retroactively.
- Use the Events admin to ensure the corresponding registration field names exactly match the selector (case-sensitive).
- Free events can still use billing: set **Price** to `0`. The system will send a confirmation email instead of an invoice.
