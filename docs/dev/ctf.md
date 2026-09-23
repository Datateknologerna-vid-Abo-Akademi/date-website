# CTF Development Notes

## Models
- `Ctf`: title/content, start/end dates, slug, and `published_time`. Methods `ctf_is_open()` and `ctf_ended()` wrap simple `now()` comparisons.
- Publication is controlled by `published_time` (same pattern as events/news): `NULL` is hidden, future is scheduled, past is public. Use `Ctf.objects.published()` or the `Ctf.published` property in views and templates.
- `Flag`: FK to `Ctf`, optional FK to `Member` (solver), plaintext `flag` string, optional `clues`, optional `solution` narrative, slug, and `solved_date`.
- `Guess`: records every submission with references to the CTF, flag, member, guessed string, correctness, and timestamp.
- `PostMortem`: one-to-one to `Ctf` with `related_name='post_mortem'`, plus `overview` (rich text) and `published_time`. `published_time` defaults to `NULL`, so a new post-mortem is hidden until an editor publishes it; a future timestamp schedules it. `published` reports that the timestamp is set and in the past, and `is_visible` additionally requires `ctf.ctf_ended()`. `PostMortemQuerySet` mirrors both with `published()` and `visible()`.
- Translation: `Ctf.title` and `Ctf.content` are registered with `django-modeltranslation` (see below). `Flag.title`, `Flag.clues`, `Flag.solution` and `PostMortem.overview` deliberately stay monolingual, so registering them later needs the language columns plus a backfill.

## Translations
- `ctf/translation.py` registers `Ctf.title` and `Ctf.content` with `django-modeltranslation`, so editors can maintain the CTF heading and description per language. `Flag.title`, `Flag.clues`, `Flag.solution` and `PostMortem.overview` stay single-language.
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
- `PostMortemIndexView` (ListView) lists `PostMortem.objects.visible()` with the newest CTF first.
- `PostMortemDetailView` (DetailView) resolves the post-mortem by `ctf__slug` through the same visible queryset with `get_object_or_404`.
- Reading a post-mortem has three conditions: the visitor is logged in (`login_required`, exactly like every other CTF route), the CTF has ended (`Ctf.ctf_ended()`), and the post-mortem is published. A logged-in member who is not yet allowed gets a bare 404, with no placeholder page and no hint that the content exists.
- The detail context builds the per-challenge input counts with a single aggregate query (`Guess.objects.filter(ctf=ctf, flag__ctf=ctf).values('flag_id').annotate(inputs=Count('id'))`). The `flag__ctf=ctf` filter drops rows that point at this CTF but at a flag from another one, which `GuessAdmin` can create. `total_guesses` is the sum of the per-challenge inputs actually rendered, so the printed numbers always add up by construction. “Number of inputs” counts every recorded guess for a challenge, correct and incorrect. Challenges are ordered by `pk`, the only stable creation-order signal `Flag` offers.
- The solve duration reuses the flag page convention, `{{ flag.solved_date|timeuntil:ctf.start_date }}`, and is skipped when a flag has a solver but no `solved_date` (for example an admin-credited solve).

## Forms
- `FlagForm` contains a single `CharField` named `flag`. Optional initialization can disable the field (unused currently but ready for dynamic behavior).

## Admin
- `FlagInline` sits inside `CtfAdmin`, excluding `solved_date` so staff can’t set it manually. `Flag.solution` appears there automatically because the inline declares no `fields`.
- `solver` is an autocomplete field (also on the standalone `FlagAdmin`). It is normally filled automatically when a member solves the flag, but staff can set or clear it by hand. The member dropdown works for CTF editors without `members.view_member` thanks to `core.admin.ReferringObjectAutocompleteJsonView`; see `docs/dev/members.md`.
- `GuessAdmin` exposes filtering/search across guesses for auditing. The full guess list is available through an **All guesses** tool link on the CTF changelist rather than a separate sidebar entry.
- `PostMortemAdmin` admits two kinds of staff. The first is anyone holding one of `CTF_EDITOR_PERMISSIONS` (`ctf.add_ctf`, `ctf.change_ctf`, `ctf.add_flag`, `ctf.change_flag`): creating a model grants brand-new `ctf.add_postmortem` / `ctf.change_postmortem` / `ctf.delete_postmortem` / `ctf.view_postmortem` permissions that no group holds, so the Django defaults alone would leave nobody able to author a post-mortem. The second is anyone explicitly granted a post-mortem model permission: `has_module_permission`, `has_view_permission`, `has_add_permission`, `has_change_permission` and `has_delete_permission` each OR `super()`, so `ctf.view_postmortem` alone gives read-only access and `ctf.add_postmortem` / `ctf.change_postmortem` / `ctf.delete_postmortem` give the matching write ability. The `super()` fallback is deliberate and stays: granting `ctf.change_postmortem` the ability to change post-mortems is what that permission name means, and it cannot escalate beyond the post-mortem model because it grants nothing on `Ctf`, `Flag` or `Guess`. `PostMortemAdminAccessTests` pins both directions. No group or permission data migration is needed.
- The CTF changelist carries a **Post-mortems** tool link and the admin sidebar a **CTF Post-mortems** entry, both behind those same CTF content permissions.
- `CtfPublicationFilter` is shared between `CtfAdmin` and `PostMortemAdmin`: it filters on `published_time` on whichever model it is attached to.

## Post-mortems
- URLs: `ctf:post_mortem_index` at `/ctf/post-mortem` and `ctf:post_mortem_detail` at `/ctf/post-mortem/<ctf_slug>`. Both omit the trailing slash, matching `ctf:detail` and `ctf:flag_detail`, and both sit behind `login_required`.
- Route order is load-bearing: `post-mortem` is itself a valid `<slug:slug>`, so the literal patterns must stay above the `<slug:...>` patterns in `ctf/urls.py` or they can never match.
- Accepted consequence: a CTF whose slug is literally `post-mortem` is unreachable at `ctf:detail`. `PostMortemVisibilityTests.test_literal_post_mortem_route_wins_over_post_mortem_slug` documents this.
- The page shows authored overview prose, a data block (total guesses plus per-challenge input counts), and one block per challenge with the title, clue, optional `[SOLVED]` marker, solver username, solve duration, flag string and editor-written solution. Wrong-guess text and other members’ usernames are never exposed.

## Extending
- Add rate limiting to `flag` view to prevent brute force.
- Hash stored flags if leaking plaintext secrets in the DB is a concern (would require custom comparison logic).
- Per-challenge guess counts are now published through the post-mortem page. Per-member scoreboards (who solved what and when) remain future work, and must not expose other members’ wrong guesses.
