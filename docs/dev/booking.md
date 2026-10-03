# Booking Development Notes

## Scope
The `booking` app owns the public room-booking pages: a list of bookable rooms, a detail page per room with a booking form, and the rotating code that visitors without a website account use to unlock that form. The same models record bookings made by signed-in members, and the Django admin is the management surface.

The app is association-agnostic. Nothing under `booking/` reads `PROJECT_NAME` or `STAFF_GROUPS`. The one content variable it touches is optional: `booking/emails.py` reads `CONTENT_VARIABLES["ASSOCIATION_EMAIL"]` to name the board's address in the confirmation email, because an email body is rendered without a request and the context processor does not run there. It defaults to an empty string, and the templates that show the same address guard on it being set, so an association that leaves it empty loses the sentence and nothing else. The other association-specific parts are which variants list the app in `INSTALLED_APPS`, which variants mount its route key, and which variants set the `BOOKING_ENABLED` capability. An association that installs the app and creates rooms gets working behaviour with no further configuration.

Where the code lives:

- `booking/models.py`: `Room`, `Booking`, `BookingSettings`.
- `booking/access.py`: the rotating code, the session token, and the HTTP gate.
- `booking/views.py`, `booking/forms.py`, `booking/urls.py`: the public pages.
- `booking/admin.py`: the admin registrations.
- `booking/emails.py`: the confirmation email for an external booker.
- `templates/common/booking/`: `index.html`, `room_detail.html`, `partials/code_form.html`, `partials/board_contact.html` and `booking_confirmation_email.txt` (see the routes section).
- `static/common/booking/css/booking.css`: the shared stylesheet the templates pull in.

## Data model (`booking/models.py`)

### `Room`
- `name` (max 255), `description` (optional text), `is_active` (default `True`).
- `is_active` is the bookable flag. A room with `is_active=False` disappears from the public pages, but the row and its whole booking history stay in the database. `RoomListView` and `room_detail` both filter on it, and `room_detail` returns 404 for an inactive room even on a direct URL.
- Default ordering is `('name', 'pk')`.

### `Booking`
- `room`: FK to `Room`, `on_delete=CASCADE`, `related_name='bookings'`.
- `author`: optional FK to the member model (`settings.AUTH_USER_MODEL`), `on_delete=SET_NULL`, `related_name='room_bookings'`. `None` means there is no website account behind the booking: either it came from a visitor, or the member who made it deleted the account afterwards.
- `booker_name` (max 255, optional), `booker_email` (optional), `start`, `end`, `description` (max 400, optional), `created` (`default=timezone.now`, not editable).
- Default ordering is `('start', 'pk')`.
- `save()` copies the author's `str()` into `booker_name` when that field is blank and an author is set. `author` is `SET_NULL`, so without the copy a deleted member's booking would lose its booker and read as a booking without an account. A name typed by the board is never overwritten.
- `is_external` is `author_id is None`. `booker_display` returns the member's `str()` when there is an author, otherwise `booker_name`, otherwise the fallback label "Extern bokning". Because the name is snapshotted, a booking whose member deleted the account still displays that member's name.
- The only rule the database enforces is the `booking_end_after_start` check constraint, `end > start`. It is a backstop only: it says nothing about overlaps, and it fires on write.

### A start time in the past
`clean()` refuses a new booking whose `start` is more than `BOOKING_PAST_GRACE` (10 minutes) in the past, with "Starttiden kan inte vara i det förflutna.". The grace exists because the `datetime-local` input has minute precision and a form takes a moment to fill in, so a start equal to the current minute can be marginally stale by the time the POST lands.

The check is guarded by `self._state.adding`: only a booking that is being created is refused. A booking that already exists keeps whatever times it has, so the board can still correct the description of one whose time is over from the admin without being told its time is invalid.

The clock comes from `booking.access.now_at()` through a function-level import in `models.py` (`access` imports this module, so a module-level import would be circular). That keeps the single time seam the gate already uses, and it is what lets the tests pin "now" while the views and the model agree on it. Without the rule a mistyped year was saved, confirmed by email, and then invisible on every public list while still occupying the admin, because the public queries filter on `end__gte=now`.

### An external booking
An external booking is an ordinary `Booking` row with `author` unset and the name and email recorded in `booker_name` and `booker_email`. There is no separate model, no account is created for the booker, and the email address on the row is the only link back to them. An unset `author` is also what a booking made by a member looks like after that member deletes the account, so `author is None` means "no account now" rather than "never had one"; the snapshotted `booker_name` is what tells the two apart.

