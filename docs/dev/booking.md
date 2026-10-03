# Booking Development Notes

## Scope
The `booking` app owns the public room-booking pages: a list of bookable rooms, a detail page per room with a booking form, and the per-room code that visitors without a website account use to unlock that form. The same models record bookings made by signed-in members, and the Django admin is the management surface.

The app is association-agnostic. Nothing under `booking/` reads `PROJECT_NAME` or `STAFF_GROUPS`. The one content variable it touches is optional: `booking/emails.py` reads `CONTENT_VARIABLES["ASSOCIATION_EMAIL"]` to name the board's address in the confirmation email, because an email body is rendered without a request and the context processor does not run there. It defaults to an empty string, and the templates that show the same address guard on it being set, so an association that leaves it empty loses the sentence and nothing else. The other association-specific parts are which variants list the app in `INSTALLED_APPS`, which variants mount its route key, and which variants set the `BOOKING_ENABLED` capability. An association that installs the app and creates rooms gets working behaviour with no further configuration.

Where the code lives:

- `booking/models.py`: `Room`, `Booking`, `BookingSettings`.
- The public lists print a time range as `18:00 - 20:00`, and add the end date with its weekday when the range crosses midnight, so a booking or a closure that runs over several days cannot be read as a same-day one. The end date appears only then, because repeating it on every row is noise.
- `booking/templatetags/booking_dates.py`: `short_date` and `year_suffix`, the two filters that format a date in the public lists. Weekday always, year only when the date is not in the current year, both taken from the active locale and measured against `access.now_at()` so a test can pin the year boundary.
- `booking/access.py`: the per-room codes, the session token, and the HTTP gate.
- `booking/views.py`, `booking/forms.py`, `booking/urls.py`: the public pages.
- `booking/admin.py`: the admin registrations.
- `booking/emails.py`: the confirmation email, sent to whoever booked.
- `booking/ics.py`: the calendar invite attached to that email.
- `templates/common/booking/`: `index.html`, `room_detail.html`, `my_bookings.html`, `cancel_booking.html`, `partials/code_form.html`, `partials/board_contact.html`, and `email/booking_confirmation.html` plus `email/booking_confirmation.txt` (see the routes section).
- `static/common/booking/css/booking.css`: the shared stylesheet the templates pull in.

## Data model (`booking/models.py`)

### `Room`
- `name` (max 255), `description` (optional text).
- `bookable_from` and `bookable_until` are optional times of day. Both empty (the default) means the room can be booked at any hour; both set means bookings must start and end inside that window on the same local day. `Room.clean()` refuses one without the other and a window whose end is not after its start, and `Room.has_bookable_hours` answers whether a window is in force.
- `code_generation` and `rotated_at` are the per-room code state, described below.
- Default ordering is `('name', 'pk')`.
- There is no active or visible flag: every room row is public. Closing a room for a while is a `Closure`, and removing one is a delete, which cascades to its bookings.

### `Closure`
- `room` (FK, `CASCADE`, `related_name='closures'`), `start`, `end`, and an optional `description` shown to visitors.
- A database check constraint, `closure_end_after_start`, is the backstop, and `Closure.clean()` refuses an end that is not after its start.
- A closure blocks new bookings that overlap it. It does not touch bookings already made inside it, by design: closing a period is not cancelling what somebody booked, and deleting a booker's row silently would be worse than telling them.
- `_upcoming_closures()` in `booking/views.py` feeds the "Stängt" list on the room page, so a visitor sees why the room is unavailable before filling in the form.

### `Booking`
- `booker_label(author)` is the single place that decides what to call the member behind a booking: the profile's full name when there is one, and the account name otherwise. A row reading a login handle next to a user card reading a full name looks like two different people, so both the snapshot and the display go through it.
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
- It rejects a booking longer than `BOOKING_MAX_DURATION` (one week), measured through UTC so a span across a daylight saving change is not an hour out. There is no limit on how far ahead a booking may be made.
- When the room and both times are present, and nothing above has already failed, it rejects the booking against the room's bookable hours, then against a closure, then against any other booking for the same room satisfying `start < new end` and `end > new start`. The closure message is checked before the overlap message because "the room is closed" is the truer explanation when both apply.
- An edit excludes its own row, and bookings that only touch (`end == new start`) do not overlap. The overlap query does not filter by time, so an old booking still blocks a new one.

