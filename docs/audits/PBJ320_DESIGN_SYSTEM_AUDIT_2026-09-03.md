# PBJ320 vNext Interface / Design-System Audit

**Date:** 2026-09-03
**Branch:** `audit/pbj320-design-system-20260903` (worktree, starting SHA `218c468`)
**Type:** Audit only. No runtime code, CSS, templates, JS, data, or configuration was modified as part of producing this document. `scripts/ensure_deploy_csvs.py --quick` was run once, per the documented local-dev workflow in `docs/DATA_DEPLOY.md`, to materialize gitignored derived data files so provider/state/entity pages could be browser-verified; this wrote only files already excluded from git (`facility_quarterly_metrics.csv`, `data/state_page_aggregates.json.gz`, ownership sqlite indexes) and changed no tracked file.
**Method:** Direct code reading (routes, generator functions, CSS/JS assets) + 10 parallel read-only research passes over specific subsystems + live browser verification (desktop 1440×900, mobile 390×844) against a local server on port 10000, with production (`pbj320.com`) used as a reference where local rendering was blocked. Every claim below is grounded in a `file:line` citation or a screenshot/DOM check; nothing here is inferred from the Figma reference alone.

---

## How to read this document

Section 1 is the diagnosis in plain language. Sections 2–14 describe the *system* (architecture, styling, tokens, tables, charts, overlays, icons, provenance) as it exists today. Sections 15–23 walk the *surfaces* (homepage, provider, state, ownership, report/SFF, insights, premium, mobile, future states) with concrete findings. Sections 24–32 are the actionable output: migration strategy, risk list, do-not-break list, Phase 1 proposal, and open decisions for Eric.

Throughout, "research file NN" refers to `_scratch/audit_research/NN_*.md` — the raw evidence backing each synthesized claim, kept under `_scratch/` per `AGENTS.md`'s scratch-only rule and not part of this deliverable.

---

## 1. Executive diagnosis

The brief's framing — *preserve the product logic, consolidate the interface system* — is the right call, and the evidence supports it more strongly than expected. PBJ320's actual problem is not that the product concept is unclear or that individual pages are badly designed. Providers, states, entities, and owners each render through a genuinely well-built page-generator function with a real, actively-shared metric primitive (`.pbj-metric` / `render_page_metric_html`, research file 02 §5) and a strong, product-differentiating "PBJ Takeaway" pattern that already works. The problem is exactly what the brief names: **visual and component drift accumulated across a single 28,200-line Flask app (`app.py`) that grew page-by-page over time, plus several surfaces that were built as genuinely separate applications and were never brought back into the shared system.**

Concretely, five things are true at once:

1. **The "connected system" model (Provider ↔ Chain ↔ State ↔ Owner) is real in the data and mostly real in the UI, with one clean break.** Provider, State, and Owner pages cross-link to each other correctly. The **Entity/Chain page is ownership-blind by design** — `render_entity_ownership_tools_block()` is a one-line stub that returns `""` (`ownership/page_integrations.py:906-907`), and `portfolio_display.py` contains zero `href=` in the entire file. A chain page cannot get a user to that chain's owner or its CHOW history, even though provider pages beneath it and state pages above it both can (research file 03 §5-6). This is the single clearest structural gap relative to the product thesis in Section 2 of the brief.

2. **Several major surfaces are not "the PBJ320 interface" at all — they are separate applications wearing the same nav bar.** SFF (`/sff*`) is a fully isolated React + Vite + TypeScript + Tailwind single-page app living in `pbj-wrapped/`, with its own hand-copied nav CSS whose own code comment admits the duplication risk (`pbj-wrapped/src/index.css:5-58`, *"Navbar: matches index.html + pbj-site-universal.js shell"*). `/report` is a static 8,400-line HTML file with a ~4,800-line inline stylesheet and its own D3-based charting stack pulled from a CDN that nothing else in the app uses (research file 04 §1, §6). Premium is not one system at all but **at least four unreconciled visual languages** — a Bootstrap 5 marketing hub, a dark slate/indigo dashboard template (whose Flask route registration is dead code — never called from `app.py`), a Calibri/Flat-UI-blue print-styled sample report, and a fifth ad hoc demo file (research file 09). PBJPedia (pre-launch, gated behind `PBJPEDIA_PUBLIC=1`) deliberately clones the MediaWiki/Wikipedia skin and shares zero visual DNA with PBJ320 (research file 04 §5).

3. **Where the app *is* one system (provider/state/entity/owner, generated inline in `app.py`), the drift is real but mostly at the edges, not the core.** The primary metric card pattern is genuinely shared. The flags/badges vocabulary for the *same* semantic set (SFF, SFF Candidate, Abuse, 1-star overall, 1-star staffing) is independently implemented three times with different colors, class conventions, and label text (research file 02 §4). Four near-identical hand-written info-modal shells exist where one parameterized component would do (research file 02 §6). The site's nav bar itself is hand-duplicated across at least four separate blocks in `app.py`, one of which is missing the "Owners" link entirely (research file 03 §5-6).

4. **A real design-token layer already partially exists — in six different, non-communicating namespaces.** `--pbj-ov-*` (app.py, one small component), `--chow-*`, `--pbj-*`/`--insights-*` (Insights, by far the most complete token set), `--ai-*`, `--ui-*`/`--pbj-premium-*` (Premium). No shared root layer connects them. The "brand accent" color alone is independently reinvented as five different hex values across five files (research file 08 §C1-C2). DM Sans, DM Mono, and Vollkorn — the exact typefaces named in the brief's brand direction — are **already self-hosted in the repo** (`/static/brand/fonts/*.ttf`) and wired via `@font-face`, but confined to Insights articles and the standalone `/state-standards` page; the rest of the app uses a plain system-font stack (research file 08 §C3). This changes the nature of the token-layer work from "invent tokens" to "generalize tokens that already exist and already match the brand direction."

5. **A meaningful amount of what looks like drift is actually dead code, not competing live patterns.** A ~58-line dead badge-vocabulary block sits unused inside `generate_provider_page_html` (`app.py:18099-18156`). A fully-built progressive-disclosure "About this data" dialog — Python renderer, CSS, and a live JS click-delegation handler — exists end-to-end but is never triggered by any page (`pbj_page_sources.py:27-49`, research file 08 §A1). The homepage silently fetches four JSON files on every pageview for a chart whose DOM target no longer exists (`index.html:3001-3183`, research file 01 §1.6). `index-render.html`, two orphaned Phoebe PNGs (~4.1MB), and a legacy `.pbj-metric-card` CSS family with zero markup usage are all pure removal candidates, not consolidation targets. This matters for scoping: some of the "drift" the brief worries about can be deleted outright rather than unified.

**The right frame for the redesign, given this evidence:** this is not a ground-up rebuild and not primarily a token-and-palette exercise. It is (a) a small set of shared primitives — metric card, flag badge, modal shell, table grammar, chart grammar — extracted from the code that already does 80% of the job correctly on provider/state/entity/owner pages, (b) a token layer that generalizes the Insights `--pbj-*` system (already the most complete) and the already-present DM Sans/DM Mono/Vollkorn fonts outward to the rest of the app, and (c) a deliberate, separately-scoped decision about what to do with SFF, `/report`, and Premium, which are integration problems (three different tech stacks) rather than styling problems that a shared CSS pass can fix.

---

## 2. Product / surface architecture

### 2.1 What the brief asks

Section 2 of the brief states the product model: PBJ320 is one connected nursing-home data system, with Provider as the primary entry path, and Provider ↔ Chain ↔ State ↔ Owner/control-party as one graph, not separate "modes." National rankings, SFF, CHOW, state comparisons, and ownership lists are comparative views across those same objects. Insights/PBJPedia/methodology explain the same system. Premium is an advanced workspace over the same product.

### 2.2 What the code actually supports

**The graph is real in the data model and mostly real in cross-linking** (full matrix in research file 03 §5):

| Link | Status |
|---|---|
| Provider → State | ✅ live |
| Provider → Entity/Chain | ✅ live |
| Provider → Owner | ✅ live (per-party links in the CHOW/ownership accordion) |
| Provider → CHOW | ✅ live (same accordion) |
| State → Provider | ✅ live (high-risk table, staffing table) |
| State → Owner | ✅ live (Explore-hub "owners"/"chow" tabs) |
| Entity/Chain → State | ✅ live (per-facility state cell) |
| Entity/Chain → Provider | ✅ live (per-facility provider cell) |
| **Entity/Chain → Owner** | ❌ **stub returns `""`** (`ownership/page_integrations.py:906-907`) |
| **Entity/Chain → CHOW** | ❌ **no code path at all** in `generate_entity_page_html` |
| **State → Entity/Chain** | ❌ **no direct link** — user must detour through a provider page |
| **Owner → State** | ❌ **no link** — only `/owners` or `/owners/<state-slug>` back-links; state breakdown renders as plain text |
| **Owner → Entity/Chain** | ❌ **none found** |
| Global nav → Owners | ⚠️ present in 3 of 4 hand-duplicated nav blocks; missing from the Insights-article nav block (`app.py:4426-4431`) |

So the graph the brief describes is **three-quarters built**. Provider is correctly the hub. State and Owner talk to each other. The break is specifically the **Entity/Chain node**, which is wired to Provider and State but not to Owner, and the **State↔Chain edge**, which doesn't exist at all. This is a precise, scoped gap — not evidence that the whole model needs rethinking, and not something a visual redesign alone fixes (it needs one new link on the entity page and one on the state page — implementation, not audited here per the AUDIT ONLY constraint, but flagged as a design decision in §26).

**A related structural finding**: a dead cross-link placeholder sits on every state page — `_state_ownership_index_cross_link = ''` (`app.py:24173`), interpolated into every render but never assigned a non-empty value anywhere. It reads as a scaffolded slot for exactly this kind of connective link that was started and abandoned.

**"Ownership has a specialized explorer" — confirmed, and it is more separate than the brief's framing implies.** Owner profile pages are correctly server-rendered HTML using the same `get_pbj_site_layout()` shell as everything else — not a separate SPA (research file 03 §3) — so architecturally it *is* the same product. But `ownership/` is the **only part of the product with a real external CSS/JS asset pipeline** (`owner-profile.css` at 6,838 lines, `chow.css` at 2,164 lines, three JS files) and its own scoped token system (`--owner-*`, not `--pbj-*`, `ownership/owner-profile.css:3-8`). Two different UI patterns represent the identical "ownership context on this page" concept: a tabbed Explore-hub widget on state pages vs. a `<details>` accordion on provider pages (research file 03 §4).

**Comparative views (rankings, SFF, state comparisons) are real conceptually but are architecturally three different products**, not three views of one system — see §3 and §19.

**Insights/PBJPedia/methodology as "explanation around the same system"**: PBJPedia is pre-launch (gated behind `PBJPEDIA_PUBLIC=1`, `app.py:24652-24656`) and deliberately skins itself as MediaWiki, sharing zero visual DNA with PBJ320. Insights has its own self-consistent `--pbj-*` token system (the best-built one in the codebase) that nothing else reuses. Methodology content itself is fragmented across at least four independent rendering paths on the *same* page in some cases (§14).

**Premium as "an advanced PBJ workspace over the same product"**: not currently true structurally. See §21.

### 2.3 Net assessment

Don't restructure the product architecture — the brief is right that the underlying model is sound and the graph is real. The concrete, scoped fix is: (1) wire Entity/Chain into Owner and CHOW, (2) add a State→Chain link, (3) decide deliberately (not by default) what SFF, `/report`, and Premium's relationship to the shared shell should be, since today it's "share the nav bar, nothing else," and (4) finish the dead `_state_ownership_index_cross_link` slot or remove it.

---

## 3. Current styling architecture

PBJ320's styling is not one system with local overrides — it is **at least seven independently-authored styling environments** sharing a nav bar and, in most cases, nothing else:

| Environment | Tech | Token system | Fonts |
|---|---|---|---|
| Main app.py pages (provider/state/entity/owner/national) | Inline Python f-string HTML/CSS | `--pbj-ov-*` (one small component only); rest hardcoded hex | System stack |
| Insights (hub + native articles) | `templates/insights_hub.html` (Jinja) + inline Python template | `--pbj-*`/`--insights-*` (230 declarations, most complete in repo) | **DM Sans/DM Mono/Vollkorn, self-hosted** |
| `/state-standards` | Static HTML | none | **DM Sans/DM Mono/Vollkorn, self-hosted (duplicate `@font-face` block)** |
| `/report` | Static HTML, SSR token-replaced | `--table-*` (local, 23 uses total) | System stack + D3/topojson from CDN |
| SFF (`/sff*`) | React/Vite/TS/Tailwind SPA (`pbj-wrapped/`) | Tailwind utilities | Tailwind defaults |
| PBJPedia (pre-launch) | Inline Python, MediaWiki skin clone (duplicated twice internally) | none (Wikipedia palette hardcoded) | inherits wrapper |
| Ownership (`/owners*`) | Inline Python HTML + external `ownership/*.css`/`*.js` | `--owner-*` (scoped, separate) | System stack |
| Premium (4 sub-surfaces) | Static HTML (Bootstrap) + Jinja templates | `--ui-*`/`--pbj-premium-*` (marketing only); dashboard template has its own unrelated `:root` | Inter/Plus Jakarta Sans (CDN) / system stack / Calibri, three different pairings |
| pbj-ai-support, chow, contact-popup | Root-level standalone CSS files | `--ai-*`, `--chow-*`, none | System stack |

