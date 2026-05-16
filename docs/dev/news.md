# News Development Notes

## Models
- `Category`: name + slug with default alphabetical ordering.
- `Post`: title, optional category, CKEditor content, FK to `members.Member` as author, timestamps (`created_time`, `published_time`, `modified_time`), and slug (max 50 chars). Methods `publish()`, `unpublish()`, `update()` manage timestamps.
- Publication is controlled by `published_time`: `NULL` means hidden, a future timestamp means scheduled, and a past timestamp means public. Use `Post.objects.published()` for public-facing post lists and detail lookups. The `Post.published` property reflects the same time-based check.

## Forms
- `PostCreationForm` and `PostEditForm` both attach `request.user` to set the `author` (creation) or just update metadata (edit). Creation form slugifies with `slugify_max`; `published_time` is editable in the form (defaults to "now" so saving immediately makes the post public).

## Admin
- `PostAdmin` swaps between the two forms in `add_view` vs `change_view`. Columns show author, category, created/modified times, computed publication status, and the raw `published_time`. The `publication` list filter splits posts into published / scheduled / hidden buckets. Categories get their own simple `ModelAdmin`.

## Views
- `index`: paginates 10 latest un-categorized, published posts (reverse order).
- `article`: fetches a published, un-categorized post by slug.
- `author`: lists all published posts tied to a specific username.
- `category_index` & `category_article`: same as above but filter by `Category.slug`.

## Feed/SEO
- There’s also `news/feed.py` (not covered here) generating RSS/Atom feeds; ensure `Post` timestamps stay accurate for feed readers.

## Extending
- Add `summary` or `hero_image` fields if marketing wants richer cards on the homepage.
- Consider `prepopulated_fields = {"slug": ("title",)}` in admin to reduce manual slug errors.
