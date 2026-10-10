# Polls Development Notes

## Models
- `Question` stores text, `published_time`, multiple-choice settings, and `voting_options` (mapped to constants `ANYONE`, `MEMBERS_ONLY`, `ORDINARY_MEMBERS_ONLY`, `VOTE_MEMBERS_ONLY`). A `ManyToManyField` to `Member` via `Vote` tracks who voted.
- Publication follows the same `published_time` pattern as events/news: `NULL` is hidden, future is scheduled, past is public. Use `Question.objects.published()` (or the `Question.published` property) for public-facing lookups.
- `Choice` belongs to a question and keeps an integer `votes` counter plus a helper `get_vote_percentage()`.
- `Vote` stores which `Member` voted on which `Question` at `voted_at` time (only used when the poll isn’t anonymous).

## Views & Flow
- `IndexView` lists the five most recent published questions.
- `DetailView` renders a single poll; template decides whether to show results, errors, etc.
- `ResultsView` shows counts. Only accessible if `Question.show_results` is true or the template enforces visibility.
- `vote` view collects `request.POST.getlist('choice')`, resolves the current user to `members.Member` if authenticated, and delegates to `polls.vote.handle_vote()`.

## Validation Logic (`polls/vote.py`)
- `validate_vote()` enforces, in this order:
  - Poll not ended (`end_vote` flag).
  - At least one choice selected.
  - Single-choice poll doesn’t receive multiple picks.
  - If `required_multiple_choices` is set, exactly that many answers must be picked.
  - Choice ids are normalized to integers once before validation or writing. Numeric aliases for the same id (for example `1` and `+1`) are rejected, so they cannot satisfy `required_multiple_choices` while incrementing only one choice. Every normalized id must belong to the question (`selected_choices_belong_to_question()`), or a crafted submission could inflate another poll’s counter.
  - Authorization via `is_user_authorized_to_vote()` which checks membership type and subscription status when necessary.
  - Members can vote only once (unless `ANYONE`, in which case anonymous visitors can spam; design decision).
  - Presence at the attached meeting, when the poll has one (`voter_is_present()`). This check is deliberately last, so a voter the poll refuses on its own terms still hears that message rather than being told they are not in the room.
- After validation, `handle_selected_choices()` increments vote counters atomically (using `F()` expressions) and records the voter membership if authenticated. The update is filtered by `question` as well as by id, so the write path stays scoped to the question even if a caller ever reaches it without `validate_vote()` in front of it.
- `not_present` and `invalid_choice` are lazy gettext strings in `polls/vote.py`, with Swedish, English and Finnish catalog entries.

## Room-Only Polls (`attendance`)
A poll becomes room-only when an `attendance.AttendancePoll` row attaches it to an `attendance.AttendanceEvent`. `voter_is_present()` then allows a vote only when the newest `AttendanceChange` for that member at that event is an arrival, read through `AttendanceEvent.is_attendee_present()` with no timestamp so it means "right now". An anonymous voter is refused rather than matched, because there is no member to look up in the meeting’s changes. A question with no `AttendancePoll` row is an ordinary poll and keeps every rule above, which is the per-poll opt-in and also the behaviour on the associations that do not install `attendance`.

The model lives in `attendance`, not in `polls`, because every association installs `polls` while `date` alone installs `attendance` (`core/settings/date.py`). A field on `Question` pointing at `attendance.AttendanceEvent` would fail `manage.py check` on the other six associations, and neither `core/settings/test.py` (which inherits the `date` app set) nor `makemigrations --check` would notice. So `polls` reaches the link in the other direction: `attendance/models.py` declares `question` with the string target `'polls.Question'`, which creates the `Question.attendance_poll` accessor, and `polls/vote.py` reads it with `getattr(question, 'attendance_poll', None)` behind `apps.is_installed('attendance')`. `polls` imports nothing from `attendance` at module level, and on a site without the app the accessor does not exist and the `getattr` returns `None`.

The gate runs after the authorization and already-voted checks on purpose: a member who is merely not in the room must not displace the message that says the poll is not for them.