### Overlap prevention
Overlap prevention lives in `Booking.clean()`:

- `end <= start` produces an error on `end`.
- A new booking more than `BOOKING_PAST_GRACE` in the past produces an error on `start` (see above).
- When `author_id is None` and `booker_name` is blank, it produces an error on `booker_name`.
- When the room and both times are present, it rejects the booking if any other booking for the same room satisfies `start < new end` and `end > new start`. An edit excludes its own row, and bookings that only touch (`end == new start`) do not overlap. The query does not filter by time or by room activity, so an old booking in a since-deactivated room still blocks a new one.

`clean()` is reached through `full_clean()`, which in practice means the public forms and the admin form. A direct write such as `Booking.objects.create(...)` bypasses it, and only the check constraint would catch a reversed pair of times.

The create path in `room_detail` wraps validation and save in `transaction.atomic()` and locks the room row with `Room.objects.select_for_update()` before validating, so two simultaneous submissions for one room cannot both pass the overlap check. SQLite ignores `select_for_update`, and `core/settings/test.py` uses in-memory SQLite, so the tests cannot prove that part; production runs PostgreSQL.

## `BookingSettings` (`booking/models.py`)
`BookingSettings` is a singleton reached through `BookingSettings.get_solo()`, which reads or creates `pk=1`. Its only field is `rotation_period`, one of `daily`, `weekly`, `monthly`, defaulting to `weekly`. Nothing else is configurable, and there is no stored password or code anywhere in the app: the code is derived from the server secret and the current clock, so the settings row can be shown read-only in the admin.

## The rotating code (`booking/access.py`)

### Derivation
```
digest = HMAC-SHA256(SECRET_KEY, 'booking-code:<slot>')
number = int.from_bytes(digest[:8], 'big') % 10**6
code   = str(number).zfill(6)
```

The result is always six digits, with leading zeros kept.

### Slots
- The slot key is `f'{rotation_period}:{calendar_part}'`, where `calendar_part` is `%Y-%m` for monthly and `%Y-%m-%d` for daily and weekly. Prefixing the period means a period change always changes the slot, even when the date part repeats.
- `daily` starts at local midnight, `weekly` at Monday local midnight (the code subtracts `weekday()` days from midnight), `monthly` on the first day of the month at local midnight.
- Boundaries are computed in the association's local time: `_as_local()` goes through `timezone.get_current_timezone()` and `timezone.localtime()`, and a naive input is treated as already local.
- `next_rotation()` returns the start of the slot after the current one. The admin uses it for the "when does the code change" column.

### Grace window
- `accepted_codes()` returns the current code, plus the previous slot's code while less than `BOOKING_CODE_GRACE` (15 minutes) has passed since the start of the current slot. The window is anchored to the slot start, so it does not slide forward with every request.
- `check_code()` strips whitespace and compares with `hmac.compare_digest` against every accepted code with no early exit.

### Session token
- `session_token()` is `HMAC-SHA256(SECRET_KEY, 'booking-session:<slot>')[:32].hex()`.
- The token depends on the slot, so a rotation invalidates every stored unlock on its own and no expiry has to be stored in the session.
- It is an HMAC over a distinct message rather than a hash of the six-digit code: the code space has only a million entries, so a stored hash of the code would be a trivially reversible fingerprint, while the HMAC needs `SECRET_KEY`. The typed code itself is never written to the session.
- The digest is hex-encoded because Django's default session serializer is JSON and cannot store bytes. `_stored_token()` accepts either form, and `session_has_access()` compares with `compare_digest`.

### Attempt limit
- `BOOKING_ATTEMPT_LIMIT` is 5 and `BOOKING_LOCKOUT_SECONDS` is `15 * 60`. The counter lives in the session under `booking_code_attempts`; the fifth wrong code also sets `booking_code_lockout_until` to now plus 900 seconds. A correct code clears both keys.
- `lockout_remaining()` returns the seconds left and clears the lockout keys once the time has passed.

### Test seams
- `now_at()` is the single time seam. Tests patch `booking.access.now_at` to pin "now".
- `at=None` and `access_settings=None` on `slot_for`, `current_code`, `next_rotation`, `accepted_codes`, `check_code`, `session_token`, `session_has_access`, `grant_session` and `booking_code_gate` let a test pass an explicit moment and an explicit settings object, so time can be pinned without `freezegun` and without a database write. `access_settings=None` means "read `BookingSettings.get_solo()`".

