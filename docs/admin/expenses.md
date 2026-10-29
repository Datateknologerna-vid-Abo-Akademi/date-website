# Expenses Admin Guide

Members can ask the association to reimburse a purchase through **Kostnadsersättningar** on the website. The treasurer reviews the claim in the admin, approves or rejects it, downloads the generated PDF, signs the paper copy and pays the money. The app does not move money by itself.

## What the member does

1. Opens **Kostnadsersättningar** and chooses **Skicka in ny kostnadsersättning**.
2. Fills in the recipient, what the purchase was for, the amount in euros and how they want to be paid. A bank transfer needs their IBAN; the form checks it and stores it formatted.
3. Attaches the receipts. Up to ten files, at most 10 MB each and 30 MB in total; JPEG, PNG, GIF, WebP and PDF are accepted. The form rejects a file that is not a real image or PDF, so a mistyped extension is caught immediately.
4. Submits. The claim gets the status **Väntar** and the PDF is generated in the background.

The member sees only their own claims, receipts and status. They never see the generated PDF; that copy belongs to the treasurer.

## What the treasurer does

The claims are under **Expenses → Expense claims** in the admin sidebar. The list shows the recipient, amount, payment method, status, who submitted it, the submission time and whether the PDF is ready. Search by recipient, description or member; filter by status and payment method; use the date tree to narrow by submission date.

Opening a claim shows every field the member submitted and a read-only list of the receipts. **Öppna kvitto** opens one in a new tab. Receipts cannot be added or removed in the admin: the signed PDF was built from them. The PDF link sits in the form when the file exists; if it does not, the page says the PDF is not generated yet.

The two decision actions work on the checkboxes in the list. They only touch claims that are still **Väntar**; a claim that already has a decision is left alone, and the message under the table says how many were skipped, so a second click cannot overwrite the first decision:

- **Godkänn valda utlägg** marks the selected claims **Godkänd** and records you as the reviewer with today's date.
- **Neka valda utlägg** does the same with **Nekad**.

Both only write the decision; they send nothing to the member and do not pay anything. Tell the member yourself if the claim is rejected, and pay approved claims the way the member asked (cash or bank transfer to the stored IBAN).

**Generera PDF på nytt** queues a new PDF for the selected claims, for example after a rendering problem. The old file is replaced only after the new one is stored, and the page says so if a task could not be queued. The generated PDF contains:

- the association name, claim number and submission date,
- the recipient, description, amount, payment method and IBAN,
- one page per image receipt and the PDF receipts appended after it,
- a signature block for the approver and the treasurer.

Print it, sign it and keep it with the accounting material. **Kassörens signeringsdatum** is a free date field on the claim for recording when the signed copy was dated.

## Notes

- A claim can only be created from the website, not from the admin. There is no add button, because a claim belongs to the member who submitted it.
- Receipts are read-only in the admin. A wrong or missing receipt means asking the member to submit a new claim.
- Deleting a member also deletes their claims and the stored receipt and PDF files. Export a signed PDF first if the financial record has to survive.
- The PDF is Swedish and fixed in layout; the rest of the site can be viewed in English while the paper form stays the one the treasurer files.