`clean()` is reached through `full_clean()`, which in practice means the public forms and the admin form. A direct write such as `Booking.objects.create(...)` bypasses it, and only the check constraint would catch a reversed pair of times.

The create path in `room_detail` wraps validation and save in `transaction.atomic()` and locks the room row with `Room.objects.select_for_update()` before validating, so two simultaneous submissions for one room cannot both pass the overlap check. SQLite ignores `select_for_update`, and `core/settings/test.py` uses in-memory SQLite, so the tests cannot prove that part; production runs PostgreSQL.

## Where the code state lives

`Room` carries `code_generation` (default 1, `editable=False`) and `rotated_at` (nullable, `editable=False`). Each room has its own, which is what makes the codes independent: the office and the sauna do not share a code, a room lent to an outside group can have a code those people never see for the rest of the house, and rotating one room leaves every other room alone. `Room.rotate_code()` moves that room to the next generation and stamps `rotated_at`, bumping the counter with a database-side `F('code_generation') + 1` rather than in Python, so two rotations racing each other cannot both read the same value and write it back.

`RoomAdmin.save_model()` writes only the editable fields. A plain `save()` would also put the generation and the rotation moment back from whatever the request read, undoing a rotation that landed in between, so the room form does not write them at all.

`BookingSettings` is now only the association-wide note about how a visitor gets a code: an optional `code_instructions` TextField, reached through `BookingSettings.get_solo()`. It has no code of its own and nothing to rotate. The public path reads it directly through `_code_instructions()` in `booking/views.py` rather than through `get_solo()`, so an anonymous page view does not create the row as a side effect.

`code_instructions` exists because the distribution channel is not the website's decision. The board hands a code out however it likes, so nothing in the app names a channel: the default copy says only that the board provides the code, and an association that wants to be specific writes its own sentence. Like `Room.name` and `Room.description`, the field is editor content and is not translated, so an English visitor reading a Swedish sentence is the same trade-off the app already makes for rooms.

## The booking code (`booking/access.py`)

### Derivation
```
digest = HMAC-SHA256(SECRET_KEY, 'booking-code:<room pk>:<generation>')
number = int.from_bytes(digest[:8], 'big') % 10**6
code   = str(number).zfill(6)
```

The result is always six digits, with leading zeros kept. The room's primary key is in the message, so two rooms on the same generation still have different codes, and the name is not, so renaming a room does not change its code.

### Why there is no schedule
A code is a pure function of `SECRET_KEY`, the room and that room's `code_generation`. Nothing in the derivation reads the time, so a code stays exactly where the board left it: `current_code(room)` takes no moment at all, and no task has to run for codes to remain correct. Rotation is an explicit act by someone holding `booking.change_room`, through the **Byt bokningskoden nu** admin action on the room list, which reports each new code with its room name. Codes are never stored, but they are always derivable, so the room list and each room's page display the current one at any time; the message is only so the board has the new ones in hand straight after rotating.

The trade-off this makes is deliberate and worth stating plainly: a scheduled rotation used to be one of the two things bounding an automated guesser. With rotation on demand, that bound is gone. A code nobody rotates stays valid indefinitely, and what is left is weaker than it looks: the five-attempt limit and the lockout live in a session cookie a script simply discards, and the captcha fails open when `CF_TURNSTILE_SECRET_KEY` is empty. Against a determined guesser of a six-digit code the honest summary is that the code is a speed bump, not a wall, and that the association is relying on the code being shared among people who do not attack it. Rotating after any suspected leak is the control that remains, and `rotated_at` is displayed so a stale code is at least visible.

### Grace window
- `accepted_codes()` returns the current generation's code, plus the previous generation's code while less than `BOOKING_CODE_GRACE` (15 minutes) has passed since `rotated_at`. The window is anchored to the stored moment, so it does not slide forward with every request, and it only opens for a generation above 1: there is no predecessor to keep alive before the first rotation.
- The elapsed time is required to be non-negative, so a `rotated_at` stamped in the future by clock skew does not revive the previous code.
- `check_code()` strips whitespace and compares with `hmac.compare_digest` against every accepted code with no early exit.

