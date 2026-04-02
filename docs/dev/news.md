# News Development Notes

## Models
- `Category`: name + slug with default alphabetical ordering.
- `Post`: title, optional category, CKEditor content, FK to `members.Member` as author, timestamps (`created_time`, `published_time`, `modified_time`), boolean `published`, and slug (max 50 chars). Methods `publish()`, `unpublish()`, `update()` manage timestamps.

## Forms
- `PostCreationForm` and `PostEditForm` both attach `request.user` to set the `author` (creation) or just update metadata (edit). Creation form slugifies with `slugify_max` and timestamps `published_time` at save.

## Admin
- `PostAdmin` swaps between the two forms in `add_view` vs `change_view`. Columns show author, category, created/modified times, and publish status. Categories get their own simple `ModelAdmin`.

## Views
- `index`: paginates 10 latest un-categorized, published posts (reverse order).
- `article`: fetches a published, un-categorized post by slug.
- `author`: lists all published posts tied to a specific username.
- `category_index` & `category_article`: same as above but filter by `Category.slug`.

## Feed/SEO
- There’s also `news/feed.py` (not covered here) generating RSS/Atom feeds; ensure `Post` timestamps stay accurate for feed readers.

## Extending
- Add `summary` or `hero_image` fields if marketing wants richer cards on the homepage.
- Introduce scheduled publishing by adding `publish_at` and a management command or background job to flip `published` when the time arrives.
- Consider `prepopulated_fields = {"slug": ("title",)}` in admin to reduce manual slug errors.
