# Polls Development Notes

## Models
- `Question` stores text, publish flags, multiple-choice settings, and `voting_options` (mapped to constants `ANYONE`, `MEMBERS_ONLY`, `ORDINARY_MEMBERS_ONLY`, `VOTE_MEMBERS_ONLY`). A `ManyToManyField` to `Member` via `Vote` tracks who voted.
- `Choice` belongs to a question and keeps an integer `votes` counter plus a helper `get_vote_percentage()`.
- `Vote` stores which `Member` voted on which `Question` at `voted_at` time (only used when the poll isn’t anonymous).

## Views & Flow
- `IndexView` lists the five most recent published questions.
- `DetailView` renders a single poll; template decides whether to show results, errors, etc.
- `ResultsView` shows counts. Only accessible if `Question.show_results` is true or the template enforces visibility.
- `vote` view collects `request.POST.getlist('choice')`, resolves the current user to `members.Member` if authenticated, and delegates to `polls.vote.handle_vote()`.

## Validation Logic (`polls/vote.py`)
- `validate_vote()` enforces:
  - Poll not ended (`end_vote` flag).
  - At least one choice selected.
  - Single-choice poll doesn’t receive multiple picks.
  - If `required_multiple_choices` is set, exactly that many answers must be picked.
  - Authorization via `is_user_authorized_to_vote()` which checks membership type and subscription status when necessary.
  - Members can vote only once (unless `ANYONE`, in which case anonymous visitors can spam; design decision).
- After validation, `handle_selected_choices()` increments vote counters atomically (using `F()` expressions) and records the voter membership if authenticated.

## Admin
- `QuestionAdmin` inline-stacks `Choice` and `Vote`. `VoteInline` disallows adding rows manually and limits deletion to superusers.
- No slug fields; URLs use numeric primary keys.

## Extending
- Consider recording anonymous voters’ IP hash if abuse becomes a concern when `ANYONE` polls are used.
- Add scheduling fields (`opens_at`, `closes_at`) if manual toggling of `published` and `end_vote` becomes error-prone.
- Results caching could be useful for high-traffic polls; currently every refresh hits the database and recalculates totals.
