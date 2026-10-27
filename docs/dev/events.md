# Events Development Notes

## Data Model Overview

- `Event` (`events/models.py`) drives everything: content, schedule, signup
  windows, capacity, avec support, optional captcha/passcode, parent-child
  relationships, and background images (`ImageField` or `PublicFileField`
  depending on storage). `background_image_layout` (`BackgroundImageLayout`:
  `full` or `sides`) picks how the generic detail page shows that picture; see
  "Background picture layouts" under Extending / Gotchas.
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
  `EventAttendeesInlineFormSet`, which pre-shifts the formset's `attendee_nr`
  values into a non-conflicting band before saving so a drag-and-drop reorder
  can never violate `unique_attendee_nr_per_event` mid-save (the sortable JS
  writes the final numbers in original row order, which would otherwise
  collide). Rows created by concurrent signups after the admin page loaded are
  not part of the formset and are never shifted: they keep the number the
  signup flow allocated and showed. A stale form row that claims one of those
  numbers is renumbered from `Event.attendee_nr_counter` (and logged as a
  warning) instead of failing the save, so an admin saving during a signup
  rush cannot 500.
- Custom admin action `delete_participants` prompts for confirmation before
  removing attendee rows.
- `EventAnswersWidget` (`events/widgets.py`) renders `EventAttendees.preferences`
  as one control per `EventRegistrationForm` row instead of a JSON textarea:
  text input for text questions, a select for multiple choice, and Ja/Nej for
  checkbox questions. Answers whose question was renamed or deleted are still
  shown, as orphan rows, so they are not silently dropped. The inline builds the
  question list per request (and per child event, because child signups store
  their answers on the parent attendee row) and the standalone attendee admin
  resolves questions from the attendee's `original_event` or `event`.
- Extra admin URL `/list/` renders `events/list.html` for an event, showing
  the registration answers.
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
- `events/api.py::upcoming_events` (`GET /api/events/upcoming/`, route name
  `api:events:upcoming`) is a public, unauthenticated JSON endpoint listing
  published events with `event_date_end` in the future. It is wired in from
  `events/api_urls.py` via `core.urls.common.API_ROUTES['events']`. The
  shared `/api/` root is assembled automatically in `build_urlpatterns()`
  from whichever `API_ROUTES` keys were also requested from `ROUTES`, so an
  association that leaves `'events'` out of its route list gets neither the
  HTML routes nor `events.api_urls` imported — no separate toggle to
  remember. See the comment above `API_ROUTES` in `core/urls/common.py`
  before adding another app's API. It excludes `members_only` events
  (matching `EventDetailView._requires_member_login`) and passcode-protected
  events (matching the passcode gate in `EventDetailView.get`/
  `handle_passcode`) — anonymous visitors cannot view either kind of detail
  page in full, so both are left out of this public listing too. Each entry
  has `id`, `title`, `slug`, an absolute `url`, ISO-8601
  `event_date_start`/`event_date_end`, `content` (raw CKEditor HTML, unlike
  the `.ics` feed which strips tags), an absolute `image`
  (`background_image_url`), and `redirect_link`. The top-level response also
  has `truncated`: `events` is capped at `MAX_RESULTS` (200) and ordered by
  `(event_date_start, id)` for a stable order, and `truncated` is `true`
  when more events exist beyond that cap. `title`/
  `content` follow the site's cookie-based language by default (see
  `date/middleware.py`; `Accept-Language` is ignored); pass `?lang=` to pick
  a language explicitly instead, e.g. for machine clients that do not carry
  the `django_language` cookie. Responses carry a 60s public `Cache-Control`
  header plus `Vary: Cookie`, since the body depends on the language cookie.
  There is no per-request auth or CSRF requirement since it is read-only and
  public.

## Websocket Layer

- `events/consumers.py` and `websocket_utils.py` push attendee updates via
  channels. Ensure the slug used in `ws_send` matches the subscription on the
  front end.

## Extending / Gotchas

- Background picture layouts: `templates/common/events/detail.html` renders the
  picture as `<img>` elements styled by `static/common/events/css/background.css`,
  which it links only when the event has a picture. It is a separate sheet because
  `pulterit` and `sf` replace `events/css/detail.css`, so rules there would not reach
  them. `full` puts a `position: fixed` image with `object-fit: cover` inside an
  absolutely positioned layer with `clip-path: inset(0)`, so the picture is sized
  against the viewport on every device and clipped to the page wrapper instead of
  painting over the footer. The old inline `background-size: cover` was sized
  against the whole page on phones (where `background-attachment: fixed` is off),
  which zoomed the picture far past the screen. `sides` shows the picture as a
  banner above the title below 1200px. From 1200px it shows two sticky copies in
  the gaps beside the 800px `.container-size` text column (not `container-md`,
  which is far wider than the visible text). Each picture is capped to stay slightly
  smaller than the event card. Each column is at most 90% of the text column wide and
  as tall as the card, because `.content`'s margins collapse through
  `.container-size`. The picture box is at most the column's height and is inset by
  1.5rem of padding, so on a short event the side pictures are small by design.
  Because the box never outgrows its column, sticky positioning always has room to
  work. Layering relies on positioning and DOM order, not `z-index`.
- Background tint: `Event.background_image_color` (`#rrggbb`, not editable) holds the
  picture's dominant colour. `events.images` finds it by reducing a
  64px thumbnail to 5 colours and taking the largest cluster, skipping transparent
  pixels. When it is set, the template adds `event-bg--tinted` and an inline
  `--event-bg-color`, and the stylesheet paints the page background with that colour
  mixed 75/25 with black. Without a colour, no background is set, so the page keeps
  its own. Pictures stored before the field existed are filled in by
  `manage.py backfill_event_background_colors` (see `operations.md`). Only the generic detail page honours the field: the baal,
  wappmiddag, kk100 and Årsfest templates keep their own background CSS.
  The column has a `db_default` as well as a `default`, so the previous release
  can still insert events into the shared database during a blue-green deploy.
