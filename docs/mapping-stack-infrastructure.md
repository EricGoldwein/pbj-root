# PBJ mapping stack — infrastructure notes (no migration yet)

**Status:** Inspection + recommendation only. Interactive maps are **not** migrated in this pass.  
**Context article:** [Prompting for interactive web maps in 2026 (Mapbox / DEV)](https://dev.to/mapbox/prompting-for-interactive-web-maps-in-2026-2872) — treat as design guidance (explicit stack, WebGL layers, feature-state, restrained basemap). **Not** an instruction to adopt Mapbox. Strip pitched 3D / cinematic camera for PBJ.

**Verified from (pbj-root, 2026-08-02):** `report.html` (`initializeMap`, D3 + topojson + us-atlas), `insights.html`, `index-render.html`, `state_quarterly_metrics.csv`, `cms_region_quarterly_metrics.csv`, `cms_region_state_mapping.csv`, `provider_info/NH_ProviderInfo_Jul2026.csv` (`Latitude`/`Longitude`), PBJapp grep for map libraries.

**PBJapp mirror + agent workflow:** `PBJapp/docs/MAPPING_STACK_INFRASTRUCTURE.md`, rule `pbj-interactive-maps`, skill `pbj-map-modernization`. Keep inventories aligned when either side’s map surfaces change.

---

## Phase 1 — Inventory

### A. Public site (`pbj-root` / PBJ320)

| Surface | Route / file | Library | Architecture | Geography | Features |
| --- | --- | --- | --- | --- | --- |
| State & regional rankings map | `/report` → `report.html` `#stateMap` | **D3** (CDN) + **topojson.v3** + **us-atlas@3** `states-10m.json` | Server-served static HTML + large inline JS | State polygons (Albers USA SVG path) | Choropleth by Total/RN HPRD, median/ratio modes; hover tooltips; click; mobile tap-outside; **table** is the a11y companion (`state` / `CMS Region` tabs) |
| Insights trends map | `/insights/trends` → `insights.html` | Same D3/topojson/us-atlas | Static HTML + JS | State polygons | Historical / trends choropleth |
| Homepage mini-map | `index-render.html` | D3 geoAlbersUsa | Static HTML | State outline | Decorative / summary |
| State page silhouette | `app.py` / ownership HTML | D3 fitSize on single state feature | Inline in rendered HTML | One state polygon | Non-interactive decoration |
| NY / CT / etc. minimum staffing | `insights-ny-minimum-staffing.html` (+ PBJapp report HTML) | Custom point/canvas-style facility viz | Dedicated report pages | Facility points (not national Mapbox) | Explicitly **avoids** coarse county choropleth |
| Cost-report / rankings **static** maps | `insights-*-tilemap-*.svg`, build scripts | Generated SVG tiles / bars | Markdown/HTML `<figure>` | State tiles; CMS region bars | Insights copy only — not interactive |

**Not present in pbj-root:** Mapbox GL JS, MapLibre, Leaflet, Mapbox tokens, hosted vector tilesets for facilities.

**Data for maps (already PBJ-owned):**

| Layer | Source | Format | Approx. size |
| --- | --- | --- | --- |
| State HPRD | `state_quarterly_metrics.csv` (+ `/report` fetch) | CSV → in-memory JS objects | 51–52 areas / quarter |
| CMS region HPRD | `cms_region_quarterly_metrics.csv` | CSV | 10 regions / quarter |
| Region ↔ state | `cms_region_state_mapping.csv` | CSV | static join |
| State boundaries | CDN `us-atlas@3/states-10m.json` | TopoJSON | ~10m US states |
| Facility coordinates | CMS Provider Info `Latitude` / `Longitude` | CSV columns | **14,693 / 14,693** both non-null (Jul 2026 NH file) |
| Facility staffing | `facility_quarterly_metrics*.csv` / provider indexes | CSV / SQLite | ~15k facilities / quarter |

**APIs:** Mapbox does **not** supply PBJ metrics. PBJ already has the substantive datasets. There is **no** facility GeoJSON national map API today; rankings maps join metrics to us-atlas polygons client-side. Mapbox basemap/geocoding/tiles would be optional delivery layers only.

**Interaction gaps (current `/report`):** SVG choropleth is fine at state count (~52). No WebGL facility layer. Color-only encoding. Tooltips are mouse/touch oriented. Alaska/PR often excluded from color scale (documented in JS). Region view is primarily **table**, not a second choropleth. No Mapbox-style feature-state; selection is loosely coupled to table highlight.

### B. PBJ Cursor / pipeline app (`PBJapp`)

| Surface | Library | Notes |
| --- | --- | --- |
| `pbj_playground.html` | D3 + topojson + us-atlas (same pattern as `/report`) | Internal playground |
| Admin / citations dashboards | Plotly `px.choropleth` | Admin analytics, not public PBJ320 |
| State minimum staffing report HTML | Facility point viz (shared philosophy with root insights) | Deliberately not county choropleth |
| CT planning regions | GeoJSON prep scripts | Local planning geometry |

**Shared vs separate:** Public rankings maps and PBJapp playground **share a pattern** (D3 + us-atlas) but **not a shared package**. Deliberately separate deployables; do not force a monorepo map package until a facility WebGL map exists in both.

### C. Tokens / secrets

No Mapbox (or MapLibre) token in either environment for maps today. Do not add tokens until Approach C/D is chosen.

---

## Phase 2 — Recommendation

**Chosen approach: A — Keep the existing D3/topojson stack for state & CMS-region views; improve styling and interaction in place.**

Optional later (not now): **D (MapLibre)** or **C (Mapbox GL)** only if/when shipping a **national facility point map** (~15k points) where HTML markers or SVG circles would fail — then GeoJSON source + circle/cluster layers, PBJ metrics as properties, CMS lat/lon already present.

| Criterion | Assessment |
| --- | --- |
| Implementation risk | **Low** for A; **High** for C/D on `/report` rewrite |
| Bundle / page load | D3+topojson already paid; Mapbox/MapLibre adds ~200KB+ and tile network |
| Traffic / map-load cost | A: CDN tiles for us-atlas only; C: Mapbox billable map loads |
| Tokens / accounts | A: none; C: Mapbox account + restricted public token |
| Facility performance | N/A for current state map; 15k GeoJSON is usually enough before custom tilesets |
| Mobile | Existing SVG + table companion; improve sheet/tooltip, don’t invent 3D |
| Accessibility | Keep **table / rankings** as primary; map is visual |
| Maintenance | One familiar stack on public site |
| State/county polygons | us-atlas (and Census TIGER later) sufficient; Mapbox not required |
| Improve without migration? | **Yes** for state/region choropleths |

**Do not** ingest Mapbox basemap POIs/roads into PBJ databases. Basemap stays hosted tiles if ever adopted. **Do not** cinematic pitch/3D buildings for staffing data.

---

## Infrastructure artifacts (this pass)

| Artifact | Role |
| --- | --- |
| This doc | Inventory + recommendation |
| `/data-sources#maps` | Public methods pointer |
| `/premium/methods` maps blurb | Premium methods pointer |
| `scripts/build_insights_rankings_maps_q1_2026.py` | Static SVG builder for insights draft |
| `insights-rankings-state-hprd-tilemap-q1-2026.svg` | State tile map for draft post |
| `insights-rankings-cms-region-hprd-q1-2026.svg` | CMS region bar “map” for draft post |
| `insights_posts/2026-us-nursing-home-staffing-rankings.md` | Unpublished draft with maps + tables |

**Explicitly not done:** Mapbox/MapLibre install, token setup, `/report` rewrite, facility GeoJSON endpoint, deploy, commit, push.

---

## Next implementation slice (when approved)

1. Document interaction states on `/report` (default / hover / selected / missing) without changing metrics.  
2. Optional: small SVG region schematic synced to region table tab.  
3. Only then evaluate MapLibre for a **facility** map product with clustering.
