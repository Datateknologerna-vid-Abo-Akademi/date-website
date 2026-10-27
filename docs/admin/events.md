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
   - **Date & time fields** – start/end timestamps plus signup open/close windows. Use the datetime picker in `YYYY-MM-DD HH:MM` form; keep members/others windows realistic.
   - **Anmälning** – uncheck if no signup is needed (all signup-related fields will be ignored). On an Årsfest page this also removes the Anmälan tab and the sign-up panel, so the page works as a plain information page.
   - **Maximal antal deltagare** – `0` means unlimited.
   - **Avec** – allow partners; extra fields will display when the signup form contains `avec_…` inputs.
   - **Kräv inloggning för innehåll** – gate the event page behind member login.
   - **Passcode** – optional simple password visitors must enter before the signup form appears.
   - **Background image** – upload a background image. The form shows the field that matches this deployment's storage (local or public S3). Large pictures are shrunk on save to fit within 1920×1080 (Full HD) and keep their shape, so nothing is cut off. Uploading a bigger original gains nothing. iPhone photos (HEIC) are accepted and stored as JPEG, and transparent logos keep their transparency.
   - **Bakgrundsbildens layout** – how the background image is shown on a normal event page:
     - **Fyll hela bakgrunden** (default) fills the whole screen behind the text. The picture keeps its proportions, so when its shape differs from the screen's, the edges are cropped. Keep important details near the middle.
     - **Visa bilden på sidorna** shows the whole picture, scaled down, to the left and right of the text on wide screens, and as a banner above the title on phones and narrow windows. The side pictures are always a little smaller than the event text box, so they stay small on events with very little text. Use it for posters where nothing may be cut off.
     - In both layouts, the page background takes on a darkened version of the picture's main colour instead of plain black. This happens automatically, with nothing to set.
     - The setting has no effect on the special Baal, Wappmiddag, KK100 and Årsfest templates, which have their own backgrounds.
   - **Redirect Link** – skip the internal page entirely and send visitors to another URL like another student association's event page.
3. Publishing:
   - Set **Publiceras** to the date and time when the event should become visible.
   - Leave **Publiceras** empty to keep the event hidden. A future timestamp keeps it hidden until that time; a past timestamp publishes it immediately.
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
   - **Alternativ** - comma-separated choices for multiple-choice fields. Empty or duplicate options are rejected, and surrounding spaces are removed when saving. This field is only editable when **Typ** is `Multiple choice`; it enables/disables automatically as you change **Typ**, including on rows you just added with "Add another". If it stays greyed out after picking `Multiple choice`, that is a bug, not expected behavior.
   - **Göm för avec** – hide this field from partner signups.
4. Save the event to persist form fields.

## Manage Attendees
1. Use the **Deltagare** inline table to review or edit registrations. Columns include order number, name, email, anonymous flag, and timestamps. The **Svar** column shows one input per registration question, so answers are edited as normal values (text, choice or Ja/Nej) instead of JSON.
2. If a registration question was deleted or renamed after people signed up, its old answer still appears in the row and is marked as no longer matching a field, so it is not lost.
3. Each inline row has a change link to the participant's own admin page, which shows the same answer fields without the rest of the event.
4. If **Avec** is active or the event has child instances, extra columns ("Avec till", "Ursprungligt evenemang") appear automatically.
5. To export a pretty list, click **Deltagarlista** in the main event row; this opens a printable view of the answers collected for that event.
6. Bulk deletion: select events in the changelist → choose **Delete all attendees for selected events**. You will get a confirmation screen before anything is removed.
7. Question names must be unique within an event. Names used by standard signup fields, such as `email`, `user`, and avec fields, are rejected to prevent invalid registrations.
8. On an Årsfest page the **Anmälda** tab follows the list itself: it appears while the event is recent enough to show the list and the event either takes sign-ups or already holds registrations. Registrations you enter by hand therefore keep the tab, even on an event whose sign-up is turned off.

## Handling Waiting Lists / Child Events
- The **Parent** dropdown lets you chain events together. Registrations for child events roll up to the parent so attendee numbers stay consistent.

## When Billing Is Enabled
- If the Billing app is configured for an event, invoices are created automatically when participants sign up. Coordinate due dates and price selectors with the billing team.

## Tips for Successful Signups
- Always set `Anmälan öppnas` and deadline times; leaving the defaults (current timestamp) might close the form immediately.
- Use the **Captcha** checkbox for high-demand events to reduce spam.
- Before promoting the signup link, view the event page in an incognito window to confirm visibility, passcodes, and registration form behavior.
