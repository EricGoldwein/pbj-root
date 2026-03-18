# Adding non-Substack articles to the newsletter page

The newsletter page shows **Substack posts** (from The 320 feed) plus **manual posts** from `newsletter_posts.json`. Use the JSON file to add any other article (external site, PDF, your own blog, etc.).

## File

**`newsletter_posts.json`** (project root) — array of objects.

## Format

| Field         | Required | Description |
|---------------|----------|-------------|
| `title`       | Yes      | Article title. |
| `url`         | Yes      | Full URL (any site). |
| `description` | No       | Short preview or pull quote (plain text). Shown under the title. |
| `date`        | No       | Publication date. Use `YYYY-MM-DD` (e.g. `2026-03-01`) or a full date string. Used for sorting (newest first). |
| `image_url`   | No       | Featured image URL. Shown as the card image when present. |

## Example

```json
[
  {
    "title": "How nursing home staffing rules are changing in 2026",
    "url": "https://example.com/article",
    "description": "A short preview or pull quote that appears under the title.",
    "date": "2026-03-01",
    "image_url": "https://example.com/og-image.jpg"
  }
]
```

Manual posts appear in the same list as Substack posts, sorted by date (newest first). They show an “Added by PBJ320” badge and the link text is “Read article” instead of “Read on The 320”.  
The feed is cached for 10 minutes; new or edited entries in `newsletter_posts.json` show up after the cache refreshes or on the next deploy.