## Public routes and views
`booking/urls.py` sets `app_name = 'booking'` and the shared URLconf mounts it at `booking/`:

- `booking:index` at `/booking/`, `RoomListView`.
- `booking:room_detail` at `/booking/<pk>/`, `views.room_detail`.

`RoomListView` lists `Room.objects.filter(is_active=True)` and attaches up to `UPCOMING_BOOKING_LIMIT` (50) bookings whose `end` is still in the future, across all active rooms, ordered by `start`. The queryset is deliberately not cached: an admin edit shows up on the next request.

`room_detail`:

- 404 for a missing or inactive room.
- For a signed-in member, or an anonymous visitor whose session token matches the current slot, it renders `templates/common/booking/room_detail.html` with the room, its future bookings (same 50 limit, restricted to that room), and a booking form.
- `BookingForm` for a signed-in member (the author is taken from the request), `AnonymousBookingForm` for a visitor (adds required `booker_name` and `booker_email`).
- Both forms declare `description` as a `Textarea` (3 rows) with `help_text`, overriding the single-line input the model field would produce, and the help text says that only the board reads it. That is the field the board needs to know what the room is for.
- `BookingForm.__init__` sets a `min` attribute on the `start` and `end` widgets to `access.now_at() - BOOKING_PAST_GRACE`, truncated to the minute. It derives the boundary from the same constant the model uses, so the browser picker offers exactly the range `Booking.clean()` accepts instead of a stricter one: a floor of "now" would refuse a start the server takes, and would invalidate a start that was picked a moment earlier whenever the form is re-rendered after another error. Truncation leaves the picker a fraction more permissive than the server, never less, and the model check stays the authority.
- The captcha check runs twice on the anonymous path, both through `core.utils.validate_captcha`: once in `booking_code_gate()` and once on the anonymous booking POST. Both call it with `access.captcha_response(request)`, which turns a missing field into an empty string, because the shared helper only short-circuits locally on `""` and a missing field would otherwise reach Cloudflare. A challenge that fails on the gate is reported through the `captcha_error` context key, and crucially the gate does not look at the submitted code at all in that case: validating it would tell a client that has not passed the challenge whether its guess was right, one guess at a time, without consuming an attempt. A rejected challenge is not a code attempt, so it does not count against the visitor's five either.
- On success the booking is saved, `emails.notify_external_booker(booking)` runs, a success message is added, and the view redirects back to the same room page (POST/redirect/GET). On a validation error the page is re-rendered with the bound form and its field errors, at status 200.
- The public templates render room names and start/end times only. The booking description, the booker name and the booker email are never rendered on the public pages.

`templates/common/booking/index.html` renders the room cards and the upcoming-booking list, and says in one line that an account books directly while everyone else needs a code. `room_detail.html` doubles as the code-gate page: it still shows the room name, its description and the upcoming bookings, and swaps the booking form for the code form. `partials/code_form.html` renders the explanation of where the code comes from, then either the code input or, during a lockout, the "too many attempts" message with no form at all. `partials/board_contact.html` is the one-line "contact the board at `ASSOCIATION_EMAIL`" note, included by the room list and the room page; both guard on `ASSOCIATION_EMAIL` being set, because the templates are shared and an association that leaves it empty would otherwise render a broken sentence.

`booking/emails.py` sends one confirmation per external booking, through the Celery task `core.utils.send_email_task` and `core.utils.enqueue_task_on_commit`, so the mail is queued after the transaction commits. It returns early unless the booking is external and has an email address, so member bookings and nameless bookings send nothing. The body is `templates/common/booking/booking_confirmation_email.txt`. The body is rendered without a request, so the context processor that exposes the association's variables does not run: `emails.py` passes `ASSOCIATION_EMAIL` from `settings.CONTENT_VARIABLES` into the context itself, and the email names that address, which is otherwise the booker's only route to change or cancel.

## Session keys and the gate function
Three session keys, all namespaced with a `booking_` prefix so they cannot collide with other apps that keep gate state in the session:

- `booking_access_token` (`BOOKING_SESSION_TOKEN_KEY`): the per-slot unlock.
- `booking_code_attempts` (`BOOKING_ATTEMPTS_COUNTER`): the wrong-code counter.
- `booking_code_lockout_until` (`BOOKING_LOCKOUT_UNTIL`): the epoch second the lockout ends.

