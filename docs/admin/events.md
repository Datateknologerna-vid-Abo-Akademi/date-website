# Events Admin Guide

## Purpose
Create public event pages, manage registration windows, collect attendee data, and export lists straight from Django admin.

## Access
1. Sign in to `/admin`.
2. Open **Events › Events** (`/admin/events/event/`). The changelist shows upcoming and past events with attendee counts.

## Create a New Event
1. Click **Add event**.
2. Fill in the form (key sections):
   - **Titel & Innehåll** – what visitors see on the event page (CKEditor field supports images, embeds, etc.).
   - **Date & time fields** – start/end timestamps plus signup open/close windows. Use the date+time split inputs; keep members/others windows realistic.
   - **Anmälning** – uncheck if no signup is needed (all signup-related fields will be ignored).
   - **Maximal antal deltagare** – `0` means unlimited.
   - **Avec** – allow partners; extra fields will display when the signup form contains `avec_…` inputs.
   - **Kräv inloggning för innehåll** – gate the event page behind member login.
   - **Passcode** – optional simple password visitors must enter before the signup form appears.
   - **Background image** – upload locally (`Bakgrundsbild`) or to S3 (`s3_image`) depending on deployment settings.
   - **Redirect Link** – skip the internal page entirely and send visitors to another URL like another student association's event page.
3. Publishing:
   - Leave **Publicera** checked so the event stays visible; uncheck it to hide the page until you’re ready to republish.
   - `Slug` can stay blank; it auto-fills from the title and becomes the URL path segment (`/events/<slug>/`), so keep it short, readable, and unique.
4. Save to create the event and unlock the inline sections described below.

## Customize the Signup Form
Each event can have dynamic questions managed inline:
1. Scroll to the **Anmälningsfält** table (Event registration form inline).
2. Click **Add another Event registration form** for each question.
3. Fields:
   - **#** – ordering token. Values jump by 10 automatically so you can drag to reorder.
   - **Namn** – label shown to participants.
   - **Typ** – `Text`, `Multiple choice`, or `Kryssryta`.
   - **Krävd** – mark required answers.
   - **Öppen info** – include responses in the public attendee list.
   - **Alternativ** – comma-separated choices for select/check fields.
   - **Göm för avec** – hide this field from partner signups.
4. Save the event to persist form fields.

## Manage Attendees
1. Use the **Deltagare** inline table to review or edit registrations. Columns include order number, name, email, anonymous flag, answers (JSON), and timestamps.
2. If **Avec** is active or the event has child instances, extra columns ("Avec till", "Ursprungligt evenemang") appear automatically.
3. To export a pretty list, click **Deltagarlista** in the main event row; this opens a printable view with the public answers.
4. Bulk deletion: select events in the changelist → choose **Delete all attendees for selected events**. You will get a confirmation screen before anything is removed.

## Handling Waiting Lists / Child Events
- The **Parent** dropdown lets you chain events together. Registrations for child events roll up to the parent so attendee numbers stay consistent.

## When Billing Is Enabled
- If the Billing app is configured for an event, invoices are created automatically when participants sign up. Coordinate due dates and price selectors with the billing team.

## Tips for Successful Signups
- Always set `Anmälan öppnas` and deadline times; leaving the defaults (current timestamp) might close the form immediately.
- Use the **Captcha** checkbox for high-demand events to reduce spam.
- Before promoting the signup link, view the event page in an incognito window to confirm visibility, passcodes, and registration form behavior.
