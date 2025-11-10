# CTF Development Notes

## Models
- `Ctf`: title/content, start/end dates, slug, and published flag. Methods `ctf_is_open()` and `ctf_ended()` wrap simple `now()` comparisons.
- `Flag`: FK to `Ctf`, optional FK to `Member` (solver), plaintext `flag` string, optional `clues`, slug, and `solved_date`.
- `Guess`: records every submission with references to the CTF, flag, member, guessed string, correctness, and timestamp.

## Views & Flow
- `IndexView` (ListView) returns the five newest ctfs.
- `DetailView` adds all related flags to the context for display.
- `flag` view handles GET (render form + status) and POST (validate guess). Logic includes:
  - Session flags `flag_valid`/`flag_invalid` to show success/failure messages without duplicate posts.
  - Checks `ctf.ctf_is_open()`, `ctf.published`, and `request.user.is_authenticated` before processing submissions.
  - Iterates through `ctf_flags` to mark `user_solved` once any flag has a solver that matches the user.
  - On correct guess: if the flag already has a solver or the user solved another flag, the guess is marked `correct=True` but doesn’t overwrite the solver. Otherwise, the solver + timestamp are saved, a success message is queued, and the user is redirected.
  - Incorrect guesses still create `Guess` records (unless the flag lookup fails, in which case an error is logged).

## Forms
- `FlagForm` contains a single `CharField` named `flag`. Optional initialization can disable the field (unused currently but ready for dynamic behavior).

## Admin
- `FlagInline` sits inside `CtfAdmin`, excluding `solved_date` so staff can’t set it manually.
- `GuessAdmin` exposes filtering/search across guesses for auditing.

## Extending
- Add rate limiting to `flag` view to prevent brute force.
- Hash stored flags if leaking plaintext secrets in the DB is a concern (would require custom comparison logic).
- Surface scoreboard data by aggregating `Flag` and `Guess` models to show who solved what and when.