**Why this happened (root-cause, for the migration strategy in §24):** the app grew by adding new inline HTML-string builder functions to `app.py` per surface, each copying the nearest existing pattern and then diverging locally; and by bolting on genuinely separate applications (SFF's React rewrite, Premium's static-site rewrite) that were never re-integrated past the nav bar. Neither pattern is unusual for a project this size and age — the point is that **wholesale CSS deletion or a global search-and-replace palette swap is not viable** (per the brief's own caution and confirmed by evidence: `report.html` explicitly keeps a commented-out "OLD TABLE STRUCTURE" *"PRESERVED FOR REFERENCE (contains critical logic)"*, `report.html:5070-5102` — a direct historical signal that removing "duplicate-looking" code here has broken things before).

Only one asset is genuinely shared across the SFF/`/report`/Insights/PBJPedia surfaces: `pbj-site-universal.js` (nav-toggle and contact-popup behavior). Everything else — CSS, fonts, tokens, table markup, chart libraries — is independently authored per surface.

---

## 4. Component inventory

This is a summary index; full detail with file:line citations lives in the numbered `_scratch/audit_research/` files referenced per row.

| Family | Distinct implementations found | Genuine cross-page reuse? | Research file |
|---|---|---|---|
| Page identity/header shell | 1 primary (`render_page_overview_html`/`render_page_summary_html`), shared by provider/entity/state | Yes — real | 02 |
| Metric/KPI card | 1 primary family (`.pbj-metric` + `render_page_metric_html`), 2 structural variants (spark, ratings), 1 separate "support figure" grammar, 1 dead legacy CSS family | Yes, for the primary family | 02 |
| PBJ Takeaway | 1 canonical builder (`render_prose_takeaway_html`), reused provider+state+entity | Yes — real, strongest single asset in the audit | 02 |
| Flag/status badges | 3 implementations for the identical semantic set (provider inline-style, state CSS-class, 1 dead) + 2 separate star-rendering systems (integer vs. fractional) | No | 02 |
| Tables | 20+ distinct implementations across ~19 page families; one real reuse case (`.chow-table` → owner-facilities table) | Partial — one real case, everything else independent | 05 |
| Charts | 10+ distinct Chart.js/Plotly/hand-rolled implementations across 5+ files; near-duplicate (not shared) theme between provider and state pages | Partial — near-duplicate, not shared | 07 |
| Overlays/disclosure | 15 distinct implementations, 4 different show/hide mechanisms, 3 different focus-management strategies | Minimal — one class-vocabulary reuse (`.pbj-casemix-modal` shell, 6+ instances) but re-copied wiring per instance | 06 |
| Nav bar | 4 hand-written `<nav>` blocks in `app.py`, 1 missing "Owners" link, dedicated helper function never called | No | 03 |
| Search | 2 independent facility-search implementations (homepage inline vs. `public-search.js`) + 3 redundant state-name datasets | No | 01 |
| Icons | Hand-inlined SVG per call site, Lucide/Feather-convention paths but no library loaded; 1 small shared helper covering a fraction of usage | Minimal | 08 |
| Provenance/sources | 4 independent rendering pathways, 2 stacked redundantly on the same page; 1 fully-built but orphaned progressive-disclosure dialog | No | 08 |
| Design tokens | 6 independent, non-communicating `--*` namespaces | No | 08 |
| Premium | 4-5 unreconciled visual languages within one product tier | No | 09 |

### 4.1 What "PBJ Takeaway" and `.pbj-metric` prove

These two are worth calling out because they are evidence the team already knows how to build a shared primitive correctly — `render_page_metric_html` (`app.py:19519`) is called from three different page-generator functions with three different data shapes and renders correctly and consistently in all three (research file 02 §5, confirmed live against `_scratch/provider_075325.html`). The Takeaway pattern is the strongest single asset in the product: a consistent avatar+title+flags+prose+metrics structure that already carries the brief's "PBJ Takeaway concept" faithfully across provider, state, and (in a simplified form) entity pages. **Neither of these should be touched beyond visual restyling** — they are proof of concept for how the rest of the consolidation should work, not problems to fix.

---

## 5. KEEP / CONSOLIDATE / RESTYLE / NEW matrix

Per the brief's Section 19 format. "Migration risk" reflects how entangled the current implementation is with correctness-critical logic (data computation, routing, accessibility), not visual complexity.

### Shell / nav
- **Strongest current implementation:** the primary layout nav block (`app.py:13683`, `data-pbj-nav-version="owners-v2"`).
- **Other implementations:** 3 more hand-written `<nav>` blocks (`app.py:4426`, `25378`, `27483`); a dedicated helper (`owners_nav_link_html()`, `ownership/nav_owners.py:107-118`) that was clearly meant to be the single source of truth and is never called.
- **Functional differences:** the Insights-article nav block (`4426`) is missing the "Owners" link entirely — a real content gap, not cosmetic.
- **Cosmetic differences:** two blocks use inline `style=` instead of the `nav-link` class.
- **Recommendation:** extract one `render_site_nav()` function, call it from all four sites plus SFF's React `SiteNavbar` (via the same class/markup contract even if not the same code).
- **Migration risk:** Low — nav is presentational, easy to visually diff before/after per page.
- **Classification: CONSOLIDATE.**

### Entity/page header
- **Strongest current implementation:** `render_page_overview_html`/`render_page_summary_html` (`app.py:19686-19792`), shared by provider/entity/state.
- **Other implementations:** none competing — this is already consolidated.
- **Recommendation:** restyle in place (tokens, spacing, typography); do not rearchitect.
- **Migration risk:** Low.
- **Classification: RESTYLE.**

### Sections / section headers
- Not separately inventoried as a distinct component in the research passes; appears ad hoc per page (`<h2>`/`<h3>` styled inline per call site). No dedicated section-header primitive exists.
- **Recommendation:** worth extracting as a genuinely NEW shared primitive during the token-layer work, since it doesn't currently exist as a component at all.
- **Classification: NEW.**

### Metrics
- **Strongest current implementation:** `.pbj-metric` family (`render_page_metric_html`, `render_hprd_spark_metric_html`, `render_ratings_metric_html`, `app.py:19519-19856`).
- **Other implementations:** `render_takeaway_support_figures_html` (deliberately non-card, divider-based secondary grammar); dead `.pbj-metric-card`/`.pbj-metrics-row` CSS with zero markup usage.
- **Functional differences:** the support-figure grammar is intentional (secondary emphasis), not redundant.
- **Recommendation:** keep the `.pbj-metric` family as the canonical primitive; delete the dead CSS; restyle for tokens/typography only.
- **Migration risk:** Low.
- **Classification: KEEP (primary family) + minor CONSOLIDATE (delete dead CSS).**

### Takeaway
- **Strongest current implementation:** `render_prose_takeaway_html` (`app.py:20016-20053`), the canonical, reused pattern.
- **Other implementations:** none — this is the one component the audit found zero fragmentation in beyond the flag-badge vocabulary it hosts (see below).
- **Recommendation:** keep the structure and content hierarchy exactly as-is; restyle visually (Phoebe artwork swap, token colors, typography) only.
- **Migration risk:** Low for restyle; the flag-badge sub-component inside it needs CONSOLIDATE (see Panels/badges below).
- **Classification: KEEP + RESTYLE.**

### Panels/cards & flags/badges
- **Strongest current implementation:** none is clearly "strongest" — all three implementations of the same SFF/Abuse/1-star semantic vocabulary (provider inline-style, state CSS-class, 1 dead block inside `generate_provider_page_html`) are equally ad hoc.
- **Functional differences:** abbreviation conventions differ (full words vs. glyphs/short codes) — this may be intentional information-density tuning for a dense table vs. a prose card, not pure drift; worth confirming with Eric before forcing one vocabulary (see §32).
- **Recommendation:** define one flag-badge component with a `dense`/`prose` display variant, backed by one shared `--pbj-danger-*`/`--pbj-warn-*` token set instead of three hand-tuned reds.
- **Migration risk:** Medium — badge content differs by context; must preserve the state table's compact glyphs where information density is load-bearing.
- **Classification: CONSOLIDATE.**

### Tables
See §8 for full detail. **No single strongest implementation; `.chow-table` is the best foundation because it's the one case of proven reuse, but needs to backport the accessible sort control from `insight-rankings__table` and the contextual missing-value pattern from `report.html`'s `#stateTable`.**
- **Migration risk: HIGH.** Five independent sort engines exist, two of which don't sort numeric columns correctly; the state high-risk table has a confirmed *functional* (not cosmetic) discrepancy between its two live renderers (different columns for "the same" data, research file 05 §4/5). Any consolidation must preserve per-table functional differences (comparison table vs. listing table vs. diff table are genuinely different jobs) while unifying the sort/filter/mobile/missing-value mechanics.
- **Classification: CONSOLIDATE** (mechanics) **+ KEEP** (per-table content/column differences that are functional, not cosmetic).

### Charts
See §9. **No single strongest implementation** — the provider-page and state-page Chart.js configs are near-duplicates with slightly different theme constants and one real functional gap (state charts lack the MACPAC benchmark line and the anomaly-flag markers that provider charts have).
- **Migration risk: MEDIUM.** Consolidating theme constants is low-risk; porting the anomaly-detection/benchmark-line logic to state charts is a product decision, not styling, and should be scoped separately.
- **Classification: CONSOLIDATE** (theme/grammar) **+ NEW** (bring state charts up to provider-chart feature parity, if desired — flagged as an open decision, §32).

### Search/forms
- **Strongest current implementation:** `public-search.js` — the best-built overlay in the entire audit (full ARIA combobox pattern, real focus trap, genuine responsive mode switch, research file 06 §13).
- **Other implementations:** the homepage's own inline search (`index.html:2644-2985`) — independently written, different caching key, different keyboard-vs-mouse navigation behavior (Enter opens in a new tab, click navigates in the same tab — a real inconsistency).
- **Recommendation:** the homepage should absorb `public-search.js`'s accessibility patterns (or use it directly) rather than staying a third, separately-maintained implementation.
- **Migration risk:** Medium — homepage search has unique three-mode (Provider/Chain/State) UX that `public-search.js` doesn't currently support; requires feature reconciliation, not just a code swap.
- **Classification: CONSOLIDATE.**

### Tabs/filters
- The state page's "Explore hub" tab widget (`app.py:23459-23585`) is the only tabbed-panel component found; not duplicated elsewhere. Table-level filters (facility search inputs) are reimplemented per table (§8).
- **Classification: KEEP** (Explore hub) **+ CONSOLIDATE** (per-table filter inputs, as part of the table-grammar work).

### Buttons
- Not inventoried as a single system anywhere — every surface hand-rolls its own button styling per component (`.pbj-provider-premium-bridge__request`, `.pbj-state-premium-cta__btn`, Premium's Bootstrap `.btn` + bespoke pill buttons, research file 09 §7). No shared button primitive exists on the public site.
- **Classification: NEW.**

### Overlays
See §10. **No single strongest implementation** across the 15 found; `.pbj-casemix-modal` family is the most-reused *shell*, but every instance re-copies its own open/close JS; the static-page contact popup has the only true focus trap but exists in 3 independently maintained copies; `public-search.js`'s overlay is the accessibility gold standard.
- **Migration risk: HIGH for behavior, LOW for visuals.** The show/hide *mechanism* differences (CSS class vs. `aria-hidden` vs. native `hidden` vs. native `<dialog>`) are behavioral, not stylistic — consolidating them is a JS refactor, not a CSS pass, and must preserve the native-`<details>` cases' zero-JS accessibility rather than "upgrading" them into a JS-driven pattern.
- **Classification: CONSOLIDATE.**

### Provenance
See §14. A complete, orphaned progressive-disclosure dialog already exists end-to-end (`pbj_page_sources.py:27-49` + CSS + live JS handler) and just needs a trigger wired up on pages — this is the rare case where the "canonical component" is **already built and simply not connected**.
- **Migration risk:** Low to re-wire the existing dialog; Medium to reconcile it with the two other live provenance pathways stacked on the same pages.
- **Classification: CONSOLIDATE** (reconcile the 4 pathways down to the 1 that's actually built for this) **+ minor NEW** (the trigger button/wiring on each page, since it currently renders nowhere).

### Loading/error/empty states
- Not separately inventoried in this pass as a distinct pattern family; no dedicated research file covered it directly, and no clear canonical pattern surfaced incidentally in the other research passes. Flagged as an **open gap in this audit** — recommend a follow-up pass before Phase 2 token/component work if empty/error states are a visible priority.
- **Classification: Unclassified — needs follow-up.**

### Icons
See §12. One small shared helper (`_pbj_overview_icon_html`) covers a fraction of usage; everything else is hand-inlined SVG in a consistent *visual convention* (Lucide/Feather-style) but inconsistent `stroke-width` (1.75 vs 2) and zero code sharing.
- **Migration risk:** Low — icons are the easiest consolidation target in the whole audit; swapping to one real icon source (or formalizing the existing hand-drawn set into one shared function) touches presentation only.
- **Classification: CONSOLIDATE.**

### Footer
- Site footer is built inline per page-generator function; not separately inventoried as its own component family, though it is referenced consistently (breadcrumb + sources footer + cross-links pattern, research file 02 §1). No conflicting implementations surfaced.
- **Classification: KEEP + RESTYLE.**

---

## 6. Canonical component candidates

These are the components the evidence says should become the shared foundation — chosen because they already work, already have real (not aspirational) reuse, and are the least risky to touch:

1. **`render_page_overview_html`/`render_page_summary_html`** (`app.py:19686-19792`) — page identity header. Already shared by provider/entity/state. Candidate for the canonical entity-header primitive as-is.
2. **`.pbj-metric` + `render_page_metric_html`** (`app.py:19519-19554`) and its two structural variants (spark, ratings) — canonical metric primitive.
3. **`render_prose_takeaway_html`** (`app.py:20016-20053`) — canonical Takeaway shell. Restyle only.
4. **`.chow-table`** (`chow.css`, reused by `ownership/owner_profile_html.py`) — canonical table foundation, per the rationale in research file 05 (proven cross-page reuse) and §8 below. Needs three specific backports before it can generalize (accessible sort control, contextual missing-value pattern, one shared numeric-aware sort function).
5. **`_pbj_overview_icon_html`/`_PBJ_OV_ICON_PATHS`** (`app.py:19453-19516`) — the one existing shared icon-lookup pattern; extend its coverage rather than replacing it, unless the icon-library decision in §12 supersedes it.
6. **`public-search.js`** — canonical overlay/combobox pattern (best ARIA, real focus trap, genuine responsive mode). Should be the reference implementation the other 14 overlay patterns in §10 are measured against, and ideally the code the homepage search consolidates onto.
7. **`insights-theme.css`'s `--pbj-*` token system** — the most complete, internally consistent token set in the repo (230 declarations, real light/dark pairing already implemented). Candidate starting point for the sitewide token layer in §7, generalized outward rather than invented from scratch.
8. **`pbj_page_sources.py`'s `_sources_dialog()`** (`app.py:12417-12433` CSS + `pbj-site-universal.js:83-93` JS already live) — the already-built, currently-orphaned progressive-disclosure provenance dialog. Candidate canonical "About this data" component; needs wiring, not building.

**Explicitly not candidates:** `report.html`'s inline 4,800-line stylesheet, SFF's Tailwind system, Premium's four visual languages, and PBJPedia's MediaWiki skin — these are covered separately in §24 as integration decisions, not sources to draw shared components from.

---

## 7. Proposed token layer

**Starting point: generalize what already exists, in this priority order.** `insights-theme.css` already has the most complete `--pbj-*` token system in the codebase (canvas/chrome/panel/border/text/blue/sky, shadow scale, a working light/dark pair) — research file 08 confirms it is self-consistent, just not adopted elsewhere. DM Sans, DM Mono, and Vollkorn are already self-hosted as `.ttf` files and wired via `@font-face` in that same file and in `state-standards.html` (duplicated `@font-face` block) — this matches the brief's brand-direction fonts exactly, so the "typography direction" section of the brief is largely a rollout task, not a font-selection task.

**Layer structure (per the brief's Section 17 mandate — token → primitives → surface exceptions):**

1. **Token layer.** Promote `insights-theme.css`'s `--pbj-*` custom properties to a real sitewide `:root` layer (new shared CSS file or a block injected into `get_pbj_site_layout()`), reconciling against the token names already used ad hoc elsewhere (`--pbj-ov-*` in app.py, `--chow-*`, `--owner-*`, `--ai-*`) — not by deleting those namespaces, but by pointing their *values* at the shared tokens where the color is conceptually the same thing (e.g., the five independently-defined "brand accent" hex values — `#2563eb`, `#0d6efd`, `#1e40af`, `#4f46e5`, `#818cf8` — collapse to one `--pbj-accent` token consumed everywhere). De-duplicate the font-face declaration (currently copy-pasted between `insights-theme.css` and `state-standards.html`) into one shared include.
2. **Shared primitives layer.** The six components in §6, restyled to consume the new tokens, become the primitive layer other pages build from.
3. **Surface-specific exceptions.** Per the brief's explicit caution (§17): **do not delete or globally search-and-replace existing CSS.** `report.html`'s "OLD TABLE STRUCTURE... PRESERVED FOR REFERENCE (contains critical logic)" comment (`report.html:5070-5102`) is a direct historical warning that this codebase has been burned by exactly that kind of cleanup before. Structural CSS (layout mechanics: sticky positioning, mobile card-stack `data-label` wiring, D3 map container sizing) should be identified and left alone even where it "looks like" a duplicate; only literal color/font/spacing *values* should be migrated onto tokens in the first pass.

**What NOT to do in the token layer:** invent a new palette from scratch (DM Sans/Mono/Vollkorn already exist and are already correctly self-hosted); force every chart/table/badge color onto one purple (the brief is explicit that brand color owns the frame, semantic color owns the data — §10 has the concrete chart-color findings that make this non-negotiable); or attempt to resolve the 19 distinct breakpoint values (research file 08 §C4) into a single set in the same pass as the color/font token work — breakpoints are entangled with layout-specific JS (tick-density logic in chart configs, table mobile strategies) and should be a separate, later cleanup.

---

## 8. Table system

Full inventory: research file 05 (20+ distinct implementations across ~19 page families). Summary matrix reproduced from §5; this section adds the "why" and the concrete migration path.

**Why no single implementation wins outright:** maturity splits across three uncorrelated axes. `.chow-table` (CHOW hub, provider ownership accordion, reused directly by the owner-facilities table) has the richest interaction set — real sticky headers, expandable rows, hover/active states — and is the *only* case of genuine cross-page table reuse already in the codebase. But its sort is string-only (`chow.js:440-445` does `String(v).toLowerCase()` for every column with no numeric fallback), and it has no accessible sort control. `insight-rankings__table` (one Insights post) has the only keyboard-operable sort control in the entire inventory — a real `<button>` inside each `<th>` with `aria-pressed` state — but it's scoped to a single editorial post. `report.html`'s `#stateTable` has the most sophisticated missing-value handling (`<abbr title="...">` with three distinct contextual reasons for *why* a value is absent) and the only sticky-corner (row+column) header, but it lives in a 7,700-line standalone file with no shared CSS/JS with the rest of the site.

**Concrete, scoped functional gap (not cosmetic drift):** the state high-risk facilities table is rendered by two live code paths inside the *same* function (`_render_state_pbj_high_risk_section_lazy`, `app.py:22339-23185`) — the "explore" preview table has a City column and no Census; the legacy accordion table has Census and no City. A user sees genuinely different information depending on which UI path they took to reach "the same" table. There is also a **confirmed ~300-line dead duplicate renderer**, `_render_state_pbj_high_risk_section()` (`app.py:22884-23185`), never called anywhere — a pure deletion candidate, not a consolidation target.

**Sort-state class naming has drifted into five spellings for the same concept**: `sort-asc`/`sort-desc` (chow-table, entity-facilities via a different attribute), `data-dir` attribute instead of classes (entity-facilities-table), `is-asc`/`is-desc` (insight-rankings). Only two of the five independent sort engines (`owner-profile.js`, `insight-rankings.js`) reliably sort numeric columns numerically — the rest sort strings, meaning a numeric CHOW or entity column added in the wrong place today would silently sort in the wrong order.

**Recommended canonical foundation and required backports** (per research file 05's conclusion, which this audit endorses): build the shared table grammar from `.chow-table`, because it is the only implementation with proven multi-surface reuse, and backport three things other implementations already solved better in isolation:
1. `insight-rankings__table`'s accessible `<button>`-in-`<th>` sort control and `aria-pressed` state.
2. `report.html`'s contextual `<abbr title="...">` missing-value pattern (with per-context reasons, not just a bare "N/A").
3. One shared numeric-aware sort function, replacing the five independent (and inconsistently correct) reimplementations.

**Six distinct, non-shared mobile strategies exist** (CSS `data-label` card-stack, server-rendered dual-DOM card list, horizontal-scroll-only, column-drop via `nth-child`, font/padding shrink only, text-truncation swap) — consistent with the brief's instruction not to default to "everything becomes cards." The strongest of these, `pbj-staffing-cmp-table`'s pure-CSS `data-label` card-stack (single DOM tree, no duplicate markup, `app.py:13514-13521`), should be the default mobile technique for listing tables where content genuinely reduces to label/value pairs; `report.html`'s sticky-corner "fight the viewport" approach should be preserved as-is for the national rankings table, where the row+column-header orientation is load-bearing for comparing many states at once.

**Do not consolidate:** the record-diff table (`chow-compare-table`, before/after CHOW fields), the fixed metric-comparison table (`pbj-staffing-cmp-table`), and the print/PDF sample-report tables are genuinely different jobs from a sortable listing grid — forcing them into one grammar would be a functional regression, not a cleanup, per the brief's explicit "we do NOT want one identical table component regardless of purpose" instruction.

---

## 9. Chart system

Full inventory: research file 07. **At least five distinct charting implementations, not one shared grammar**, across the surfaces in scope: Chart.js (provider page, state page — near-duplicate, not shared), a hand-rolled `<canvas>` 2D-context chart with no library (`generate_us_chart_html`, `app.py:21707-21837`, the only chart in the app that is light-themed by default), Plotly (`premium/premium-hero-chart.js`, apparently unwired/orphaned — no page loads it or the Plotly CDN), plus three more Chart.js implementations outside the originally-scoped files (`insights.html`, `insights-ny-minimum-staffing.html` pinned to Chart.js 4.4.0, `templates/premium_facility_dashboard.html`) each with their own palette and theme.

**The single biggest problem is color carrying zero metric identity.** `#2dd4bf` teal is the default "primary series" color for Total staffing, RN, LPN, Aide, Census, *and* Contract % — every metric on the provider and state pages gets the identical hue regardless of what's being measured, so nothing in the chart's color tells a reader which metric they're looking at except the title/legend text (research file 07 §4). Meanwhile the *same* conceptual metrics get different colors elsewhere in the app: Total staffing is indigo (`#818cf8`) in the Premium dashboard template instead of teal; Census is orange (`#ff7f0e`) in `insights.html` instead of teal; and within that single Premium dashboard file, Census and Nurse-aide HPRD both use the identical `#34d399` emerald for two unrelated metrics in the same chart set.

**A real, not cosmetic, functional gap between the provider and state charts for the same metric:** the provider (facility) page's Total Staffing chart shows a MACPAC state-minimum benchmark reference line; the state-aggregate page for that *same state* does not — confirmed by a full read of `state-page-charts.js`, which contains no reference to `macpac` anywhere. The provider page also has a data-driven anomaly detector that flags suspected-incomplete PBJ submissions with amber diamond markers and an explanatory footnote/tooltip; the state chart has none of this, so a missing/bad quarter on the state chart just shows as an unexplained gap.

**Four different techniques exist for the same "draw a horizontal benchmark line" need** (manual flat-value Chart.js dataset, the same technique ported to Plotly traces, `chartjs-plugin-annotation`, and a custom `afterDraw` canvas plugin) — none shared across more than one file.

**On the brief's "don't assume more staffing = green" instruction:** the audit found **no instance of raw staffing magnitude being colored green because higher is assumed better.** Every deliberate green/red usage traces to an actual computed comparison — the case-mix ratio bars (reported HPRD ÷ CMS case-mix benchmark), the NY minimum-staffing report's `pctColor()` (share of facilities below a named threshold), and the Premium hero chart's per-day threshold comparison. **One clear violation of the adjacent principle was found**, though: `insights.html:2059` applies a red/amber/green traffic-light palette (`['#e74c3c', '#f39c12', '#27ae60']`) to three *neutral statistical methods* for computing the same figure (weighted "Ratio," "Median," "Simple Mean") — none is better or worse than another, so the coloring invites a reader to infer the green bar is the "right" number, which the underlying data doesn't support. This should be corrected as part of any chart-system pass regardless of the broader redesign.

**Recommendation for one PBJ chart grammar:** consolidate the provider-page and state-page Chart.js theme constants (currently near-identical but not literally matching — `rgba(228,228,231,0.95)` vs. `rgba(226,232,240,0.95)` for text color, etc.) into one shared theme object; assign each metric (Total, RN, LPN, Aide, Census, Contract %) a distinct, fixed color from the semantic-color scale rather than the current all-teal default, reserving brand purple for chrome/frame per the brief's Section 4 instruction; and treat porting the provider page's benchmark-line and anomaly-marker features to the state chart as a deliberate product decision (flagged in §32) rather than an automatic side effect of a styling pass, since it changes what information the state chart conveys, not just how it looks. Line-style/dash differentiation between primary and secondary series (already good practice on the Total/Direct pairing) should be the default pattern extended to any newly-added series, so meaning doesn't rely on color alone per the brief's instruction.

---

## 10. Overlay/disclosure system

Full inventory: research file 06 (15 distinct implementations, 4 different show/hide mechanisms — CSS class toggle, `aria-hidden` attribute toggle, native `hidden` attribute toggle, native `<dialog>` — and at least 3 independently-written focus-management strategies).

**A clean 3-tier content taxonomy is visible in the evidence, matching the brief's suggested model closely:**
- **Tier A — inline label** (bare `title=""` attributes, simple hover tooltips): one short string, no interactive content, dismissed passively. Weakest tier for accessibility across the board — native `title` is not reliably reachable by keyboard or announced consistently by screen readers.
- **Tier B — contextual popover** (states lists, AI action menu, owner-info dialog, entity-states/staffing-comparison popover): triggered by click or hover, positioned near the trigger or portaled to a fixed mobile position, holds a short list or a few data points.
- **Tier C — full modal/dialog** (case-mix modal family, Premium hub modals, contact/CHOW/sources dialogs): centered overlay with backdrop, holds multi-paragraph explainers, tables, or forms.

**But the technical execution underneath that taxonomy is not consolidated — this is a JS/behavior problem, not primarily a CSS one.** Within Tier C alone, five different modal *engines* do conceptually the same job: hand-rolled `div`+`aria-hidden` with per-instance inline `<script>` (the `.pbj-casemix-modal` family — used 6+ times, each instance re-copying its own open/close JS rather than sharing one handler); a better-focus-managed `div`+`aria-hidden` engine (Premium hub modals — stores and restores focus, moves focus to the close button on open); a third `div`+inline-style engine (the dynamic-page contact modal); native `<dialog>` via `showModal()`/`close()` (owner-info modal, and the orphaned sources dialog — both get free Escape/focus-trap/focus-restore from the browser); and three **independently copy-pasted** `div`+manual-focus-trap engines across `index.html`/`report.html`/`press.html`'s static contact popups — the only implementation with a genuine Tab-cycling keyboard focus trap, duplicated three times by hand rather than shared once.

**Best-built implementation in the entire audit, and the reference standard to consolidate toward:** `public-search.js`'s facility-search overlay — full ARIA combobox pattern (`role="combobox"`, `aria-autocomplete`, `role="listbox"`), a real Tab-cycling focus trap, arrow-key roving selection, and a genuinely distinct (not just resized) mobile layout. This proves the team can build the accessible version correctly; it sharpens rather than excuses the inconsistency found in the other 14 implementations.

**Concrete, fixable accessibility issues found (independent of the broader consolidation):**
- The owner-donor-dashboard hover tooltip (`donor/templates/owner_donor_dashboard.html:1260-1295`) is mouse-only with zero ARIA and contains an interactive "View details" link a keyboard or screen-reader user can never reach — the single most accessibility-concerning pattern found.
- The bare-span variant of the high-risk-criteria tooltip (`app.py:22438`, `23016`) has no focusable trigger at all — hover-only, no keyboard path.
- The `.pbj-casemix-modal` family (6+ instances) never moves focus into the dialog on open, and has no Tab-cycling trap — a keyboard user who activates the info chip has focus stranded on the now-hidden trigger.
- The CHOW detail modal (duplicated byte-for-byte between `chow.js` and `ownership/chow_display.py`) never moves focus in on open or restores it on close — weaker focus handling than every other Tier-C implementation.
- `_about_data_button()`/`_sources_dialog()` (`pbj_page_sources.py:27-49`) is a fully-built native-`<dialog>` progressive-disclosure pattern — the leanest, most natively-accessible dismiss mechanism in the whole inventory (`<form method="dialog">`, no JS needed to close) — but it is **never called from any page**, even though its CSS ships on every page load and its JS click-handler is unconditionally bound at page-init. This is the clearest "re-wire, don't rebuild" opportunity in the entire audit.

**Recommendation:** define the 3-tier taxonomy formally (Tooltip / Popover / Modal, matching the brief's suggested model), but treat consolidation as reducing 15 code paths to roughly 3 *shared functions* (one per tier) called from every surface, not as a styling pass — the underlying JS behavior (focus management, Escape handling, dismiss mechanism) is where the real inconsistency and the real accessibility risk live, not the visual chrome. Preserve native `<details>` and native `<dialog>` usage wherever they already exist rather than replacing them with JS-driven equivalents — they are, by construction, the most accessible options in the inventory today.

---

## 11. Search / control system

**Two independent facility-search implementations exist**, not one shared component (research file 01 §5): the homepage's own inline search (`index.html:2644-2985`, three-mode Provider/Chain/State) and `public-search.js` (823 lines, used elsewhere on the site — provider/state page nav — as "desktop anchored popover, mobile expanded header mode"). They cache independently under different `sessionStorage` keys and — concretely — **behave differently for the identical action**: pressing Enter on the homepage search opens the first result in a new tab (`window.open(..., '_blank')`), while clicking a result navigates in the same tab. This is a real, fixable inconsistency independent of any visual redesign.

**Three redundant 50-state name/abbreviation datasets** exist across the search surface: one inline in the dead "Mobile Chart Setup" script (`index.html:3006-3017`), one in `public-search.js`'s `SLUG_TO_STATE` map, and the live homepage state filter's own data (sourced from `/search_index.json` at runtime). Only the latter two are live; the first is dead weight (see §15).

**The Provider / Chain / State segmented control is fully functional, not vestigial** — confirmed live via browser interaction: switching tabs changes the placeholder text, hides/shows the "USA" state-filter dropdown (Provider mode only), and is wired via `role="radiogroup"`/`aria-pressed` (`index.html:2245-2251`, `2749-2776`).

**The "USA" state-filter dropdown is real, functional, and correctly scoped** — it is a per-search-mode filter (limits Provider search results to one state; not shown in Chain/State modes), populated at runtime from the search index, not a vestigial or decorative control. This directly answers the brief's open question in Section 3 ("USA selector: whether it serves any real purpose") — it does.

**A second, fully dead "USA" feature coexists with the live one**, creating a naming collision worth flagging even though it's invisible to users: a ~185-line inert script block (`index.html:3001-3183`) targets a `#stateSelect`/`#staffingChart` pairing that no longer exists in the page's markup, from an earlier design iteration. It's harmless in that it renders nothing, but it unconditionally fetches four JSON files (`/states_list.json`, `/state_historical_data.json`, `/quarters_list.json`, `/national_historical_data.json`) on every homepage pageview for a chart that can never draw — pure wasted network weight, and a maintenance trap for the next person who sees "USA" and "state chart" logic and doesn't know one of the two is dead.

**Recommendation:** consolidate the homepage's inline search onto `public-search.js`'s accessibility patterns (real focus trap, keyboard/mouse parity) rather than maintaining a third implementation of the same underlying concept; this is a behavior fix, independent of and cheaper than the token/visual work. Delete the dead mobile-chart script and its four unconditional fetches as a zero-risk cleanup (§15, §29 candidate).

---

## 12. Icon recommendation

**Current state:** hand-inlined SVG per call site throughout `app.py` — 13 `<svg` occurrences sampled directly, each redefining its own `viewBox`, dimensions, and stroke attributes independently (research file 08 §B). No icon library is loaded anywhere in the app (confirmed: zero hits for Lucide/Phosphor/Feather/Font Awesome/Material CDN references, script tags, or class conventions). `ai-icons/` is explicitly a 3-file allow-listed set of AI-vendor brand marks (ChatGPT/Claude/Gemini logos, `app.py:2718-2728`) — not a functional icon system, and should not be confused with one, exactly as the brief warns.

**A telling structural clue:** every sampled icon uses `viewBox="0 0 24 24"`, `fill="none"`, `stroke="currentColor"`, `stroke-linecap="round"`, `stroke-linejoin="round"` — the precise Lucide/Feather convention — strongly suggesting the original paths were copied from a Lucide-derived set even though no such library is actually loaded. `stroke-width` is inconsistent between call sites (`2` in some places, `1.75` in others, including within the one shared helper `_pbj_overview_icon_html`), so even icons that share a visual lineage render at different weights depending on which code path emitted them. One small centralized pattern already exists — `_PBJ_OV_ICON_PATHS`/`_pbj_overview_icon_html` (`app.py:19453-19516`) — proving the team already knows how to do this; it just covers a fraction of total icon usage. A clear, easy consolidation target was also found: four Explore-hub card icons (`app.py:23411-23428`) share byte-identical wrapper markup with only the inner `<path>` differing — a direct candidate for the same shared-helper pattern.

**Recommendation, per the brief's evaluation criteria (restrained, legible, broad coverage, accessible, consistent, minimal integration friction, appropriate for serious data UI):**

- **Primary: Lucide.** Its stroke conventions are already what the codebase's hand-drawn icons imitate, so adopting it formalizes an aesthetic the team has already chosen rather than introducing a new one. It ships as plain SVG (easy to inline server-side from Python without a JS runtime dependency, matching the app's inline-HTML-string architecture), has broad coverage for the data/analytics icon vocabulary this product needs (search, sort arrows, info/warning, external link, expand/collapse), and is MIT-licensed with no attribution burden.
- **Runner-up: Phosphor (regular weight).** Slightly larger glyph library, similarly restrained default weight, also available as plain SVG. Choose this over Lucide only if a stylistic preference emerges during implementation for Phosphor's marginally more geometric forms — functionally the two are close enough that either satisfies the brief's criteria.
- **Avoid:** any icon *font* (Font Awesome, Material Icons class-based) — these require either a webfont load (extra request, FOUC risk) or a build step the current inline-Python-HTML architecture doesn't have; and avoid emoji as ordinary UI icons (the audit found no current emoji-as-icon usage in the sampled sections, which is worth preserving deliberately as the icon system formalizes).

**Migration approach:** replace the hand-inlined `viewBox="0 0 24 24"` SVGs with the equivalent Lucide paths inside a generalized version of `_pbj_overview_icon_html`, standardizing on one `stroke-width` (recommend `1.75`, the more common value in the sample and visually lighter/more restrained, consistent with the brief's "low UI chrome" direction). This is a low-risk, high-visibility consolidation — icons carry no business logic, so the change is purely presentational and easy to visually diff.

---

## 13. Phoebe / Takeaway treatment

**Phoebe's actual footprint is wider than the product's own documented policy.** `phoebe-usage-rules.js` (the authoritative-by-name usage doctrine, defining `PHOEBE_ALLOWED_PAGES = ['index', 'about', 'insights', 'pbj-sample']` and hard exclusions for Press/Attorneys/Methodology) is **pure documentation — never `<script src>`-loaded, never imported, never enforced anywhere in the codebase** (research file 01 §3.1). In practice, Phoebe's actual, wider footprint is: the homepage "What is PBJ?" hover strip; the About page explainer; the standalone `/phoebe` page; **the PBJ Takeaway avatar on every provider page and every state page** (the widest deployment by far, via `PBJ_TAKEAWAY_AVATAR_HTML`, `app.py:4715-4718`, consumed at `20042` and `24364`); the Insights hub/article pages (where Phoebe also doubles as the page **favicon**, `insights.html:11` — the only page in the site that departs from the standard `pbj_favicon.png`); and the PBJ Wrapped social-share image. The "hard exclusions" (Press, Attorneys, Methodology) are honored only by convention/omission today, with no shared guard function checking them.

**Within the Takeaway, Phoebe's role already matches the brief's intent precisely** — a fixed 48×48 avatar (`alt="Phoebe J"`) placed once, at the top of the card, with **no inline "Phoebe says" narration, no named voice in the prose text**, and no other Phoebe-branded element inside the card. This is exactly "occasional explanatory... not dominating ordinary analytical screens." **No "Put another way" pattern exists anywhere in the codebase** (`grep -i "put another way"` — zero matches) — the brief's mention of this concept describes an aspiration, not a current feature; if it's wanted, it would be new copy/content work, not a design-system change.

**Confirmed: "Bricky" and "Mr. Cells" are not present anywhere in the codebase.** A repo-wide case-insensitive grep for both names, restricted to `.html`/`.css`/`.py` files, returned zero real hits — every apparent match was the unrelated real facility-chain name "Brickyard Healthcare" in data files. No exclusion work is needed; there is nothing to exclude.

**Concrete cleanup opportunities surfaced alongside Phoebe, independent of the artwork swap:**
- Two large, fully orphaned Phoebe PNGs sit at repo root (`phoebe_wide.png`, 2.29MB; `phoebe-wrapped-wide.png`, 1.80MB) with zero references anywhere in code — confusingly, a *different* file at a different path shares the second file's exact name and *is* the one actually served. ~4.1MB of dead weight, doubly confusing for future maintainers.
- The favicon-as-Insights-icon override (`insights.html:11`) is a deliberate but undocumented departure from the standard favicon — worth a conscious decision (keep as a distinct Insights identity marker, or standardize) rather than leaving it as an unexplained one-off.

**Recommendation for the canonical Phoebe artwork swap:** because the avatar is a single, tightly-scoped 48×48 image reference (`PBJ_TAKEAWAY_AVATAR_HTML`) consumed from exactly one constant, replacing the artwork is a **one-line change with sitewide effect** across every provider and state page — genuinely low migration risk. Formalize the usage doctrine currently sitting inert in `phoebe-usage-rules.js` into an actual guard function (even a simple allowlist check called from the relevant page generators) so the "hard exclusions" are enforced rather than just documented, and delete the two orphaned PNGs as part of the same pass.

---

## 14. Provenance / evidence system

**The infrastructure for the brief's "progressive evidence disclosure" model already exists — split across two well-built modules that never talk to each other, plus a dialog that's fully built and never wired up.**

`public_source_vintage.py` is a genuinely well-structured single source of truth: one row per dataset (CMS PBJ, Provider Info, SNF ownership, SFF PDF list, chain performance, MACPAC state staffing, FEC contributions), each with a release ID, human vintage label, official/processing dates, cadence, and source URL(s). `pbj_page_sources.py` builds compact, correct-looking footer components on top of it — including a full "About this data" progressive-disclosure dialog (`_about_data_button()` + `_sources_dialog()`, `pbj_page_sources.py:27-49`) with its CSS already shipping on every page (`app.py:12417-12433`) and its JS click-delegation handler already unconditionally bound at page-init (`pbj-site-universal.js:83-93`). **This dialog is never called from any page — the trigger button that would open it is never rendered anywhere in the codebase.** This is the single clearest "build vs. re-wire" finding in the whole audit: the exact compact-affordance → contextual-explanation pattern the brief asks for (§12: *"a compact source/vintage affordance → contextual explanation → deeper evidence/methodology path"*) is sitting fully built and dormant.

**Where source/vintage info actually surfaces today, it does so through four uncoordinated pathways, two of them stacked redundantly on the same page:**
1. `render_facility_sources_footer()`/`render_entity_sources_footer()` — one-line "Sources:" footer.
2. `render_methodology_block()` — a separate collapsible Methodology block, called on the **same** facility and entity pages as #1, independently deriving/displaying overlapping vintage info.
3. Ad hoc inline `<p>` sentences in the NY/state compliance modals, not using either shared helper, each linking to a *different* `/data-sources#anchor` fragment.
4. The `/data-sources` page's own vintage table (`render_data_sources_vintage_table_html()`), the deepest single view but disconnected from the on-page footers/blocks that reference the same data.

**Concrete phrasing inconsistencies found, independent of any visual redesign** (research file 08 §A6): the same PBJ dataset is described as a specific quarter in one component and a year-range ("2017–2026") in another, on the same page; "updated" language uses day-level precision in article bylines but month-level precision on `/data-sources`; the "no value" sentinel is rendered as an em-dash in the public label helper but the literal string `'UNKNOWN'` internally before that helper is applied; and the full name "CMS Payroll-Based Journal (PBJ)" is spelled out inconsistently (sometimes with "(PBJ)," sometimes bare "CMS PBJ," sometimes without the parenthetical at all) across at least four call sites. None of this requires new design work — it's a copy-consistency pass once the rendering pathways are consolidated.

**PBJPedia methodology content (pre-launch) is richer than what's exposed elsewhere** — `pbjpedia-data-limitations.md` enumerates known PBJ caveats (paid-hours-only, no wages/shift times, no resident-level acuity, quarterly-not-daily exclusions, underreported physician hours) in more depth than the one-line "Note:" caveat baked into `render_methodology_block`, but is not currently cross-linked from `/data-sources` or the on-page Methodology blocks at all, and is itself gated behind `PBJPEDIA_PUBLIC=1`.

**Recommendation, matching the brief's explicit "no bulky provenance footer beneath every card" instruction:** wire the existing `_sources_dialog()`/`_about_data_button()` pattern into the compact "Sources:" line already rendered on provider/entity pages (pathway #1), making the existing one-line footer the trigger for the existing (currently dormant) dialog — this directly implements the brief's compact-affordance → contextual-explanation model without adding a new component. Then fold pathway #2 (Methodology block) and pathway #3 (ad hoc modal sentences) into calls against the same `public_source_vintage.py` data rather than independent derivations, so the phrasing inconsistencies in the previous paragraph resolve as a side effect rather than requiring a separate copy-editing pass. Treat `/data-sources` and PBJPedia's methodology articles as the "deeper evidence/reproducibility" tier for the technical/journalist/attorney audience the brief names, and add the cross-link from the compact dialog into that tier that doesn't currently exist.

---

## 15. Homepage findings

Browser-verified live (desktop 1440×900 and mobile 390×844, local server, `/`).

**Visual reality vs. the Figma reference — the biggest single gap in this audit relative to the supplied direction.** The live homepage today is a **dark navy theme** (near-black background, white/lavender text, indigo `#818cf8` "320" accent) with a bold sans-serif headline — not the "warm paper/light background... strong serif headline treatment" direction described in the brief's Section 3. This is a real, visible gap between the current baseline and the supplied visual reference; it is squarely what the redesign is *for*, not a defect to fix separately. Screenshots captured to `_scratch/screenshots/` during this audit for reference.

**Content/behavior baseline (per the brief's instruction to treat this as authoritative over Figma placeholder copy):**
- Eyebrow: "OPEN-ACCESS CMS DATA · NURSING HOME STAFFING"
- H1: "PBJ Nursing Home Staffing Dashboard" (with a mobile line-break variant)
- Subhead: "Search 10 years of CMS Payroll-Based Journal staffing data across 15,000+ U.S. nursing homes."
- Provider / Chain / State segmented control — **confirmed live and fully functional** by direct interaction (clicking "Chain" swaps the search field to "Chain name or ID" and removes the USA selector).
- "USA" state-filter dropdown — **confirmed live and functional**, Provider-mode only, populated from the search index at runtime.
- "What is PBJ?" — a small circular Phoebe avatar + hover/focus popup, positioned directly under the search card.
- Quick-links row: "Rankings · SFFs · Insights · PBJ Explained" — confirmed **mobile-only** in code (`@media (min-width: 769px) { .hero-explore-bar { display: none; } }`); desktop visitors never see this row and there is no desktop equivalent elsewhere on the page.
- Below the fold: an email subscribe band, a Premium CTA banner, then the standard footer (About · Premium · Press · Sources · Corrections · Subscribe).
- Source attribution is **not** persistently visible in the hero — it lives one click deep, inside the search-help popup, under a "Sources" subsection linking to the three underlying CMS datasets. This is one click deeper than the always-visible sourcing line on provider/state pages.

**Homepage architecture is structurally distinct from the rest of the app**: the homepage route (`app.py:1950-1960`) serves the literal static file `index.html` (3,187 lines) with light server-side splicing (CSRF token, audience-widget injection), rather than being built as an inline-Python HTML string like provider/state/entity pages. This matters for the migration plan (§24) — the homepage's CSS/JS is not entangled with `app.py`'s inline-template system at all, so it can be redesigned largely independently without touching the 28,200-line file.

**Two categories of dead code found on the homepage, safe to remove regardless of the visual redesign:**
- A ~185-line inert "Mobile Chart Setup" script (`index.html:3001-3183`) targeting DOM elements that no longer exist, still unconditionally fetching four JSON files per pageview (§11).
- `index-render.html` (1,140 lines) — a fully orphaned legacy homepage build referencing a defunct Render staging domain and loading D3.js from a CDN nothing else uses; zero Flask routes reference it.
- Matching dead CSS (~9 classes, `index.html:1650-1755`), explicitly self-labeled in a code comment as "retained for any future use," and one orphaned class (`.hero-explore-links`).

**Mobile search:** no separate markup — the same DOM with responsive CSS overrides, including a specific fix for iOS auto-zoom (16px input font-size) and a bottom-sheet transformation of the search-help popup under 768px. This is a reasonable existing pattern, not a rebuild candidate.

---

## 16. Provider findings

Browser-verified live (desktop and mobile, `/provider/075325` — Mary Wade Home, New Haven, CT).

**The provider page is the strongest, most consistent surface in the audit and the correct Phase 1 proof surface** (confirmed independently by both the code research and live rendering). Section order, confirmed both in code (`generate_provider_page_html`, `app.py:17805-18828`) and live: snapshot eyebrow + identity header → PBJ Takeaway card (avatar, flag badges, prose, primary metrics, support figures) → collapsible ownership/CHOW accordion → intro copy → four Chart.js charts (Total Staffing, RN/LPN/Aide, Census, Contract %) → CMS Case-Mix comparison block → CTAs (custom report, Premium) → Methodology block → footer (breadcrumb, sources, cross-links).

**Live-verified metric set for the sample facility:** Total HPRD 4.76 (4.39 direct) with a quarterly sparkline, Residents 84, CMS Ratings (Overall ★, Staffing ★★★★), CMS Case-Mix 3.60 HPRD, RN 0.56 HPRD, Nurse Aide 2.76 HPRD — followed by a full CMS Case-Mix ratio breakdown (Total/RN/LPN/Nurse-aide case-mix ratios) and four line charts. All four charts confirmed rendering live data via direct DOM/canvas pixel inspection (see §22 for a note on a browser-tooling screenshot artifact encountered and resolved during this check).

**Confirmed dead code inside the page generator, safe to delete independent of any redesign:** a ~58-line badge-vocabulary block (`app.py:18099-18156` — `overall_badge_html`, `staffing_badge_html`, `casemix_badge_html`, etc.) is computed but never referenced again anywhere in the function; the page renders its actual badges through a completely different, live code path. A matching legacy CSS family (`.pbj-metric-card`/`.pbj-metrics-row`, `app.py:11026-11031` + mobile overrides) ships on every page load with zero markup anywhere in the repo emitting those classes.

**The flag-badge vocabulary problem is concentrated here** — see §5/§10: the same SFF/Abuse/1-star semantic set (single source of truth: `_pbj320_high_risk_reasons`, `app.py:782-824`) renders through three independent color/label/markup conventions depending on which page you're looking at, including the now-dead third instance inside this very function.

**PBJ Takeaway confirmed matching the brief's intent exactly**: single static 48×48 Phoebe avatar, no named narration, single prose paragraph (no "Put another way" pairing exists in the codebase today), primary metric row, secondary support-figure row, optional caveat. This is the pattern to restyle, not restructure.

**Provenance is doubled on this exact page**, per §14 — the collapsible Methodology block and the one-line Sources footer both render here, independently deriving overlapping vintage information.

---

## 17. State findings

Browser-verified live (desktop and mobile, `/state/ny`).

**Same identity/Takeaway/metric shell as the provider page, confirmed consistent live**: Total HPRD 3.55 (state 2026 Q1), Providers 590, Residents 98,707, National Rank #46 of 51, RN 0.68, State Minimum 3.50 — same `.pbj-metric` primitive, same Takeaway prose pattern, same avatar. This consistency is real and should be preserved as-is through the redesign.

**The "Explore [State]" hub is the connective-tissue mechanism the product-architecture question in §2 depends on**, and it is confirmed live and fully wired: four tabs (High-risk facilities, Staffing snapshot, Ownership groups, Ownership changes), all rendering for New York — `ownership_beta_enabled_for_state()` now covers all 50 states + DC despite its "beta" name (`ownership/beta_gate.py:25`), so this hub is live everywhere, not a partial rollout.

**A dead cross-link placeholder ships on every state page**: `_state_ownership_index_cross_link = ''` (`app.py:24173`), interpolated into the render but never assigned a value anywhere — a scaffolded connective-tissue slot abandoned mid-build.

**Stale product-phase messaging survives a completed rollout**: `_owners_state_locked_html` still tells users ownership pages are available only for "New York, Connecticut, and Florida" (`app.py:7172`), directly contradicting the nationwide-launch state the code actually implements (`OWNERSHIP_PUBLIC_STATES = US_STATE_CODES`, all 50 + DC). The path is effectively unreachable in normal navigation today, but the copy is a leftover of a superseded product phase still shipping in the code — worth a one-line fix independent of the redesign.

**Mobile table handling on this page is a genuine positive finding, worth preserving as a pattern**: the high-risk facilities table transforms into stacked cards on mobile (facility name, city, OVR/STF star ratings per card) rather than defaulting to horizontal scroll — confirmed live at 390px. This is exactly the brief's instruction not to reflexively "card everything," applied selectively where it fits the content.

**Chart parity gap with the provider page** (detailed in §9): the state Total Staffing chart has no MACPAC benchmark line and no anomaly-flag markers, even though the *same state's* provider pages show both for individual facilities.

---

## 18. Ownership / entity findings

Browser-verified live (desktop and mobile, `/entity/50` — Aspen Skilled Healthcare, 35 facilities; `/owners`; `/owners/6507082955/chad-keetch`).

**The clearest structural gap in the entire audit is here, not a visual one.** The Entity/Chain page is **ownership-blind by design**: `render_entity_ownership_tools_block()` (`ownership/page_integrations.py:906-907`) is a one-line stub returning `""`, `portfolio_display.py` contains zero `href=` in the whole file, and `generate_entity_page_html` has no CHOW code path at all. Live-verified: the rendered `/entity/482` page contains exactly one `/owners`-domain link (the global nav item) and zero occurrences of "chow." A chain page cannot get a user to that chain's controlling owner or its ownership-change history, even though the provider pages beneath it and the state pages above it both can.

**Owner profile pages are correctly server-rendered HTML, architecturally the same pattern as provider/state/entity** — not a separate SPA, confirmed both in code (uses the same `get_pbj_site_layout()` shell) and live (visually consistent dark theme, same nav, same purple accents on screenshot). The `/owners/api/*` endpoints are progressive-enhancement fragments (autocomplete, "show more"), not the primary render path.

**But Owner has no way back to State**: `_owner_index_back_link_html` only offers `/owners` or `/owners/<state-slug>`, never `/state/<slug>` — a user who arrives at an owner profile via a state page's Explore hub has no way back to that state's staffing page except browser Back; the owner page's own state-by-state facility breakdown renders as plain text, not links.

**Ownership runs its own parallel design-token and asset system**, the only part of the product with a real external CSS/JS pipeline: `owner-profile.css` (6,838 lines) defines `--owner-*` custom properties (`--owner-card-bg`, `--owner-accent`, etc.) scoped to `.owner-profile-root`, entirely separate from the `--pbj-*`/inline-hex conventions used elsewhere in `app.py`. This is architecturally isolated in a way that matters for the migration plan (§24) — it is a real, working system on its own terms, just not integrated with the token layer proposed in §7.

**Duplicated, drifting nav markup was traced to its root cause here**: at least four hand-written `<nav>` blocks exist in `app.py` instead of one shared builder; the Insights-article block is missing the "Owners" link entirely; and a purpose-built helper (`owners_nav_link_html()`, `ownership/nav_owners.py:107-118`) that appears to have been written specifically to prevent this drift is never actually called from `app.py`.

**Live confirmation of visual consistency at the hub level**: the `/owners` national hub and the `/owners/<pac>/<slug>` profile page both screenshot as visually consistent with the rest of the site (same dark theme, purple accents, "Largest ownership portfolios" / "Recent ownership changes" panels reading like native PBJ320 content) — the fragmentation here is structural (missing cross-links, parallel token system) rather than a jarring visual mismatch, unlike Premium (§21) or SFF (§19).

**Two different UI patterns represent the identical "ownership context on this page" concept**: state pages use a tabbed Explore-hub widget; provider pages use a `<details>` accordion. Both ultimately render CHOW rows through shared table classes, so the data layer is consistent even though the surrounding disclosure chrome is not.

---

## 19. Report / SFF findings

Browser-verified live (desktop and mobile, `/report`, `/sff` — local render blocked; production `pbj320.com/sff` used as reference per §22).

**`/rankings` is not a separate page** — it is a 301 redirect to `/report` (`app.py:3948-3951`). Any redesign work targeting "rankings" is targeting `/report`.

**`/report` is a static 8,400-line HTML file, not a Python-rendered page** (`report.html`, ~331KB). `app.py`'s `_serve_report_page_html()` only does SEO-metadata and initial-table-row token replacement on top of it. The entire visual system — a ~4,800-line inline `<style>` block with its own reset, its own `.navbar`/`.nav-link` rules, its own local `--table-*` custom properties — is standalone. It pulls D3 v7 and topojson from a CDN for a US-states choropleth map, a charting dependency used nowhere else in the app. **A direct historical warning against careless cleanup lives in this exact file**: a full "OLD TABLE STRUCTURE" is commented out and explicitly labeled *"PRESERVED FOR REFERENCE (contains critical logic)"* rather than deleted — evidence this codebase has been burned before by removing code that looked redundant.

Live-verified: the `/report` page shares the site's top nav and general dark-blue palette but uses a visibly brighter blue for its own headline treatment than the purple used elsewhere — a subtle, real color drift consistent with its independent `--table-*` token system. The D3 map showed "Loading map…" during this audit's check without fully resolving in the local dev run; not confirmed whether this is a local-only timing/data issue or reproducible in production — flagged as needing a follow-up check before any Phase 1 work touches this surface, not claimed as a confirmed production bug.

**SFF (`/sff*`) is the single most isolated surface in the entire audit** — a fully independent React + Vite + TypeScript + Tailwind single-page app living in `pbj-wrapped/`, not server-rendered HTML. Different language, different build tool, different CSS methodology (Tailwind vs. hand-written inline CSS), different component model. Its own nav CSS is hand-copied from the main site with an explicit code comment admitting the duplication risk (*"Navbar: matches index.html + pbj-site-universal.js shell"*, `pbj-wrapped/src/index.css:5-58`) — a fork that must be manually kept in sync by a human reading that comment, with no shared source of truth.

**Local rendering of `/sff` was blocked during this audit** — the page loaded a blank/near-white screen locally with only benign console warnings ("D3/topojson not loaded yet"), no hard errors. **Production (`pbj320.com/sff`) was checked directly as a reference** and renders correctly: a dark-blue gradient hero, "Special Focus Facilities Program" heading, source attribution line ("CMS SFF Posting (Aug. 2026); CMS PBJ (Q1 2026)"), a state selector, and status filter chips (All/Special Focus Facilities/Candidates/Graduates/Decertified with live counts). This confirms the local blank render is a local build/asset gap (likely `pbj-wrapped/dist` not built in this worktree), **not** a production defect — do not carry the local blank-screen observation forward as a claimed bug; the production screenshot is the valid visual reference for this surface. Visually, production SFF is a third distinct color/theme treatment (dark-blue gradient hero) alongside the app.py pages' near-black theme and `/report`'s bright-blue-on-navy theme.

**The same React app also powers "PBJ Wrapped,"** a separate Spotify-Wrapped-style animated slide deck (SFF is slide #10 of 15 in the USA/State sequences per `SLIDE_ORDER_AND_STYLE.md`) — worth knowing before scoping any SFF consolidation work, since "SFF as a design surface" actually spans two different interaction patterns (a data-table browser and an auto-advancing slide deck) sharing one codebase and build output.

**Recommendation:** treat `/report` and `/sff` as integration decisions, not styling passes (§24) — bringing them into the shared token/component system means either a substantial rewrite (Python-render `/report`, or absorb its D3 map as a standalone component) or a lighter-touch "shared token file consumed by both stacks" approach (CSS custom properties can be read by Tailwind and by a static HTML file equally). Do not attempt this in Phase 1.

---

## 20. Insights findings

**Insights already has the most complete, self-consistent design-token system in the entire codebase** — `insights-theme.css` (3,029 lines) defines 230 `--pbj-*`/`--insights-*` custom properties with a genuine, documented light/dark pair (dark for the hub, light "reading theme" for native article pages, article nav staying dark chrome with light brand text per the file's own header comment). This is the strongest candidate to seed the sitewide token layer proposed in §7, not something to redesign from scratch.

**Native article pages (`/insights/<slug>`) already consume this token system rather than hardcoding raw colors** (`var(--pbj-canvas)`, `var(--pbj-text)`, referenced in the inline overrides at `app.py:4089-4090`) — evidence the pattern of "generate a page in `app.py`, but style it via shared tokens" already works in at least one place in the codebase, which de-risks the token-layer proposal in §7.

**A minor, fixable version-drift finding**: the Insights hub loads `/insights-theme.css?v=7` while the native-article template loads `/insights-theme.css?v=56` — two different cache-busting version strings pointing at the identical physical file from two templates that are supposed to share one theme. Harmless today (same file either way) but worth reconciling as part of any token-layer consolidation to avoid future confusion about which version is "current."

**The NY minimum-staffing report has only one live design**, not three, despite three URLs suggesting variants: `/insights/ny-minimum-staffing/classic` and `/insights/ny-minimum-staffing/press` are both dead 301 redirects to the canonical page, kept alive only to avoid breaking old inbound links. No separate CSS/JS investment exists for the retired "classic" or "press" designs — there is nothing to consolidate here beyond confirming the redirects stay in place.

**`/insights/trends` is a fourth, separate static HTML file** (`insights.html`, distinct from `report.html`), served through the generic static-file path rather than Insights' own token-aware template — not deep-audited in this pass, flagged as a gap for a follow-up if this surface is prioritized.

**PBJPedia (pre-launch, gated behind `PBJPEDIA_PUBLIC=1`)** is a deliberate MediaWiki/Wikipedia skin clone — literal `.mw-body`/`.mw-parser-output`/`.firstHeading` classes and the exact classic Wikipedia color palette (`#0645ad` link blue, `#202122` body text, `#a2a9b1` border gray, `#54595d` muted gray). This is a self-aware design choice, not accidental drift, and shares zero visual DNA with PBJ320's own chrome by intent. **It does have a real internal-duplication problem independent of that choice**: the same ~500-line MediaWiki stylesheet is separately hand-maintained in two places within PBJPedia itself (`generate_dynamic_pbjpedia_page()` vs. a second, independent shell inside the generic `pbjpedia_page()` handler) — worth consolidating into one shared MediaWiki-skin stylesheet before or alongside launch, regardless of what the rest of the redesign does.

---

## 21. Premium — polish/alignment only

Per the brief: Premium's functionality is not being redesigned; classify findings as polish/alignment unless a concrete defect requires more.

**Premium is not one design system with a light/dark variant — it is at least four, and arguably five, unreconciled visual languages sharing only a brand name and, by coincidence, one favicon file** (research file 09; visually confirmed live via browser screenshot of `/premium`):

1. **Marketing hub** (`premium/index.html` + `premium-hub.css` + `premium-site.css`) — Bootstrap 5, Inter/Plus Jakarta Sans (Google Fonts CDN), a light periwinkle-blue background (`#EBF0F8`), indigo/violet accents, its own `pbj-premium-*`/`pbj-audit-*` class namespace. **Confirmed live**: this page is visually a completely different product from the rest of PBJ320 — light theme, different nav treatment, no PBJ320 wordmark styling — the single clearest visual confirmation in this audit of the brief's core concern ("Premium should feel like part of PBJ320 rather than a different website").
2. **Facility dashboard (logged-in)** (`templates/premium_facility_dashboard.html`/`premium_facility_login.html`) — dark slate/indigo theme (`#0f172a`/`#818cf8`), plain system-font stack, generic `.nav`/`.kpi`/`.panel` classes, no relation to the marketing hub's tokens or fonts at all. **This route's registration function (`register_premium_facility_routes`) is never called anywhere in `app.py`** — this surface is currently unreachable/dead code on this branch, a significant finding for scoping: the one Premium surface that most resembles a real logged-in app appears to not actually be servable today.
3. **Sample/export report** (`premium/samples/pbj320-report-demo-335513.html`) — Calibri, Flat-UI blue (`#2980b9`/`#3498db`), print/Word-document layout with `@page` sizing — a downloadable-report mockup dressed as if it came from Microsoft Word, linked from the marketing hub as the primary "see a sample" artifact.
4. **A further ad hoc demo file** (`premium/demo/320365-dashboard-preview.html`) with yet another distinct palette.

**Routing itself is fragile and split across two hosting providers** — `premium_redirect_routes.py`'s own module docstring admits the ambiguity: *"Cloudflare may route `/premium/<CCN>` to Vercel by default... Ensure that path reaches Render, or open the Render service URL directly after deploy."* `premium/vercel.json` contains only a single legacy redirect rule with no active build config.

**One thing is already genuinely consistent and worth explicitly preserving:** the favicon. `premium/pbj_favicon.png` and the root `pbj_favicon.png` are byte-identical (verified by checksum), and every Premium surface actually references the root-served file rather than its own copy — in practice, exactly one favicon is ever served everywhere. This is a small but real anchor point for the identity-alignment pass.

**Recommendation, staying within "polish/alignment, no IA overhaul, no new features":**
- Point the marketing hub (`premium/index.html`) at the shared token layer proposed in §7 once it exists — swap its Bootstrap/Inter/light-blue system for the PBJ320 shell (nav, footer, button, and card conventions) while preserving its existing content and page structure exactly.
- Resolve the sample-report's Calibri/Flat-UI-blue treatment to use the shared table grammar (§8) and typography, since it's the artifact prospective customers actually see.
- Decide deliberately whether the dead facility-dashboard route should be revived (in which case it inherits the shared shell from day one) or formally retired — leaving unreachable code with its own fourth visual language in the tree is a real (if invisible-to-users) maintenance cost.
- Do not touch Premium's IA, its pricing/CTA logic, or the report/dashboard's underlying data views — none of that is in scope per the brief, and nothing in the research surfaced a defect that would require it.

---

## 22. Mobile findings

Verified at 390×844 (iPhone 12/13-class viewport) against the local server for surfaces that render locally; production used as reference for `/sff`.

**Overall: mobile is handled thoughtfully in the core app.py-rendered pages (homepage, provider, state, entity), inconsistently everywhere else — consistent with the code-level table/overlay findings in §8/§10.**

- **Homepage (mobile):** clean single-column stacking, no overflow, good touch targets on the Provider/Chain/State tabs, 16px search input (correctly avoids iOS auto-zoom). No issues found.
- **Provider page (mobile):** metric grid correctly compacts to a 3-column dense layout; the Total Staffing chart renders fully legible with a wrapping legend; good padding throughout. No issues found in the golden-path facility page.
- **State page (mobile):** same metric/Takeaway pattern holds up correctly; **the high-risk facilities table transforms into stacked cards** (facility name, city, star ratings) rather than defaulting to horizontal scroll — a deliberate, content-appropriate mobile technique, not a generic "everything becomes cards" fallback, and worth calling out as a pattern to keep and extend to other tables per §8's recommendation.
- **Entity/Chain page (mobile):** the facilities table uses a **different** mobile strategy than the state page's high-risk table — horizontal scroll with columns visibly cut off at the viewport edge, rather than card-stacking. This is the concrete, live-confirmed instance of the "six distinct, non-shared mobile table strategies" finding from research file 05 — two structurally similar tables (state high-risk list vs. entity facility list) resolve to genuinely different mobile UX today.
- **`/report` (mobile, not fully verified):** research file 04/05 documents extensive `!important`-laden media-query overrides fighting to keep the desktop sticky-corner table behavior working at small widths, with no card fallback — flagged as a likely-weak mobile experience based on code inspection; not independently screenshot-verified in this pass at 390px and should be checked directly before any Phase 1 work touches this surface.
- **SFF (mobile):** not verifiable locally (blank render, §19); production reference at desktop width only was checked in this session — a dedicated mobile pass against production is recommended before scoping SFF work.
- **Premium (mobile, not verified):** out of scope for this pass given the "polish/alignment only" framing and the surface's other priorities (§21); flagged as unverified.

**A note on tooling, not product behavior, encountered during this audit:** the Browser-pane screenshot mechanism used for verification returned solid-black frames for regions of the provider page containing `<canvas>` Chart.js elements scrolled below the first viewport at desktop width, even though direct DOM/pixel inspection (`getImageData`) confirmed the canvases held real rendered chart data. The same charts screenshotted correctly at mobile viewport width and in the first-viewport desktop screenshot. This is assessed as a browser-automation capture artifact specific to this session's tooling, not a PBJ320 rendering defect — recorded here per the brief's "do not claim visual verification you did not perform" instruction, in both directions: the charts were not visually broken, but the mid-page desktop screenshots taken during this session should not be read as confirming their exact pixel appearance either.

**Recommendation:** formalize the state page's card-stack table pattern and the provider page's metric-grid compaction as the two default mobile techniques in the table/metric primitives proposed in §6/§8, and specifically reconcile the entity-page table's mobile behavior to match the state page's (or make a deliberate, documented exception if the entity table's different column set genuinely warrants a different technique).

---

## 23. Future state-edition implications

**`pbj_connecticut_public.py` is not a page generator and has no rendered-page footprint at all** — this reframes the brief's Section 15 question. It is a pure AI-prompt-text module (zero Flask routes, not imported by `app.py`'s page-rendering code) whose one function returns lens-varying Markdown bullets injected into an AI-review-prompt system, not into HTML. A second, independent Connecticut-only string is hardcoded directly inline in `generate_provider_page_html` (`app.py:18295-18300`) for the same AI-prompt purpose. **Neither mechanism touches rendered HTML/CSS/JS** — there is no "Connecticut edition" of any page template today, and no CSS/JS/route fork risk exists in the presentation layer currently.

**Two unrelated systems are both internally called "audience," which matters for anyone reading the code later:** `audience/` (governing `PBJ_AUDIENCE_*` env flags) is a subscription/CTA-copy system — it decides which signup button/copy to show, not what content or evidence depth a visitor sees. The actual per-audience *content*-tailoring mechanism, which is where the Connecticut prompt text plugs in, is `pbj_review_framework.py`'s separate "lens" system (family/journalist/ombudsman/attorney/researcher/advocate/general/operator). If the brief's "progressive evidence disclosure for different user types" goal is meant to eventually mean visually/structurally different page content per visitor type, **no such mechanism exists today** — the only per-audience tailoring anywhere in the repo is prompt-text strings fed to an external AI chat/review flow, not rendered page structure.

**What already supports a config-driven state-module pattern, and should be preserved/built on:** `generate_state_page_html`'s function signature (`app.py:23588`) is already fully parametric — state name, code, data, MACPAC standard, and region info are all passed as arguments, not read from module-level per-state constants. This is the correct architectural precondition for a future state edition and needs no rework. `state_standards.json`/`data/state_standards/state_standards_enriched.{csv,json}` already store MACPAC/regulatory figures per state in one structured, build-time-generated file. `pbj-wrapped/` already produces per-state sliced JSON exports (e.g., `provider_CT_q1.json`) as a build artifact — the data layer already thinks in terms of "slice by state."

**What would currently cause a fork if a real state edition were built today:** despite the parametric signature, actual per-state deviations are implemented as scattered inline conditionals bypassing the data-driven path that was built to carry them — `if state_code_upper == 'NY':` inside `get_macpac_chart_info` (`app.py:15696`, hardcoded MACPAC override, bypassing `state_standards.json` used for every other state) and `if (state_code or '').strip().upper() == 'CT':` inside `generate_provider_page_html` (`app.py:18295-18300`). There is no single "state module" config abstraction these branches could read from instead, even though the state page's own function signature was clearly designed to support exactly that.

**Bottom line, directly answering the brief's Section 23 ask:** the concrete precondition for a future `connecticut.pbj320.com`-style edition to avoid a visual/logic fork is **not** a CSS/component change — it's consolidating the existing scattered `if state_code == 'XX':` branches (currently 2-3 known instances) into the `state_standards.json`-style config layer that the state page generator's signature was already built to accept. This is a code-organization task to flag for the engineering roadmap, not a design-system deliverable, but it should happen *before* any state-edition subdomain work begins, since the shared component/token layer proposed in this audit (§6, §7) will otherwise have nothing state-specific to parameterize against.

---

## 24. CSS migration strategy

**Root cause of the drift (why wholesale cleanup is not viable — per the brief's explicit caution, and confirmed by direct evidence):** PBJ320 grew by two mechanisms simultaneously. First, `app.py` accumulated new inline HTML-string-builder functions per surface over time, each one typically copying the nearest existing pattern and then diverging locally as that surface's needs changed — this produced the three-independent-flag-badge-implementations, five-sort-engine, six-token-namespace pattern documented throughout this report. Second, at least two genuinely separate applications were built and never re-integrated: SFF as a React/Vite/Tailwind rewrite, and Premium as a set of independent static Bootstrap sites. Neither of these is unusual for a project this size and age, but they require different remedies — the first is a within-`app.py` consolidation problem; the second is an integration/architecture decision (§19, §21) that a CSS pass alone cannot solve.

**Direct historical evidence that naive cleanup has broken things before, exactly as the brief anticipates:** `report.html` contains a fully commented-out "OLD TABLE STRUCTURE" explicitly labeled *"PRESERVED FOR REFERENCE (contains critical logic)"* (`report.html:5070-5102`) rather than deleted — a maintainer's own record that removing "duplicate-looking" code on this surface has cost real logic before. Treat this as binding precedent for the whole migration, not just for `report.html`.

**Therefore, per the brief's Section 17 mandate, the migration proceeds in three layers, strictly in this order, with no step touching structural/behavioral CSS:**

1. **Token layer** (§7). Promote `insights-theme.css`'s already-complete `--pbj-*` system to a sitewide `:root` layer; reconcile (not delete) the other five token namespaces by pointing their color *values* at shared tokens where the underlying concept is the same thing, leaving the namespace boundaries (`--chow-*`, `--owner-*`, `--ai-*`, `--ui-*`) in place since they mark real, working subsystems with their own CSS/JS pipelines. De-duplicate the copy-pasted `@font-face` block between `insights-theme.css` and `state-standards.html`.
2. **Shared primitives layer** (§6). Restyle the six already-proven-reusable components (page header, `.pbj-metric` family, Takeaway shell, `.chow-table` foundation + three backports, icon helper, `public-search.js` overlay pattern) to consume the new tokens. This is where the DM Sans/DM Mono/Vollkorn rollout happens — these fonts are already self-hosted and working in Insights/`state-standards.html`; the work is applying them to the primitives, not sourcing them.
3. **Surface-specific exceptions.** Every other surface (provider/state/entity page-generator functions not yet touched, `/report`, SFF, PBJPedia, Premium) is migrated by pointing its *local* color/font/spacing literals at the new tokens where a literal genuinely maps to a token concept, while leaving structural/layout CSS (sticky positioning math, mobile card-stack wiring, D3 map sizing, Tailwind utility classes) untouched. `/report`, SFF, and Premium are explicitly **not** included in this layer for Phase 1 or Phase 2 — see §19/§21's integration-decision framing.

**What must NOT happen, per the brief and this evidence, at any point in the migration:**
- No wholesale deletion of local/route-specific CSS files. Each has been shown to encode real, working (if divergent) behavior — `owner-profile.css`'s 6,838 lines are a functioning parallel design system, not noise.
- No global search-and-replace palette swap. The five independently-defined "brand accent" hex values need to converge on one token *value*, but each call site needs individual verification that the surrounding contrast/hierarchy still works — a blind find-replace risks exactly the kind of regression `report.html`'s preserved-comment warns about.
- No framework migration (React/Next rewrite) for the `app.py`-rendered surfaces. The inline-Python-HTML-string architecture, while unusual, is what makes the `.pbj-metric`/Takeaway/primary-page-generator consolidation tractable — a rewrite would throw away the one part of the system that's already working well.
- No "just centralize everything" pass that pulls SFF (React/Tailwind) or `/report` (static file + D3) into the `app.py` token system in one motion. These require an architecture decision first (§19), not a styling PR.

**Rules for identifying "safe to touch" vs. "leave alone" CSS during implementation** (a heuristic, since a fully automated safe/unsafe classifier is out of scope for this audit): a rule is likely **safe to retarget onto a token** if it sets a color/font/spacing *value* with no accompanying `position`, `display`, `grid-template`, `transform`, or JS-read (`getComputedStyle`, `data-*` attribute paired with a CSS selector) dependency nearby. A rule is likely **structural and should be left alone** if it participates in sticky/fixed positioning, a mobile card-stack transformation (`data-label`/`::before` pairs), a JS-computed layout (chart tick-density branching, popover positioning math), or is inside a block explicitly commented as legacy/preserved. When in doubt, the `report.html` precedent means: leave it alone and flag it for a human decision rather than guessing.

---

## 25. Highest-risk regressions

Ranked by (a) how likely a change is to silently break something a user depends on, and (b) how hard the breakage would be to notice before it reached production.

1. **Table sort correctness.** Five independent sort engines exist across the table inventory (§8); only two reliably sort numeric columns numerically. Any consolidation that swaps in a "unified" sort function without verifying numeric-column behavior on every consuming table risks silently reordering CHOW/facility-list rows lexicographically instead of numerically — a correctness bug, not a visual one, and one a casual visual QA pass would not catch (the table would still *look* sorted).
2. **The state high-risk table's two-column-set discrepancy.** Consolidating the "explore preview" and "legacy accordion" renderings of the state high-risk table (§8, §17) must preserve *both* column sets deliberately (City vs. Census) or make a conscious decision to unify them — accidentally dropping one column set during a "de-duplication" pass would be a real information loss, not a style fix, since this discrepancy is functional, not cosmetic.
3. **Focus/keyboard behavior during overlay consolidation.** §10 documents 15 independent overlay implementations with 3 different focus-management strategies. Replacing any of the zero-JS-native patterns (`<details>`, `<dialog>`) with a "consistent" JS-driven modal would be a net accessibility regression, not an improvement, despite looking like consolidation progress.
4. **Provider-page chart anomaly/benchmark features not silently disappearing during a "shared chart theme" pass.** The provider page's MACPAC benchmark line and anomaly-flag markers (§9) are real product features absent from the state chart; a mechanical "make state and provider charts use the same code" change must add these to the state chart deliberately (a product decision, §32) rather than accidentally removing them from the provider chart to achieve parity.
5. **Ownership's parallel token system (`--owner-*`) and its 6,838-line CSS file.** This is a large, independently-functioning system with its own dual-mobile-DOM table technique (§8 §2) — a hasty token-layer migration that touches this file risks the kind of "supposedly duplicate rules removed → navigation regression" incident the brief specifically warns has happened before in this codebase.
6. **`/report`'s "OLD TABLE STRUCTURE" comment is a live tripwire.** Any future contributor who sees the commented-out block and "cleans it up" without reading the adjacent warning risks reintroducing the exact regression class the brief is worried about.
7. **Nav-block consolidation dropping the Insights-article surface's missing "Owners" link permanently**, if the consolidation copies the *wrong* one of the four existing nav blocks as the new canonical source rather than reconciling them.
8. **Homepage dead-code removal accidentally touching the live "USA" state-filter control**, given the naming collision between the dead mobile-chart script's `#stateSelect` and the live, functional homepage state-filter dropdown (§11, §15) — these are different elements today, but a search-based cleanup that isn't precise about which "USA"/"state" identifiers are live vs. dead could remove the wrong one.

---

## 26. Explicit DO NOT BREAK list

- **The Provider ↔ Chain ↔ State ↔ Owner cross-links that already work** — Provider→State, Provider→Entity, Provider→Owner, Provider→CHOW, State→Provider, State→Owner, Entity→State, Entity→Provider, Owner→Provider (§2, §18). These are the load-bearing edges of the "one connected system" model; none of the visual work in this audit should touch the routes or data plumbing behind them.
- **`_pbj320_high_risk_reasons` as the single source of truth for SFF/SFF-Candidate/Abuse/1-star flags** (`app.py:782-824`) — three different rendering conventions may consolidate, but the underlying CMS-derived logic that decides *which* facilities are flagged must not change as a side effect of a visual pass.
- **The numeric formatting/calculation logic behind every metric** (HPRD, case-mix ratios, contract %, etc.) — this audit found zero design-system reason to touch any calculation code, and the brief explicitly excludes staffing calculations from scope.
- **`pbj_page_sources.py`/`public_source_vintage.py`'s underlying data** (release IDs, official/processing dates, cadence) — the *rendering* of this data may consolidate (§14), but the data registry itself is Tier-1 authority per `AUTHORITY_LADDER.md` and out of design-system scope.
- **Route URLs and redirect behavior** — `/rankings` → `/report`, the NY minimum-staffing `/classic`/`/press` redirects, the `/chow` intentional 404, `/ownership` → `/owners` alias, etc. These are stable public URLs; changing them breaks external links and SEO independent of any visual change.
- **`PBJPEDIA_PUBLIC` gating** — PBJPedia is deliberately not public; nothing in a design-system pass should flip this flag or otherwise expose gated routes.
- **The native `<details>`/`<dialog>` accessibility properties documented in §10** — these must not be "upgraded" to JS-driven equivalents; they are already the most accessible patterns in the codebase.
- **`.chow-table`'s existing cross-page reuse** (owner-facilities table extending it directly, §6/§8) — any table-grammar work should extend this relationship, not break it by giving the two tables independent styling again.
- **The Takeaway's existing content hierarchy and copy logic** — per the brief's Section 9 instruction and confirmed by this audit as a genuinely strong, working pattern (§13); restyle, do not restructure.
- **Ownership's dual-mobile-DOM technique for the owner-facilities table** (`owner_profile_html.py`'s server-rendered card list kept in sync via `syncMobileOrder()`, §8 §2) — a genuinely different, deliberate mechanism from every other mobile table strategy; do not collapse it into the CSS-only `data-label` pattern without confirming it doesn't regress the sort-then-resync behavior.
- **Existing SEO/JSON-LD emission** (`_provider_page_json_ld_scripts`, `_state_page_json_ld_scripts`, `_entity_page_json_ld_scripts`, `_owner_page_json_ld_scripts`, etc.) — untouched by anything in this audit's scope; flag for whoever implements the redesign to verify no template restructuring drops these.

---

## 27. Things explicitly NOT to redesign

Restating and grounding the brief's own constraints against what this audit found, so implementation has no ambiguity:

- **The homepage's utility-first structure** (identity → search → below-fold links) — confirmed live and already matches the brief's intent; only the visual treatment (dark navy → warm paper direction) changes, not the layout or content order.
- **The Provider/Chain/State segmented control and the USA state-filter** — both confirmed fully functional and correctly scoped; restyle only.
- **PBJ Takeaway's content hierarchy, prose-first approach, and single-avatar Phoebe placement** — confirmed working exactly as the brief intends; restyle only.
- **The product architecture (Provider ↔ Chain ↔ State ↔ Owner)** — confirmed sound; the one real gap (Entity↔Owner) is a link to add, not a model to rethink.
- **Table *content*/column differences that are functional** (comparison table vs. listing table vs. diff table vs. rankings table) — §8 is explicit that these are different jobs, not cosmetic drift, and must not be forced into one identical component.
- **Chart analytical meaning** — what's charted, and why, is untouched; only color/theme/grammar consolidation is in scope (§9).
- **Premium's IA, pricing, and functionality** — per the brief, and confirmed by this audit finding no functional defect that would require more than polish/alignment (§21).
- **SFF and `/report`'s underlying data/interaction logic** (the map, the filter chips, the rankings sort) — these are integration/architecture questions (§19), and the interactions themselves are not shown by this audit to be broken.
- **State-specific regulatory content and MACPAC standards data** — the *data layer* (`state_standards.json`) is sound and should be built on, not replaced (§23).
- **CHOW's embedding-not-standalone architecture** — the product decision that CHOW lives contextually on state/owner/provider pages rather than as its own page is intentional (confirmed by the route's own code comment) and not something this audit found reason to revisit.

---

## 28. Recommended migration sequence

1. **Zero-risk deletions** (§29 detail) — dead code identified with high confidence throughout this audit: the homepage's dead mobile-chart script and its 4 unconditional fetches, `index-render.html`, the two orphaned Phoebe PNGs, the dead provider-page badge-vocabulary block, the dead `.pbj-metric-card`/`.pbj-metrics-row` CSS, the dead `_render_state_pbj_high_risk_section()` duplicate table renderer (~300 lines), `report.html`'s commented-out old table (leave commented, do not silently delete without a human confirming the "critical logic" warning no longer applies). Each is independently verified as unreferenced; each can be a separate, small, easily-reviewed PR with no visual-design dependency.
2. **Token layer** (§7, §24 step 1) — generalize `insights-theme.css`'s `--pbj-*` system sitewide; de-duplicate the `@font-face` block.
3. **Phase 1 proof surface: Provider page** (§29-31 detail) — restyle the shared primitives (page header, `.pbj-metric` family, Takeaway shell) against the new tokens on the single strongest, most representative surface, plus the Phoebe artwork swap (§13, a one-line change with sitewide reach through the Takeaway avatar constant).
4. **Extend the same primitives to State and Entity pages** — these already share the underlying generator functions with Provider (§16-18), so this is largely "does the Phase 1 restyle hold up" rather than new work.
5. **Table grammar consolidation** (§8) — backport the three identified improvements onto `.chow-table`, fix the numeric-sort inconsistency, resolve (don't silently drop) the state high-risk table's two-column-set discrepancy, apply the new grammar to entity/owner/CHOW tables.
6. **Overlay/disclosure consolidation** (§10) — reduce to ~3 shared functions (Tooltip/Popover/Modal), re-wire the orphaned Sources dialog (§14) as part of this pass since it's the same underlying `<dialog>` pattern, fix the two concrete accessibility defects found (donor-dashboard hover tooltip, bare-span high-risk tooltip).
7. **Chart grammar consolidation** (§9) — shared theme constants, per-metric fixed color assignment, fix the `insights.html` traffic-light-on-neutral-data instance; treat state-chart feature parity (benchmark line, anomaly markers) as a separate, explicitly-scoped product decision.
8. **Icon consolidation** (§12) — adopt Lucide (or formalize the existing hand-drawn convention), standardize stroke-width, extend `_pbj_overview_icon_html`'s coverage.
9. **Provenance consolidation** (§14) — wire the orphaned Sources dialog to the existing footer trigger, fold the Methodology block and ad hoc modal sentences onto the shared `public_source_vintage.py` data.
10. **Ownership integration** (§18) — restyle `owner-profile.css` onto the shared tokens (a large, careful pass given its size and independent working state), add the Entity→Owner and Owner→State links flagged as the clearest structural gap.
11. **Nav consolidation** (§6, §18) — one shared `render_site_nav()`, fixing the missing Owners link.
12. **Premium polish/alignment pass** (§21) — separately scoped, lower priority given its "polish only" classification and the marketing-hub-vs-dashboard routing ambiguity that should be resolved first.
13. **`/report` and SFF integration decision** (§19) — explicitly deferred; requires an architecture decision (rewrite vs. shared-token-file-only approach) before any styling work begins.

---

## 29. Proposed Phase 1

**The provider page (`/provider/<ccn>`) is the correct, safest Phase 1 proof surface.** It exercises identity/header, Takeaway (including Phoebe), metrics, flags, charts, explanatory copy, provenance, and responsive behavior — every major component family in one page — and it is, by a wide margin, the most internally consistent surface already (confirmed by both static analysis and live browser verification, §16). It also directly answers the brief's own caution not to let homepage aesthetics alone define the system: the homepage has a well-developed Figma reference already, but it's architecturally isolated (a static file, not `app.py`) and comparatively simple (search + links); the provider page is where the actual product's complexity lives and where a restyle proves the token/primitive layer under real conditions.

**What Phase 1 should include:**
- Token layer rollout (§7, §28 step 2) — required prerequisite.
- Restyle (not restructure) of the page header, `.pbj-metric` family (including its two structural variants), and the Takeaway shell against the new tokens.
- Phoebe artwork swap via the single `PBJ_TAKEAWAY_AVATAR_HTML` constant (§13).
- Consolidation of the three flag-badge implementations into one component *as it appears on this page specifically* — the state-table and dead-code variants can follow in a later phase once the pattern is proven here.
- Chart theme restyle (color/font/gridline tokens) on this page's four charts, without touching the anomaly-detection or benchmark-line logic.
- Deletion of the confirmed-dead code local to this page: the ~58-line dead badge block and the dead `.pbj-metric-card` CSS (§16, §29 zero-risk list).

**What Phase 1 should explicitly exclude:** table-grammar consolidation (state/entity/owner tables are a separate, larger effort, §8); overlay/disclosure consolidation beyond what's needed to restyle this page's existing modals in place; the state page's chart-parity question; anything touching `/report`, SFF, Premium, or PBJPedia; the Entity→Owner link (a behavior change, not styling, even though it's a good candidate for a fast-follow).

---

## 30. Exact files Phase 1 would likely touch

Based on the generator functions and shared helpers identified throughout this audit. Listed for planning purposes only — **no files were modified as part of producing this audit.**

- `app.py` — specifically the ranges: `17805-18828` (`generate_provider_page_html`), `19519-19856` (`.pbj-metric` family), `19899-20053` (Takeaway support figures + prose shell), `875-980` (flag-badge constants/helpers), `16173-16935` (provider chart Chart.js config + theme constants), `4715-4718` (`PBJ_TAKEAWAY_AVATAR_HTML`), `18099-18156` (dead badge block, to delete), `11026-11031` + mobile overrides (dead `.pbj-metric-card` CSS, to delete), and wherever `get_pbj_site_layout()`'s shared `<style>` block defines the tokens this page consumes.
- A new shared token file/CSS block (does not exist yet) — likely generalized from `insights-theme.css`'s `:root` block, injected into `get_pbj_site_layout()` or a new dedicated stylesheet route.
- `insights-theme.css` — source of the token values being promoted; itself unchanged except possibly de-duplicating the `@font-face` block against `state-standards.html`.
- `static/brand/fonts/*.ttf` — already-present DM Sans/DM Mono/Vollkorn files; no new assets needed, just broader `@font-face`/`font-family` application.
- New canonical Phoebe artwork asset (to be supplied) replacing the file referenced by `PBJ_TAKEAWAY_AVATAR_HTML`.
- `_scratch/` — any smoke-test HTML/screenshots produced during implementation QA, per `AGENTS.md`.

**Not touched in Phase 1:** `templates/*.html`, `report.html`, `pbj-wrapped/`, `premium/*`, `ownership/*.css`/`*.js`, `chow.css`/`chow.js`, `insights_hub.html`, any route/URL definitions, any calculation/data-loading code.

---

## 31. Phase 1 acceptance criteria

1. **Visual:** the provider page reads as "warm paper / restrained purple / DM Sans+Vollkorn" per the brief's brand direction, verified at desktop 1440px and mobile 390px against a real facility (not just the sample used in this audit).
2. **No content/copy regression:** the Takeaway's prose logic, metric values, flag conditions, and chart data are byte-for-byte identical in *content* before and after — a diff of the rendered text content (not styling) should show zero unintended changes. The methodology/sources text and cross-links must all still resolve to the same URLs.
3. **No calculation regression:** every displayed number (HPRD, case-mix ratios, percentile rank, etc.) matches pre-change output exactly for a fixed sample of facilities across at least 3 states, confirmed via a script or manual diff — not just visual inspection.
4. **Accessibility parity or improvement, never regression:** any overlay/modal touched during the flag-badge or Takeaway restyle must retain (at minimum) its current keyboard/focus behavior; if the native `<details>`/`<dialog>` patterns on this page are touched at all, they must remain native, not become JS-driven.
5. **No route/URL change:** `/provider/<ccn>` and every link the page emits (to `/state/`, `/entity/`, `/owners/`, `/data-sources`, etc.) resolves identically.
6. **Dead code removed cleanly:** the ~58-line dead badge block and the dead `.pbj-metric-card`/`.pbj-metrics-row` CSS are confirmed absent from the rendered page's output with no change to visible markup (since neither was ever rendered).
7. **Chart correctness preserved:** the MACPAC benchmark line and anomaly-flag markers on this page's Total Staffing chart still render and still link to `/data-sources#trend-exclusions` as before — only their color/line-style tokens change.
8. **Performance:** no regression in page weight/load time attributable to the change (e.g., the token file itself should be small; verify it doesn't duplicate the font-face declarations that already exist).
9. **Cross-page consistency check:** since `.pbj-metric`/`render_page_overview_html`/Takeaway are shared with the entity and state pages, confirm those pages still render correctly (even though they are not the Phase 1 target) — a shared-primitive restyle that only checks the provider page risks an undetected regression on the pages that share the same code.

---

## 32. Open product/design decisions for Eric

These are questions the evidence in this audit surfaced but cannot answer on its own — decisions only Eric can make:

1. **Flag-badge vocabulary: unify wording, or keep the density-driven difference deliberate?** The provider Takeaway uses full words ("Abuse," "SFF Candidate"); the state high-risk table uses abbreviations/glyphs ("1★," "⚠"). This audit found this looks like drift, but it may be intentional information-density tuning for a dense table vs. a prose card. Decide before consolidating (§5, §10).
2. **State chart feature parity with provider charts:** should the state-aggregate Total Staffing chart gain the MACPAC benchmark line and anomaly-flag markers that provider charts already have (§9, §17)? This is a real product/analytical decision (what does a state-level benchmark line even mean, given MACPAC standards are typically stated per-facility), not just a styling question.
3. **Entity↔Owner and Owner↔State links:** confirmed as the clearest structural gap (§2, §18). Is adding these two links in scope for the design-system work, or a separate engineering ticket to file alongside it? This audit recommends treating it as a fast-follow immediately after Phase 1, given how small and well-scoped the fix is relative to its impact on the "one connected system" narrative.
4. **`/report` and SFF: rewrite onto the shared system, or keep as integrated-by-token-only satellites?** (§19, §24, §28 step 13). This is the single biggest scope decision in the whole roadmap — a full rewrite of either is a multi-week engineering effort, not a design-system task; a lighter "shared CSS custom-property file both can read" approach is faster but leaves the structural/component-level drift (D3 vs. Chart.js, React vs. Python-string-templates) unresolved.
5. **Premium facility-dashboard route: revive or retire?** It's currently dead code (§21) with its own fourth visual language. Reviving it as a "logged-in Premium workspace" is presumably the long-term intent per the brief's Section 6, but that's a product decision about Premium's roadmap, not something this audit can infer from the code alone.
6. **PBJPedia launch timing relative to the redesign:** it's pre-launch and intentionally skinned as Wikipedia. Should the design-system work include PBJPedia's *internal* CSS de-duplication (the two hand-maintained copies of the same MediaWiki stylesheet, §20) regardless of launch timing, or wait until launch is imminent?
7. **The Insights favicon override:** Insights uses Phoebe as its favicon instead of the standard `pbj_favicon.png` (§13). Keep this as a deliberate distinct-identity marker for Insights, or standardize it? Currently undocumented as a decision either way.
8. **Homepage "USA" naming collision:** no user-facing impact today (the dead script never renders), but worth deciding whether to rename the live state-filter control's internal identifiers to avoid future confusion with the (soon-to-be-deleted) dead script's identical naming, or whether deletion of the dead code alone resolves it sufficiently (§11, §15).
9. **Table missing-value convention:** standardize on one glyph/pattern (this audit's evidence points toward `report.html`'s contextual `<abbr title="...">` as the most informative), or preserve the current em-dash-vs-N/A-vs-tooltip variety as deliberately different treatments for different audiences (a quick dash for a casual browsing table vs. an explained abbreviation for a rankings table)?
10. **CSS migration ownership and sequencing after Phase 1:** given the size of this system (28,200-line `app.py`, 6+ independent CSS environments), does Eric want this audit's proposed 13-step sequence (§28) followed roughly in order, or re-prioritized around a different immediate need (e.g., SFF/`/report` first if those are seen as more urgent than table/overlay consolidation)?