### Cancelling
Two paths, because the two kinds of booker can prove different things.

A member cancels from `booking:my_bookings` (`/booking/mine/`, `MyBookingsView`, login required). The POST carries the booking id and the queryset is filtered to `author=request.user` and `end__gte=now`, so an id that is somebody else's, unknown, or already finished resolves to nothing and becomes a 404. There is no code on this path: the account is the credential.

Somebody without an account uses `booking:cancel` (`/booking/cancel/`), where they paste the code from the confirmation email. The code is `HMAC-SHA256(SECRET_KEY, 'booking-cancel:<booking pk>')[:12]`, derived rather than stored, so `booking_with_cancel_code()` finds the booking by deriving the code for each upcoming booking and comparing with `hmac.compare_digest`. Twelve hex characters is deliberate: a room code is typed by people who were told it, while this one deletes a row, so it has to be beyond guessing rather than merely inconvenient. Only upcoming bookings are searched, which is also exactly the set that may be cancelled.

The public page is two steps. The GET that a mail client or a link scanner follows only shows which booking the code belongs to, and the deletion happens on the POST behind the confirmation button. A GET that cancelled would let a mailbox provider that prefetches links delete a booking before its owner ever read the email.

Both paths delete the row rather than marking it cancelled, which is what the admin's delete does. Nothing is emailed on cancellation, to the booker or to the board, so a board that needs to hear about cancellations has to watch the admin.

### Session token and per-room session state
- `session_token(room)` is `HMAC-SHA256(SECRET_KEY, 'booking-session:<room pk>:<generation>')[:32].hex()`.
- The token depends on the room and its generation, so rotating a room invalidates exactly the unlocks that room granted and no expiry has to be stored in the session. Note the asymmetry: the code that was just handed out keeps working for the grace window, but an unlock granted with it does not survive the rotation.
- `booking_access_token`, `booking_code_attempts` and `booking_code_lockout_until` hold mappings keyed by the room primary key as text, because the default session serializer is JSON and JSON object keys are strings. Attempts and lockouts are therefore per room too: fumbling one room's code does not lock a visitor out of another's. `_room_state()` reads a mapping and treats anything else as empty, so a session written by an earlier release loses its unlock and heals on the next visit instead of needing a migration.
- It is an HMAC over a distinct message rather than a hash of the six-digit code: the code space has only a million entries, so a stored hash of the code would be a trivially reversible fingerprint, while the HMAC needs `SECRET_KEY`. The typed code itself is never written to the session.
- The digest is hex-encoded because Django's default session serializer is JSON and cannot store bytes. `_stored_token()` accepts either form, and `session_has_access()` compares with `compare_digest`.

### Attempt limit
- `BOOKING_ATTEMPT_LIMIT` is 5 and `BOOKING_LOCKOUT_SECONDS` is `15 * 60`. The counter lives in the session under `booking_code_attempts`; the fifth wrong code also sets `booking_code_lockout_until` to now plus 900 seconds. A correct code clears both keys.
- `lockout_remaining()` returns the seconds left and clears the lockout keys once the time has passed.

### Test seams
- `now_at()` is the single time seam, and it now only matters to the grace window and the lockout. Tests patch `booking.access.now_at` to pin "now".
- Every code function takes a room, so the pure-function tests pass an unsaved `Room` with an explicit primary key and generation and touch no database. `at=` survives only where the moment is genuinely read, which is the grace window.

## Public routes and views
`booking/urls.py` sets `app_name = 'booking'` and the shared URLconf mounts it at `booking/`:

- `booking:index` at `/booking/`, `RoomListView`.
- `booking:room_detail` at `/booking/<pk>/`, `views.room_detail`.

`RoomListView` lists every room and attaches up to `UPCOMING_BOOKING_LIMIT` (50) bookings whose `end` is still in the future, ordered by `start`. The queryset is deliberately not cached: an admin edit shows up on the next request.

