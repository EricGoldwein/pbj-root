# PBJpedia launch checklist

PBJpedia is a draft reference wiki (markdown in `PBJPedia/`). **It is not public by default.** Production serves **404** for all `/pbjpedia/*` routes unless you explicitly opt in.

## Local preview (while drafting)

```bash
# Windows PowerShell
$env:PBJPEDIA_PUBLIC = "1"
python app.py

# macOS/Linux
export PBJPEDIA_PUBLIC=1
python app.py
```

Then open e.g. `http://127.0.0.1:5000/pbjpedia/overview`.

Unset `PBJPEDIA_PUBLIC` before testing “production-like” behavior (404 everywhere).

## What is gated today

| Surface | Behavior when not public |
|--------|---------------------------|
| `/pbjpedia`, `/pbjpedia/*` | HTTP **404** (no redirect leak) |
| `/pbjpedia/state/*`, `/pbjpedia/region/*` | **404** |
| `sitemap.xml` | No `/pbjpedia/` URLs (`SITEMAP_EXCLUDED_PATHS` + forbidden fragment) |
| `robots.txt` | `Disallow: /pbjpedia/` |
| `llms.txt` | Notes `/pbjpedia/` is not for crawling |
| Explainer pages (`/what-is-hprd`, etc.) | Link to **public** guides only (no PBJpedia) |

Markdown under `PBJPedia/` may still use `/pbjpedia/...` links for authoring; those pages are unreachable until launch.

## Pre-launch audit

After deploy (or against staging with **no** `PBJPEDIA_PUBLIC`):

```bash
python scripts/audit_indexability.py --base-url https://www.pbj320.com
```

Confirm the report includes **pbjpedia gated** checks (404 on sample URLs, no sitemap entries, robots disallow).

## Launch steps (when ready)

1. **Content** — Finish pages; keep `history` unpublished until reviewed (leave out of `page_map` in `app.py` or ship later).
2. **Cross-links** — Restore PBJpedia links on explainer pages in `utils/seo_utils.py` and any “See also” blocks you want.
3. **Sitemap** — Add published slugs to `static_pages` in `app.py` (start with `overview`, `metrics`, `methodology`, `state-standards`; add others as ready).
4. **Robots** — Keep `Disallow: /pbjpedia/history` if history stays draft; otherwise rely on `/pbjpedia/` allow + page-level quality.
5. **Enable routes** — Set `PBJPEDIA_PUBLIC=1` in production env (Render/host env vars), redeploy.
6. **Verify** — Re-run `audit_indexability.py`; spot-check canonicals, contact CTA, sample dashboard link.
7. **Optional** — Submit updated sitemap in Search Console; monitor Coverage for soft-404s.

## Best practices when public

- **One flag** — `PBJPEDIA_PUBLIC` is the single switch; do not serve pages via a hidden URL without updating robots/sitemap.
- **404 vs noindex** — Pre-launch uses **404** so URLs are not indexed as thin “noindex” stubs. After launch, indexable pages should return **200** with real titles/descriptions.
- **Sitemap parity** — Only list URLs that return 200 and match `robots.txt` (no disallowed paths in sitemap).
- **Internal links** — Prefer explainer pages for SEO entry points; use PBJpedia for depth (metrics tables, MACPAC table, job codes).
- **History / draft pages** — Keep off sitemap and out of `page_map` until ready; use `SITEMAP_EXCLUDED_PATHS` for one-off paths.

## Source files

| Item | Location |
|------|----------|
| Public gate | `site_public_config.pbjpedia_is_public()`, `app._require_pbjpedia_public()` |
| Markdown | `PBJPedia/pbjpedia-*.md` |
| Routes | `app.py` — `pbjpedia_index`, `pbjpedia_page`, `pbjpedia_state_page`, `pbjpedia_region_page` |
| SEO policy | `site_public_config.py` — `ROBOTS_TXT`, `SITEMAP_*` |