`booking_code_gate()` is a function rather than a decorator, and `room_detail` calls it itself. The room list is public, and the room page still renders the room's name, description and upcoming bookings; only the booking form is replaced by the code form, so the gate belongs inside the view that owns the form instead of in a decorator that would have to cover a whole view. The view routes a request to the gate when the visitor has no unlock, and also whenever the POST carries the code form, so an older tab cannot submit a code into the booking form after the visitor has unlocked the room elsewhere. The status codes mirror the exam bank gate: a fresh gate is 200, a wrong code is 403, and a lockout is 429, including the request that reaches the attempt limit. The redirect target is a URL name or an already resolved URL chosen by the view (`next_url`), never a value taken from the request, so the gate cannot be turned into an open redirect.

## The `BOOKING_ENABLED` capability
- Shared default: `BOOKING_ENABLED = False` in `core/settings/common.py`, next to the other association capabilities.
- DaTe: `core/settings/date.py` sets `BOOKING_ENABLED = env('BOOKING_ENABLED', bool, True)`, so the capability is on unless the environment sets it to a false value. `core/settings/test.py` pins it to `True` so the suite does not depend on a developer's `.env`.
- Templates: `core/context_processors.py` exposes it as `BOOKING_ENABLED`.
- Routing: `core/urls/date.py` adds the `booking` route key to its `build_urlpatterns(...)` call only when `settings.BOOKING_ENABLED` is true, and `core/urls/common.py` maps that key to `path('booking/', include('booking.urls'))`. With the capability off, the `booking/` paths are not routed at all.
- Homepage: `templates/date/date/components/bookings.html` is included from `templates/date/date/start.html` and wrapped in `{% raw %}{% if BOOKING_ENABLED %}{% endraw %}`. Its data comes from `_homepage_context()` in `date/views.py`, which imports `booking.models.Booking` lazily and only when the capability is on and the app is installed, then takes the next five bookings in active rooms that start within seven days. Each card links to the room page of the booking it describes, not to the room list, because the card names one room and one time.

Only DaTe parses the variable. No other module under `core/settings/` reads or sets `BOOKING_ENABLED`, and none of them lists `booking` in its installed apps or its URLconf, so setting `BOOKING_ENABLED` on another association's release has no effect.

To disable the feature on DaTe, set `BOOKING_ENABLED` to a false value (`False`, `0`, `off`, `no`, or an empty value; the shared `env` helper treats any string that is not a true value as false). The `booking/` paths and the homepage block disappear, while the app, its admin pages and all booking rows stay in place.

The repository's environment template is `.env.example`, the file contributors copy to `.env`. `BOOKING_ENABLED` is not listed there today, so add it there if the switch becomes part of local setup.

## Adopting the app in another association
1. Add `'booking'` to that variant's installed apps (`get_installed_apps([...])` in `core/settings/<variant>.py`). `core/settings/date.py` is the worked example.
2. Add the `booking` route key to that variant's `build_urlpatterns(...)` call. `core/urls/date.py` gates the key behind the capability; a variant that always wants the routes can pass the key unconditionally.
3. Set the `BOOKING_ENABLED` capability for that variant, either directly in the settings module or from an environment variable the module reads.
4. Run that variant's migrations so the `booking` tables exist.

The public templates under `templates/common/booking/` and `static/common/booking/css/booking.css` are shared, so nothing else is required. An association-specific override follows the usual `templates/<association>/` rules described in `docs/dev/templates.md`.

