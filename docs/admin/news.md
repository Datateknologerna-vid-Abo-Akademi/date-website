# News Admin Guide

## Purpose
Publish and organize news articles that appear on the home page and `/news/` listing.

## Categories
1. Visit **News › Categories** to add or rename sections (e.g., "Albins Angels").
2. Fields:
   - **Namn** – public label.
   - **Slug** – used in `/news/<slug>/` category URLs. Keep lowercase and unique.

## Create a News Post
1. Open **News › Posts**.
2. Click **Add post**.
3. Complete the form:
   - **Titel** – headline.
   - **Kategori** – optional; un-categorized posts show on the home page by default.
   - **Innehåll** – CKEditor field for body text, images, embeds.
   - **Publicera** – uncheck to keep as draft.
   - **Slug** – type a short identifier; auto-suggest isn’t enabled, so copy a clean version of the title.
4. Save to publish immediately. `Skapad`, `Publicerad`, and `Modifierad` timestamps update automatically.

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
