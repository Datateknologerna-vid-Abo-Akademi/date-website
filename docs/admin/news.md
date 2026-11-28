# News Admin Guide

## Purpose
Publish and organize news articles that appear on the home page and `/news/` listing.

## Categories
1. Visit **News › Categories** to add or rename sections (e.g., "Albins Angels").
2. Fields:
   - **Namn** – public label.
   - **Slug** – used in `/news/<slug>/` category URLs. It fills in from the name while you create the category; keep it lowercase and unique. Renaming a category does not change the slug of an existing one.

## Create a News Post
1. Open **News › Posts**.
2. Click **Add post**.
3. Complete the form:
   - **Titel** – headline. If translation features are enabled, fill the translated title/content tabs as needed.
   - **Glanseffekt på titeln** – tick to show the headline with the gold shine on the home page, in the `/news/` list and on the article page. Leave it unticked for ordinary posts, because the effect only stands out when few posts use it. The checkbox only appears on sites whose styles support it (currently DaTe).
   - **Kategori** – optional; un-categorized posts show on the home page by default.
   - **Innehåll** – CKEditor field for body text, images, embeds.
   - **Publiceras** – set the date and time when the post should become visible. Leave empty to keep it hidden as a draft; pick a future time to schedule publication.
   - **Slug** – fills in from the title while you create the post. Keep it short and readable; leave it as suggested unless you need a specific URL. The suggestion is not applied when editing an existing post, so its public URL stays stable.
4. Save to publish (or schedule). `Skapad`, `Publiceras`, and `Modifierad` timestamps update automatically.

## Editing Existing Posts
- Use the changelist filters (by author/date) to find posts.
- Click a row, adjust content, and save. The `Modifierad` timestamp updates so you can track revisions.

## Front-End Behavior
- `/news/` shows a paginated feed (10 posts per page) of published, un-categorized posts sorted by most recent.
- `/news/<category>/` limits the feed to that category (e.g., `/news/albins-angels/`).
- `/news/articles/<slug>/` renders an uncategorized post. Categorized posts must be opened via `/news/<category>/<slug>/`. Changing the slug later will break whichever URL applies, so avoid edits once a link has been shared.

## Tips
- For Albins Angels highlights, set the category to "Albins Angels"; the home page automatically surfaces the newest post from that category if it’s < 10 days old.
- Use descriptive slugs (e.g., `styrelseval-2024`) to keep permalinks readable.
- Add the author info in the body if needed; the template already shows the Member assigned in the admin form.
- If multilingual content is enabled, preview the post in Swedish and at least one translated locale after saving.
