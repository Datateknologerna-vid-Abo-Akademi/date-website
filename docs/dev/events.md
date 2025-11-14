# Events Development Notes

## Data Model Overview
- `Event` (`events/models.py`) drives everything: content, schedule, signup windows, capacity, avec support, optional captcha/passcode, parent-child relationships, and background images (`ImageField` or `PublicFileField` depending on storage).
- `EventRegistrationForm` defines dynamic signup fields. `choice_number` controls ordering (auto-incremented by tens). `choice_list` stores comma-separated options for select/checkbox questions.
- `EventAttendees` persists registrations, including arbitrary `preferences` stored as `JSONField`. `attendee_nr` increments by 10 to keep admin-ordering drag handles stable. `original_event` enables cloned/child events, while `avec_for` links partner signups.

## Core Logic
- `Event.make_registration_form()` dynamically builds a `forms.BaseForm` subclass per event based on `EventRegistrationForm`. That form is used by `EventDetailView` to render the signup.
- Capacity: `Event.event_is_full()` (defined elsewhere in the model) prevents registrations when the limit is hit. Child events delegate to their parent for attendee counts.
- Sign-up windows rely on helper methods (`registration_is_open_members`, `registration_is_open_others`, etc.) comparing now to the configured datetimes.
- Passcode flow: if `passcode` is set, `EventDetailView` stores the successful passphrase in `request.session['passcode_status']`. Until matched, the template `events/event_passcode.html` is rendered.
- Captcha integration uses `core.utils.validate_captcha` and expects Cloudflare Turnstile responses in `cf-turnstile-response`.
- Websocket notifications: `ws_send(slug, form, public_info)` broadcasts new registrations (except during tests). The slug is derived from the parent event if present.
- Billing hook: when `settings.EXPERIMENTAL_FEATURES` contains `event_billing`, `billing.handlers.handle_event_billing()` runs after a successful signup to generate invoices or send confirmations.

## Admin Customizations
- `EventAdmin` swaps between `EventCreationForm` and `EventEditForm`, injecting `request.user` so the `author`/`modified_time` fields update correctly.
- Inline classes `EventRegistrationFormInline` and `EventAttendeesFormInline` leverage `admin_ordering`. Attendee inline fields vary depending on `sign_up_avec` and whether the event has children.
- Custom admin action `delete_participants` prompts for confirmation before removing attendee rows.
- Extra admin URL `/list/` renders `events/list.html` for an event, showing public info answers.

## Forms
- Creation/Edit forms override `save()` to enforce slug uniqueness (`slugify_max`), normalize signup settings when `sign_up` is false, and stamp publish/modified times.
- `PasscodeForm` is a simple `forms.Form` used when `passcode` is required.

## Views & Routing
- `IndexView` lists upcoming and past events separately.
- `EventDetailView` handles GET (render + optional redirect link) and POST (passcode validation + signup). On success it redirects back to the detail page with anchor fragments for certain event types (Årsfest, ÖN100, etc.). Template overrides can be triggered by event title or slug for special layouts.

## Websocket Layer
- `events/consumers.py` and `websocket_utils.py` push attendee updates via channels. Ensure the slug used in `ws_send` matches the subscription on the front end.

## Extending / Gotchas
- Any changes to registration fields must keep `Event.make_registration_form()` in sync; inconsistent `choice_list` formatting breaks multiple-choice inputs.
- When altering attendee serialization, update both the model and the JS that renders real-time updates.
- Parent/child events rely on consistent `parent` assignments; deleting a parent cascades to children and could orphan registrations.