Presence is read from the newest change, so a member who checks in and never checks out is present for as long as that row says so: the meeting's own end time is not consulted, and `AttendanceEvent.has_ended` plays no part here. An attached poll therefore keeps accepting that member's vote after the meeting has ended, until an editor stops it with `end_vote` or the member checks out. Closing the poll is the control for that, and it is the one an editor already has.

## The poll page's presence prompt
The page and the vote check share one definition of the attachment. `attendance_requirement(question, user)` in `polls/vote.py` returns the meeting, whether the visitor is signed in and whether they are in the room, or `None` when the poll is ordinary, and `voter_is_present()` is a thin wrapper over it. `polls/views.py` puts that object in the `polls/detail.html` context, and `handle_vote()` puts it there too when it re-renders the page with a refusal, so the page and the POST cannot disagree about the room.

`templates/common/polls/detail.html` draws the prompt above the vote form, in the place the error message occupies, and it has three cases:

- A signed-in member who is not in the room reads the meeting's name and gets one button, "Ange koden och checka in", pointing at `{% raw %}{% url 'attendance-event-view' attendance_requirement.event.slug %}?next={% url 'polls:detail' question.id %}{% endraw %}`. The check-in page honours that `next` and returns the member to the poll (see `docs/dev/attendance.md`).
- A signed-in member the meeting counts as present reads "Du är närvarande på <meeting>." and gets no button.
- A visitor who is not signed in is sent to `{% raw %}{% url 'members:login' %}?next={% url 'polls:detail' question.id %}{% endraw %}` and is told that voting needs a signed-in member and presence. A guest cannot vote however many times they check in, because the meeting's changes are keyed on a member.

A poll with no attachment, and every poll on an association that does not install the app, renders exactly what it rendered before. The prompt sits inside `{% raw %}{% if attendance_requirement %}{% endraw %}`, so the block and the `{% raw %}{% url %}{% endraw %}` tags in it are never reached when the helper answers `None`.

The return path is built from the URL name rather than from `request.path`, because this template draws the prompt twice: on the GET that shows the poll, where the path is `/polls/<id>/`, and again when a refused vote re-renders it, where the path is the vote endpoint. A value taken from `request.path` would send a member who pressed "Rösta" first, and only then went to check in, back to `/polls/<id>/vote/`, which renders the poll again with a spurious "Du valde inget alternativ." message. Both links therefore name `polls:detail`, and a test pins it.

## Admin
- `QuestionAdmin` inline-stacks `Choice` and `Vote`. `VoteInline` disallows adding rows manually and limits deletion to superusers.
- Where `attendance` is installed, `AttendancePollInline` is added to the same page so an editor picks the meeting on the poll they are editing; see `docs/admin/polls.md` for what the editor sees. Its permissions follow `QuestionAdmin`: `polls.add_question` on the add page and `polls.change_question` on an existing poll. No AttendancePoll-specific or event-management permission is required. The poll list gets a `Närvaroevenemang` column behind the same flag, and `QuestionAdmin.get_queryset()` joins `attendance_poll__event` so the column costs one query rather than one per row. `question_list_display()` builds the column list from the flag, which is what keeps the changelist valid on an association without the app.
- The same block adds two read-only fields to the change page of an attached poll: **Närvarande i mötet nu**, the attached meeting's `AttendanceEvent.present_count()`, and **Har röstat**, the poll's `question.voters.count()`. `get_readonly_fields()` returns them only for a saved poll that has an `AttendancePoll` row, so an ordinary poll and the add page render exactly as before, and `get_fieldsets()` names them in the last section because a read-only field is only rendered from a fieldset. Neither is in `list_display`, so no changelist row pays a query for them. The headcount includes everyone counted in the room, while voters counts poll members; it is context, not an exact poll-time denominator.
- No slug fields; URLs use numeric primary keys.

## Extending
- Consider recording anonymous voters’ IP hash if abuse becomes a concern when `ANYONE` polls are used.
- Add an explicit `closes_at` if manual toggling of `end_vote` becomes error-prone (publication scheduling already lives on `published_time`).
- Results caching could be useful for high-traffic polls; currently every refresh hits the database and recalculates totals.
