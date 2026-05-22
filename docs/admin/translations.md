# Translation Editor Guide

## Purpose

Use this guide when updating multilingual site content through Django admin. It explains what translators and editors need to know about language tabs, translated fields, and language-aware links.

## When Translation Features Are Available

Multilingual editing is available only when `ENABLE_LANGUAGE_FEATURES=True` in the active environment.

When enabled:

- the public site can switch between the languages configured for the active association on the same unprefixed URLs
- the admin shows a language switcher
- supported models expose translated tabs or translated inline fields

For DaTe, the public runtime and translated admin languages are currently Swedish and English. Some other associations still expose Finnish as well. The database schema still keeps the full shared modeltranslation language set so translated columns remain stable.

When disabled:

- only Swedish is active
- the admin behaves like a single-language site

## Which Content Is Translated

Typical translated content in admin includes:

- event titles and event content
- news titles, category names, and article content
- poll questions and choices
- static-page navigation category names and dropdown-link titles

Some labels and proper names intentionally stay fixed across languages. Follow the wording rules in the main README and coordinate with the content owners when unsure.

## Editing Translated Content in Admin

1. Open the relevant model in `/admin`.
2. If language features are enabled, look for language tabs or grouped fields.
3. Treat Swedish as the source version unless the content team has explicitly decided otherwise.
4. Fill in the non-Swedish language fields only for content that should actually vary by language.
5. Save and preview the public page in at least one translated locale.

Common field patterns:

- `title` plus language-specific variants
- `content` plus language-specific variants
- category or navigation names translated per language

## Previewing the Result

After editing translated content:

1. Open the public page in Swedish.
2. Use the site language switcher to move to one of the other languages offered by the active association.
3. Confirm that:
   - the translated title/content appears
   - internal navigation still points to the same page in the selected language
   - untranslated proper names remain intentionally unchanged

The page URL normally stays unchanged while you switch languages. Confirm the visible copy changes even though the path remains the same.

## Navigation and Static Links

For Static Pages and navigation links:

- keep internal links as relative paths when possible, for example `/pages/foretagssamarbete/`
- absolute external links should stay absolute
- translated link labels can change by language, but the target path often stays the same logical page

If a stored internal link looks correct in Swedish but jumps back to the wrong language after switching locales, ask a developer to verify the `localized_url` handling.

## Good Translation Hygiene

- Keep shared UI labels consistent across the whole site.
- Avoid translating association names, branded labels, or special terms unless the project has explicitly chosen a translated version.
- Do not rename slugs casually after a page or article has been published, because older links may break.
- If only Swedish content is ready, it is better to leave other language fields intentionally blank than to add misleading filler text.

## When To Ask a Developer

Ask for developer help if:

- translated tabs do not appear in admin when you expect them to
- a field that should be translated only exists once
- changing the language switcher leads to the wrong page
- a page shows stale wording even after content was updated and saved
- the URL or slug structure needs to change