`room_detail`:

- 404 for a missing or inactive room.
- For a signed-in member, or an anonymous visitor whose session token matches the current slot, it renders `templates/common/booking/room_detail.html` with the room, its future bookings (same 50 limit, restricted to that room), and a booking form.
- `BookingForm` for a signed-in member (the author is taken from the request), `AnonymousBookingForm` for a visitor (adds required `booker_name` and `booker_email`).
- Both forms declare `description` as a `Textarea` (3 rows) with `help_text`, overriding the single-line input the model field would produce, and the help text says that only the board reads it. That is the field the board needs to know what the room is for.
- `BookingForm.__init__` sets a `min` attribute on the `start` and `end` widgets to `access.now_at() - BOOKING_PAST_GRACE`, truncated to the minute. It derives the boundary from the same constant the model uses, so the browser picker offers exactly the range `Booking.clean()` accepts instead of a stricter one: a floor of "now" would refuse a start the server takes, and would invalidate a start that was picked a moment earlier whenever the form is re-rendered after another error. Truncation leaves the picker a fraction more permissive than the server, never less, and the model check stays the authority.
- The captcha check runs twice on the anonymous path, both through `core.utils.validate_captcha`: once in `booking_code_gate()` and once on the anonymous booking POST. Both call it with `access.captcha_response(request)`, which turns a missing field into an empty string, because the shared helper only short-circuits locally on `""` and a missing field would otherwise reach Cloudflare. A challenge that fails on the gate is reported through the `captcha_error` context key, and crucially the gate does not look at the submitted code at all in that case: validating it would tell a client that has not passed the challenge whether its guess was right, one guess at a time, without consuming an attempt. A rejected challenge is not a code attempt, so it does not count against the visitor's five either.
- On success the booking is saved, `emails.notify_booker(booking, cancel_url=..., site_url=...)` queues the confirmation, a success message is added, and the view redirects back to the same room page (POST/redirect/GET). On a validation error the page is re-rendered with the bound form and its field errors, at status 200.
- The public templates render room names and start/end times only. The booking description, the booker name and the booker email are never rendered on the public pages.

`templates/common/booking/index.html` renders the room cards and the upcoming-booking list, and says in one line that an account books directly while everyone else needs a code. It deliberately does not say how the code is obtained; that belongs to the page that asks for it. `room_detail.html` doubles as the code-gate page: it still shows the room name, its description and the upcoming bookings, and swaps the booking form for the code form. `partials/code_form.html` renders the explanation of where the code comes from, then either the code input or, during a lockout, the "too many attempts" message with no form at all. The first sentence of that explanation is `code_instructions` when the board has written one, and "Bokningskoden får du av styrelsen." when it has not; the second sentence, that an account needs no code, always follows, because it is a fact about the site rather than about the board's process. `code_instructions` reaches the template through the gate's context, from `_code_instructions()` in `booking/views.py`. `partials/board_contact.html` is the one-line "contact the board at `ASSOCIATION_EMAIL`" note, included by the room list, the room page and the gate; all three guard on `ASSOCIATION_EMAIL` being set, because the templates are shared and an association that leaves it empty would otherwise render a broken sentence. It is a contact route, not a claim about how the code arrives.

`booking/emails.py` sends one confirmation per booking, member or not, with `notify_booker(booking, cancel_url=..., site_url=...)`. The mail is queued after the transaction commits, through `core.utils.enqueue_task_on_commit` and the Celery task `core.utils.send_email_with_attachments_task`. That task exists because `send_mail` cannot carry a file: it builds an `EmailMultiAlternatives` itself and attaches the calendar invite, keeping the same failure handling as `send_email_task`, where a mail problem is logged rather than raised because the row it describes is already saved.

The message complements the confirmation on the page rather than replacing it. The view adds its `Tack! Din bokning är registrerad.` message whether or not there is an address to send to, and the mail is a second copy of the same news with the details worth keeping.

Bodies are `templates/common/booking/email/booking_confirmation.html` and `.txt`, rendered as a multipart pair. Both are rendered without a request, so the context processor that exposes the association's variables does not run: `emails.py` passes `association_email` from `settings.CONTENT_VARIABLES` into the context itself, and the email names that address, which is otherwise the booker's only route to the board.

