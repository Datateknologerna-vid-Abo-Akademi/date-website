# Lucia Development Notes

## Models
- `Candidate` fields: `img_url`, `title`, `content` (CKEditor5), `published`, `slug`, and `poll_url`. Meta ordering is by `id`, so insertion order dictates listing. Verbose names are set to Swedish strings ("Lucia"/"Lucian").

## Views & URLs
- `lucia.views.index` and `lucia.views.candidates` both load `Candidate.objects.all()` and render different templates (`lucia/index.html`, `lucia/candidates.html`).
- `lucia.views.candidate` fetches a single published candidate by slug and renders `lucia/candidate.html`. Attempting to view an unpublished slug raises `DoesNotExist` and triggers a 500, so publish status doubles as public visibility control.

## Admin
- Default admin registration (`admin.site.register(Candidate)`) means there is no custom form logic. Slugs must be managed manually or via Django’s "slug" suggestions.

## Integrations
- Poll URLs often point to the internal Polls app (e.g., `/polls/<id>/`). There is no FK constraint, so keep links in sync manually.
- Templates typically embed `poll_url` in buttons, so ensure it includes the full scheme (`https://`).

## Extending the App
- To incorporate internal voting instead of external links, relate `Candidate` to a `polls.Question` and expose live vote counts.
- Add `ordering` or `display_order` fields if marketing requires manual sorting without re‑creating objects.
- If file uploads are preferred, switch `img_url` to `ImageField` and configure storage.