- Background picture uploads: `Event.save()` passes a newly assigned `image` or
  `s3_image` (an uncommitted `FieldFile`) to
  `events.images.process_background_image`. That reads the file once and returns a
  copy shrunk to fit within 1920x1080, keeping its shape, together with its
  dominant colour. It never crops or enlarges. Every picture is first normalised
  to RGB, RGBA, L or LA. Wide greyscale is scaled rather than converted, because
  Pillow's `convert()` clips values above 255 to white. 16-bit pictures are scaled
  from 0-65535, and 32-bit pictures that go beyond that are scaled by their
  brightest pixel. Palette or colour-key transparency becomes an alpha channel.
  The EXIF orientation is applied before resizing, because re-encoding drops all
  EXIF data (GPS position included) and phone photos would otherwise end up
  sideways. JPEG, PNG and WebP keep their format. A lossless WebP stays lossless,
  detected from its `VP8L` chunk because Pillow does not report it. Other still
  formats become PNG when they have transparency and JPEG otherwise. The ICC
  colour profile (iPhone photos are Display P3) is kept unless the colour space
  changed, for example CMYK to RGB. HEIC/HEIF is readable because
  `EventsConfig.ready()` registers `pillow_heif`; `gallery` does the same, but not
  every association installs it. A picture that already fits and is upright is
  stored byte for byte. Animated GIF, PNG and WebP files, and unreadable files,
  are stored as uploaded. Pillow's `is_animated` only means "more than one frame",
  so other multi-frame files (phone JPEGs with an embedded second picture, which
  open as MPO, multi-page TIFFs, multi-image HEIFs) are processed from their first
  frame. Pictures that are already stored are never reprocessed.
- Tint bookkeeping: `background_image_color` always describes the picture the page
  shows, which is `image` before `s3_image`, as in `background_image_url`. A new
  upload to the field that is not shown leaves the colour alone. When the shown
  picture changes without an upload (for example `image` is cleared and an older
  `s3_image` takes over), `save()` compares against the stored row and reads the
  colour from storage. Clearing both pictures clears the colour. A
  `save(update_fields=[...])` that includes a picture field also saves
  `background_image_color`. A call without picture fields skips the processing.
  Assign the file to the field (as forms do) rather than calling
  `event.image.save(name, content)`. That writes the file to storage immediately,
  so `save()` sees an already-stored file and neither resizes it nor reads its
  colour.
- Association capabilities: `REGISTRATION_TERMS_ENABLED` (date) adds the terms
  checkbox to registration forms and the admin field;
  `KK_EVENT_TEMPLATES_ENABLED` (kk) adds the kk event-template choices to the
  admin forms. Defaults live in `core/settings/common.py`; enable them per
  association in its settings module rather than adding `PROJECT_NAME` checks.
- The Årsfest layout lives in `templates/common/events/arsfest_base.html`, and an
  association overrides only the block that differs: `arsfest_logo`,
  `arsfest_heading_block` (the whole `h1`), `arsfest_heading` (its text),
  `arsfest_shell_classes`, `arsfest_content_classes`, `arsfest_header_extra`,
  `arsfest_main_tab_class`, `arsfest_background_style`, `arsfest_scripts`,
  `arsfest_signup_tab` and `arsfest_attendee_tab`. `templates/common/events/arsfest.html`
  is a one-line `{% raw %}{% extends %}{% endraw %}` of that base, and every association file is now a
  short override: date keeps its mascot, its edition number and its click easter
  eggs, pulterit and biocum keep their own logo and background, sf adds a
  stylesheet. The easter eggs belong to DaTe alone, because they load DaTe's audio
  and overwrite the heading, so no other association fills `arsfest_scripts`.
  `templates/impuls/events/arsfest.html` exists only to stop Impuls inheriting
  DaTe's page, since Impuls' template path includes `templates/date`.
  A template that only fills blocks is exempt from the near-copy ratchet, because it
  has no page body of its own to have been copied. Dropping a registration tab needs no override:
  which tabs appear follows the event. Adding a tab means adding a link whose `data-nav`
  and `#/` hash carry the key, plus a `.ball-content` panel carrying that key as its
  `id`: both the click handler and the hash navigation select the panel by id, and fall
  back to the main panel when no id matches.
- The Årsfest tabs follow the event rather than the layout: the Anmälan tab and the
  sign-up panel render only while the event has `sign_up` set, and the Anmälda tab
  only while `Event.show_attendee_tab` holds, which means the list is shown for that
  event and the event either takes sign-ups or already holds registrations. An event
  with sign-up off and no registrations is therefore a plain information page with no
  registration tabs, while an event that takes sign-ups offers the Anmälda tab for as
  long as its attendee list is shown.
  DaTe, Biocum and Pulterit render their own standalone copies of the page and apply
  the same conditions; Baal, KK100 and Wappmiddag still carry unconditional tabs, and
  Tomtejakt renders its registration sections without a tab row.
- The tabs are presentation only. The sign-up POST is accepted whenever the event has
  `sign_up` set and its registration window is open, whether or not a tab points at
  the form, and hiding a tab never disables registration.
- Any changes to registration fields must keep `Event.make_registration_form()`
  in sync; inconsistent `choice_list` formatting breaks multiple-choice inputs.
- When altering attendee serialization, update both the model and the JS that
  renders real-time updates.
- Parent/child events rely on consistent `parent` assignments; deleting a parent
  cascades to children and could orphan registrations.
