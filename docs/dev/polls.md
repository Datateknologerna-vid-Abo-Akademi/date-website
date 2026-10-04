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
  - Every posted choice id belongs to the question (`selected_choices_belong_to_question()`). The ids come straight from the POST, so without this check a crafted submission could name another poll’s choices and inflate that poll’s counters.
  - Authorization via `is_user_authorized_to_vote()` which checks membership type and subscription status when necessary.
  - Members can vote only once (unless `ANYONE`, in which case anonymous visitors can spam; design decision).
  - Presence at the attached meeting, when the poll has one (`voter_is_present()`). This check is deliberately last, so a voter the poll refuses on its own terms still hears that message rather than being told they are not in the room.
- After validation, `handle_selected_choices()` increments vote counters atomically (using `F()` expressions) and records the voter membership if authenticated. The update is filtered by `question` as well as by id, so the write path stays scoped to the question even if a caller ever reaches it without `validate_vote()` in front of it.

## Room-Only Polls (`attendance`)
A poll becomes room-only when an `attendance.AttendancePoll` row attaches it to an `attendance.AttendanceEvent`. `voter_is_present()` then allows a vote only when the newest `AttendanceChange` for that member at that event is an arrival, read through `AttendanceEvent.is_attendee_present()` with no timestamp so it means "right now". An anonymous voter is refused rather than matched, because there is no member to look up in the meeting’s changes. A question with no `AttendancePoll` row is an ordinary poll and keeps every rule above, which is the per-poll opt-in and also the behaviour on the associations that do not install `attendance`.

The model lives in `attendance`, not in `polls`, because every association installs `polls` while `date` alone installs `attendance` (`core/settings/date.py`). A field on `Question` pointing at `attendance.AttendanceEvent` would fail `manage.py check` on the other six associations, and neither `core/settings/test.py` (which inherits the `date` app set) nor `makemigrations --check` would notice. So `polls` reaches the link in the other direction: `attendance/models.py` declares `question` with the string target `'polls.Question'`, which creates the `Question.attendance_poll` accessor, and `polls/vote.py` reads it with `getattr(question, 'attendance_poll', None)` behind `apps.is_installed('attendance')`. `polls` imports nothing from `attendance` at module level, and on a site without the app the accessor does not exist and the `getattr` returns `None`.

The gate runs after the authorization and already-voted checks on purpose: a member who is merely not in the room must not displace the message that says the poll is not for them.

Presence is read from the newest change, so a member who checks in and never checks out is present for as long as that row says so: the meeting's own end time is not consulted, and `AttendanceEvent.has_ended` plays no part here. An attached poll therefore keeps accepting that member's vote after the meeting has ended, until an editor stops it with `end_vote` or the member checks out. Closing the poll is the control for that, and it is the one an editor already has.

## Admin
- `QuestionAdmin` inline-stacks `Choice` and `Vote`. `VoteInline` disallows adding rows manually and limits deletion to superusers.
- Where `attendance` is installed, `AttendancePollInline` is added to the same page so an editor picks the meeting on the poll they are editing; see `docs/admin/polls.md` for what the editor sees. The poll list gets a `Närvaroevenemang` column behind the same flag, and `QuestionAdmin.get_queryset()` joins `attendance_poll__event` so the column costs one query rather than one per row. `question_list_display()` builds the column list from the flag, which is what keeps the changelist valid on an association without the app.
- No slug fields; URLs use numeric primary keys.

## Extending
- Consider recording anonymous voters’ IP hash if abuse becomes a concern when `ANYONE` polls are used.
- Add an explicit `closes_at` if manual toggling of `end_vote` becomes error-prone (publication scheduling already lives on `published_time`).
- Results caching could be useful for high-traffic polls; currently every refresh hits the database and recalculates totals.