`notify_booker` returns early when there is no address to send to, which is `booking.author.email` for a member and `booking.booker_email` for somebody without an account. The recipient is the only difference between the two cases; the body is the same template, and the `cancel_code` key is `None` for a member, which is how the template knows to say "cancel from your account" instead of showing a code.

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
- Homepage: `templates/date/date/components/bookings.html` is included from `templates/date/date/start.html` and wrapped in `{% raw %}{% if BOOKING_ENABLED %}{% endraw %}`. Its data comes from `_homepage_context()` in `date/views.py`, which imports `booking.models.Booking` lazily and only when the capability is on and the app is installed, then takes the next five bookings that start within seven days. Each card links to the room page of the booking it describes, not to the room list, because the card names one room and one time.

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
- `RoomAdmin` lists name, bookable hours, the current code, when it was rotated and a booking count, searches by name, and carries a `BookingInline` plus a `ClosureInline` limited to periods that have not ended, so a room's bookings and closures can be managed from the room page.
- `ClosureAdmin` lists room, period and description, filters by room and start, and carries a date hierarchy.
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

The codes are testable without `freezegun` because of the seams above: patch `booking.access.now_at`, or pass `at=` straight to the `access` functions. The app's tests live in `booking/tests.py`.

## Risks and gotchas
- The homepage block sits inside `{% raw %}{% cache 300 main_page_fixed LANGUAGE_CODE %}{% endraw %}` in `templates/date/date/start.html`, so flipping `BOOKING_ENABLED` can take up to five minutes to show on the homepage. A stale fragment can even hold a link to a now unmounted route for that long. The app's own pages are not cached and change on the next request.
- The attempt counter and the lockout live in the session, which limits a browser but not a script: a client that never returns the session cookie starts from zero attempts on every request, so the five-attempt limit does not bound an automated guesser. What slows one down is the captcha on the gate, which makes every guess cost a challenge. The rotation no longer helps, because the code does not move unless somebody moves it. Nothing keyed on a discarded cookie and nothing that is optional can be called an enforceable bound. The residual gap is the association that has not configured Turnstile: `core.utils.validate_captcha` fails open when `CF_TURNSTILE_SECRET_KEY` is empty, so with no secret there is no captcha and no server-side limit either. Closing that properly needs a rate limit keyed on something the client cannot discard, and that needs a decision about client addresses first: behind an ingress that rewrites the source address, every visitor shares one key and a low threshold would lock out all of them.
- Direct edits to rooms and bookings in the admin appear on the public booking pages immediately because those views query the database on every request. Only the homepage block is cached.
- The origin filter reads "came from the public form" as "no author and a recorded address". That is an inference, not a stored fact, and it is wrong for the two rows that do not fit the pattern: a member booking whose address the board filled in by hand, and an admin-created booking with an account-less booker and an address. Storing the origin would need a new field, and the app is not deployed yet, so the inference is used instead and the guide describes it.
- The room page's inline hides past bookings, so a booking that was made and has since passed is edited through the Booking changelist. Nothing is deleted by the filter: an inline formset only saves and deletes the rows it was given.
- `select_for_update` is a no-op on SQLite, so the tests cannot cover the race that the room lock exists to prevent. Verify that path against PostgreSQL.
- The code is derived from `SECRET_KEY`, so rotating the secret changes every code and invalidates every unlock at once.
- If the member account behind a booking is deleted, the booking survives with no author and displays the recorded name, or "Extern bokning" when none was recorded.

## Permissions and provisioned staff groups
If this app is ever installed for an association whose staff group permissions are provisioned from code, a single-group restriction cannot be enforced with Django permissions alone. `members/provisioning.py` runs on `post_migrate` from `members/apps.py` and, when the `SF_ROLE_PERMISSION_SCOPES` setting (`core/settings/sf.py`) is present, grants every permission of every local app to several broad groups. `booking` is a local app, so its permissions would be handed to those groups automatically and the board-only rule would be defeated. Issue #1193 tracks that provisioning behaviour.
