# Events Development Notes

## Data Model Overview

- `Event` (`events/models.py`) drives everything: content, schedule, signup
  windows, capacity, avec support, optional captcha/passcode, parent-child
  relationships, and background images (`ImageField` or `PublicFileField`
  depending on storage).
- `EventRegistrationForm` defines dynamic signup fields. `choice_number`
  controls ordering (auto-incremented by tens). `choice_list` stores
  comma-separated options for select/checkbox questions.
- `EventAttendees` persists registrations, including arbitrary `preferences`
  stored as `JSONField`. `attendee_nr` increments by 10 to keep admin-ordering
  drag handles stable. `Event.attendee_nr_counter` atomically reserves those
  numbers per storage event. `original_event` enables cloned/child events,
  while `avec_for` links partner signups.

## Core Logic

- `Event.make_registration_form()` dynamically builds a `forms.BaseForm`
  subclass per event based on `EventRegistrationForm`. That form is used by
  `EventDetailView` to render the signup.
- Publication is controlled by `published_time`: `NULL` means hidden, a future
  timestamp means scheduled, and a past timestamp means public. Use
  `Event.objects.published()` for public-facing event lists, feeds, and detail
  lookups.
- Capacity: `Event.event_is_full()` (defined elsewhere in the model) reports
  when the limit is hit. Child events delegate to their parent for attendee
  counts. Only **child** events hard-block signups once full
  (`events/registration.py::_ensure_capacity`); a full **parent/standalone**
  event keeps its signup form open and lets registrations overflow past
  `sign_up_max_participants`, showing a "you'll be added to the reserve list"
  message instead. There is no dedicated reserve-list tracking (no separate
  status/flag on overflow attendees, no promotion when someone cancels). It is
  just uncapped overflow signup, restored 2026-08 to match pre-refactor (PR
  #939) behavior after that PR's capacity change turned out to be an unwanted
  regression rather than a bug fix.
- Sign-up windows rely on helper methods (`registration_is_open_members`,
  `registration_is_open_others`, etc.) comparing now to the configured
  datetimes.
- Passcode flow: if `passcode` is set, `EventDetailView` stores the successful
  passphrase in `request.session['passcode_status']`. Until matched, the
  template `events/event_passcode.html` is rendered.
- Captcha integration uses `core.utils.validate_captcha` and expects Cloudflare
  Turnstile responses in `cf-turnstile-response`.
- Websocket notifications: `ws_send(slug, form, public_info)` broadcasts new
  registrations (except during tests). The slug is derived from the parent event
  if present. The client (`static/common/core/js/live-attendee-list.js`)
  auto-reconnects with capped exponential backoff (1s doubling to 30s, reset
  only after a connection has stayed open) after a close or error, so worker
  recycling, deploys and network blips do not leave the live list stale.
  Broadcasts received while disconnected are not replayed and the row counter
  is local, so the list can show gaps after a longer outage until the page is
  reloaded.
- Billing hook: when `settings.EXPERIMENTAL_FEATURES` contains `event_billing`,
  `billing.handlers.handle_event_billing()` runs after a successful signup to
  generate invoices or send confirmations.
- Concurrency: `register_event_signup` runs in a transaction. It refreshes the
  event row from the database (the caller's object may be stale) and only takes
  the capacity row lock (`select_for_update`) for a child event with
  `sign_up_max_participants > 0`. Unlimited parent/standalone events skip that
  lock. The storage event reserves one attendee number, or two for an avec
  signup, using one atomic `UPDATE ... RETURNING` against
  `Event.attendee_nr_counter`. Concurrent signups briefly serialize on that
  counter update without racing, rescanning attendees, or retrying the complete
  signup transaction. The update takes the greater of the persisted counter
  and the current attendee maximum, so existing rows, explicit admin/import
  numbers, and old pods during a rolling deployment cannot leave it behind.
  The selected base is rounded down to a step-10 boundary before advancing,
  which keeps legacy/manual non-step-10 values out of the admin reorder band.
  `attendee_nr` is a positive 64-bit integer rather than a smallint, removing
  the old ~3276-signup ceiling caused by step-10 allocation. The
  `unique_attendee_nr_per_event` constraint remains the final integrity guard.
  Duplicate emails are still caught by the unique constraint on `(event, email)` and surfaced as a friendly error. Residual race: an event changed
  from unlimited to capacity-limited between the fresh read and insert is
  accepted as a consistency boundary; avoid changing capacity mode while
  registrations are active if strict atomicity is required. PostgreSQL
  concurrency coverage lives in `events.tests.AttendeeNrConcurrencyTests`.
  Migration `0026` widens the attendee column and can briefly lock writes to
  `events_eventattendees`; deploy it during a low-traffic window.
- Duplicate-email validation (`Event.validate_unique_email`) uses an indexed
  `exists()` query, not a full attendee scan (the scan became a bottleneck at
  scale on the shared postgres; measured on qa 2026-08-30).

## Admin Customizations

- `EventAdmin` swaps between `EventCreationForm` and `EventEditForm`, injecting
  `request.user` so the `author`/`modified_time` fields update correctly.
- Inline classes `EventRegistrationFormInline` and `EventAttendeesFormInline`
  leverage `admin_ordering`. Attendee inline fields vary depending on
  `sign_up_avec` and whether the event has children. The attendee inline uses
  `EventAttendeesInlineFormSet`, which pre-shifts all `attendee_nr` values of
  the event into a non-conflicting band before saving so a drag-and-drop reorder
  can never violate `unique_attendee_nr_per_event` mid-save (the sortable JS
  writes the final numbers in original row order, which would otherwise
  collide).
- Custom admin action `delete_participants` prompts for confirmation before
  removing attendee rows.
- Extra admin URL `/list/` renders `events/list.html` for an event, showing
  public info answers.
- `static/common/core/js/eventform.js` (loaded via `EventAdmin.Media`)
  enables/disables the `choice_list` ("Alternativ") input based on the row's
  `type` select, and toggles the whole registration-fields section based on
  `sign_up`. The `type` → `choice_list` handler is delegated
  (`$(document).on('change', 'select[id$="type"]', ...)`), not bound directly,
  and there's also a `formset:added` listener that re-applies the
  enabled/disabled state to a freshly inserted row. Both are required: rows
  added via the inline's "Add another" control are cloned from the (hidden,
  already-disabled-by-default) empty-form template, and under the Unfold admin
  theme that clone uses plain DOM `cloneNode` rather than jQuery's
  `clone(true)`, so it does not carry over directly-bound jQuery handlers. A
  non-delegated handler works for pre-existing rows and for classic-admin "Add
  another" (which clones with jQuery and does carry handlers over), but silently
  leaves new rows' `choice_list` stuck disabled under Unfold. If you touch this
  file, keep the delegation and the `formset:added` handler.
- New or modified registration question names must be non-empty, unique per
  event, and must not collide with built-in signup or avec fields.
  Multiple-choice options are trimmed and must contain at least one unique
  value. Unchanged legacy configurations remain editable so unrelated event
  updates are not blocked. These checks run server-side in both admin themes.
- Child registrations are stored on the parent event, but `get_registrations()`
  filters them by `original_event`. This prevents sibling attendee data from
  appearing in public or printable lists.
- The printable registration list requires both event and attendee view
  permissions. The participant deletion action separately requires attendee
  delete permission.
- Admin and model-form validation requires avec links to point to another
  attendee in the same event. Direct ORM writes must call `full_clean()` if they
  modify this relation.

## Forms

- Creation/Edit forms override `save()` to enforce slug uniqueness
  (`slugify_max`), normalize signup settings when `sign_up` is false, and stamp
  modified times.
- `PasscodeForm` is a simple `forms.Form` used when `passcode` is required.

## Views & Routing

- `IndexView` lists upcoming and past events separately.
- `EventDetailView` handles GET (render + optional redirect link) and POST
  (passcode validation + signup). On success it redirects back to the detail
  page with anchor fragments for certain event types (Årsfest, etc.). Template
  overrides can be triggered by event title or slug for special layouts.

## Websocket Layer

- `events/consumers.py` and `websocket_utils.py` push attendee updates via
  channels. Ensure the slug used in `ws_send` matches the subscription on the
  front end.

## Extending / Gotchas

- Association capabilities: `REGISTRATION_TERMS_ENABLED` (date) adds the terms
  checkbox to registration forms and the admin field;
  `KK_EVENT_TEMPLATES_ENABLED` (kk) adds the kk event-template choices to the
  admin forms. Defaults live in `core/settings/common.py`; enable them per
  association in its settings module rather than adding `PROJECT_NAME` checks.
- Any changes to registration fields must keep `Event.make_registration_form()`
  in sync; inconsistent `choice_list` formatting breaks multiple-choice inputs.
- When altering attendee serialization, update both the model and the JS that
  renders real-time updates.
- Parent/child events rely on consistent `parent` assignments; deleting a parent
  cascades to children and could orphan registrations.