## Admin surface (`booking/admin.py`)
- `RoomAdmin` lists name, `is_active` and a booking count, filters on `is_active`, searches by name, and carries a `BookingInline` so a room's bookings can be managed from the room page.
- `BookingInline` shows only the room's upcoming bookings, soonest first, with `show_change_link`. Django does not paginate inlines, so an unfiltered inline grows without bound for a room with years of history and would open on the oldest rows. Past bookings stay reachable through the Booking changelist, which has the filters and the date drill-down for them.
- The inline's queryset also keeps every booking id the submitted formset names, read from the `-id` fields in `request.POST`. Cutoff alone is not enough: if a row's `end` passes between the page being opened and the form being submitted, the row would leave the queryset, Django would resolve the submitted id to an unsaved instance, `save_existing_objects()` would skip it, and a checked Delete or an edited description would be dropped while the save still reported success. `_submitted_pks()` on the inline is what closes that; `BookingAdminSurfaceTests` pins both halves.
- `BookingAdmin` lists room, a start/end time range, the booker display and a "no account" flag, filters on booking origin, room and start, adds a start-date drill-down, searches booker name, booker email and description, and marks the booker display and the account flag read-only. `ordering` is `('-start',)`, so the changelist does not open on the oldest booking ever made; this matches the descending ordering the other time-ordered admins in this project use.
- `BookingOriginFilter` (`admin.SimpleListFilter`) separates member bookings from bookings made through the public form. `author` alone cannot do it, because `SET_NULL` gives a deleted member's booking the same shape as a visitor's, so the filter also reads `booker_email`: the public form requires an address and a member booking never records one. "Bokning utan konto, via webbformuläret" is the address-bearing subset of "Bokning utan konto".
- The account flag column is labelled "Utan konto" rather than "extern". It is `is_external`, which is also true for a booking whose member deleted the account, so the old label stated something false about that row; the Bokare column carries the snapshotted name.
- `BookingSettingsAdmin` shows the rotation period, the current code and the next rotation, both computed and read-only. It refuses to delete the singleton and only allows adding one while no settings row exists.
- The admin is the only place that displays the current code. There is no separate "generate a code" action anywhere, because nothing is stored.
- `core/admin_ui.py` carries a `Booking` sidebar group (Bookings, Rooms, Booking Code) for the Unfold theme. Each link resolves only when its permission is held and its URL name exists, so the group disappears for an association that does not install the app.

## Testing
Run the app's tests with the test settings, which install the DaTe app set and set `BOOKING_ENABLED=True`:

```bash
uv run python manage.py test booking
```

Through the Docker helper, after `source env.sh`:

```bash
date-test booking
```

The rotating code is testable without `freezegun` because of the seams above: patch `booking.access.now_at`, or pass `at=` and `access_settings=` straight to the `access` functions. The app's tests live in `booking/tests.py`.

## Risks and gotchas
- The homepage block sits inside `{% raw %}{% cache 300 main_page_fixed LANGUAGE_CODE %}{% endraw %}` in `templates/date/date/start.html`, so flipping `BOOKING_ENABLED` can take up to five minutes to show on the homepage. A stale fragment can even hold a link to a now unmounted route for that long. The app's own pages are not cached and change on the next request.
- The attempt counter and the lockout live in the session, which limits a browser but not a script: a client that never returns the session cookie starts from zero attempts on every request, so the five-attempt limit does not bound an automated guesser. What does bound one is the captcha on the gate, which makes every guess cost a challenge, together with the rotation. The residual gap is the association that has not configured Turnstile: `core.utils.validate_captcha` fails open when `CF_TURNSTILE_SECRET_KEY` is empty, so with no secret there is no captcha and no server-side limit either. Closing that properly needs a rate limit keyed on something the client cannot discard, and that needs a decision about client addresses first: behind an ingress that rewrites the source address, every visitor shares one key and a low threshold would lock out all of them.
- Direct edits to rooms and bookings in the admin appear on the public booking pages immediately because those views query the database on every request. Only the homepage block is cached.
- The origin filter reads "came from the public form" as "no author and a recorded address". That is an inference, not a stored fact, and it is wrong for the two rows that do not fit the pattern: a member booking whose address the board filled in by hand, and an admin-created booking with an account-less booker and an address. Storing the origin would need a new field, and the app is not deployed yet, so the inference is used instead and the guide describes it.
- The room page's inline hides past bookings, so a booking that was made and has since passed is edited through the Booking changelist. Nothing is deleted by the filter: an inline formset only saves and deletes the rows it was given.
- `select_for_update` is a no-op on SQLite, so the tests cannot cover the race that the room lock exists to prevent. Verify that path against PostgreSQL.
- The code is derived from `SECRET_KEY`, so rotating the secret changes every code and invalidates every unlock at once.
- If the member account behind a booking is deleted, the booking survives with no author and displays the recorded name, or "Extern bokning" when none was recorded.

## Permissions and provisioned staff groups
If this app is ever installed for an association whose staff group permissions are provisioned from code, a single-group restriction cannot be enforced with Django permissions alone. `members/provisioning.py` runs on `post_migrate` from `members/apps.py` and, when the `SF_ROLE_PERMISSION_SCOPES` setting (`core/settings/sf.py`) is present, grants every permission of every local app to several broad groups. `booking` is a local app, so its permissions would be handed to those groups automatically and the board-only rule would be defeated. Issue #1193 tracks that provisioning behaviour.
