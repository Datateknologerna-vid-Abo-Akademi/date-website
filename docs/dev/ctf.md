# CTF Development Notes

## Models
- `Ctf`: title/content, start/end dates, slug, and `published_time`. Methods `ctf_is_open()` and `ctf_ended()` wrap simple `now()` comparisons.
- Publication is controlled by `published_time` (same pattern as events/news): `NULL` is hidden, future is scheduled, past is public. Use `Ctf.objects.published()` or the `Ctf.published` property in views and templates.
- `Flag`: FK to `Ctf`, optional FK to `Member` (solver), plaintext `flag` string, optional `clues`, slug, and `solved_date`.
- `Guess`: records every submission with references to the CTF, flag, member, guessed string, correctness, and timestamp.

## Translations
- `ctf/translation.py` registers `Ctf.title` and `Ctf.content` with `django-modeltranslation`, so editors can maintain the CTF heading and description per language. `Flag.title` and `Flag.clues` stay single-language.
- The translated columns are `title_sv`/`title_en`/`title_fi` and `content_sv`/`content_en`/`content_fi`. They exist for every association because the shared schema keeps the full modeltranslation language set.
- `CtfAdmin` follows the `events` pattern: a language-tabbed change form plus a `translation_status` coverage column in the changelist (hidden when `ENABLE_LANGUAGE_FEATURES=False`).
- Rows created before the translated columns existed are copied into the Swedish columns by `ctf/migrations/0006_backfill_ctf_default_translations.py`. Without that backfill the public pages render an empty title and body, because the modeltranslation descriptor only reads the `*_<language>` columns.
- Public pages read the active language and fall back to Swedish when a translation is missing.

## Views & Flow
- `IndexView` (ListView) returns the five newest ctfs.
- `DetailView` adds all related flags to the context for display.
- `flag` view handles GET (render form + status) and POST (validate guess). Logic includes:
  - Session flags `flag_valid`/`flag_invalid` to show success/failure messages without duplicate posts.
  - Checks `ctf.ctf_is_open()`, the `ctf.published` property (time-based), and `request.user.is_authenticated` before processing submissions.
  - Iterates through `ctf_flags` to mark `user_solved` once any flag has a solver that matches the user.
  - On correct guess: if the flag already has a solver or the user solved another flag, the guess is marked `correct=True` but doesn’t overwrite the solver. Otherwise, the solver + timestamp are saved, a success message is queued, and the user is redirected.
  - Incorrect guesses still create `Guess` records (unless the flag lookup fails, in which case an error is logged).

## Forms
- `FlagForm` contains a single `CharField` named `flag`. Optional initialization can disable the field (unused currently but ready for dynamic behavior).

## Admin
- `FlagInline` sits inside `CtfAdmin`, excluding `solved_date` so staff can’t set it manually.
- `solver` is an autocomplete field (also on the standalone `FlagAdmin`). It is normally filled automatically when a member solves the flag, but staff can set or clear it by hand. The member dropdown works for CTF editors without `members.view_member` thanks to `core.admin.ReferringObjectAutocompleteJsonView`; see `docs/dev/members.md`.
- `GuessAdmin` exposes filtering/search across guesses for auditing. The full guess list is available through an **All guesses** tool link on the CTF changelist rather than a separate sidebar entry.

## Extending
- Add rate limiting to `flag` view to prevent brute force.
- Hash stored flags if leaking plaintext secrets in the DB is a concern (would require custom comparison logic).
- Surface scoreboard data by aggregating `Flag` and `Guess` models to show who solved what and when.
