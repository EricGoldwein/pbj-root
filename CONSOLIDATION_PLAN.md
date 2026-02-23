# Markdown Consolidation Plan (DESIGN ONLY — NOT EXECUTED)

**Status:** Plan proposed. Execution (STEP 4) pending internal approval.

---

## STEP 1 — INVENTORY OF ALL MARKDOWN

| File Name | Primary Purpose | Contains Rules? | References JSON/CSV/YAML? | Is It Duplicative? |
|-----------|-----------------|-----------------|---------------------------|--------------------|
| `donor/OWNERSHIP_PROVIDER_SEARCH_FIXES.md` | notes / discovery | No | Yes (CSV, column names) | No |
| `donor/EXAMPLES_FEC_DOCQUERY_URLS.md` | notes / discovery | Yes (docquery path rules) | Yes | No |
| `donor/DONOR_FEC_LINKS.md` | explanation | Yes (F13→f132, sa/ALL) | Yes (CSV) | Partial (overlaps EXAMPLES) |
| `RENDER_DEPLOY.md` | notes / explanation | Yes (health check path) | Yes (render.yaml) | Partial (overlaps DEPLOY_AND_RUN) |
| `DEPLOY_AND_RUN.md` | explanation / how-to | Yes (health check, commands) | Yes | Partial |
| `donor/DONOR_RUN.md` | how-to / notes | No | Yes (CSV paths) | No |
| `donor/FEC data/README.md` | explanation / how-to | Yes (build commands, data priority) | Yes (parquet, CSV, manifest) | No |
| `donor/ROOT_CAUSE_ANALYSIS.md` | discovery / notes | No | No | No |
| `donor/data/fec_committee_master/README.md` | explanation / how-to | Yes (cycle naming cm26=2025–2026) | Yes (CSV) | Partial (overlaps DONOR_FEC_LINKS) |
| `donor/DONATION_SOURCE_TRACEBACK.md` | discovery / notes | No | Yes (API) | No |
| `Q3_2025_UPDATE_CHECKLIST.md` | temporary / process | No | Yes (CSV, JSON, scripts) | No |
| `PBJPedia/pbjpedia-state-standards.md` | explanation | Yes (HPRD thresholds, federal baseline) | Yes (state links) | No |
| `PBJPedia/pbjpedia-overview.md` | explanation | Yes (what PBJ measures) | Yes | No |
| `PBJPedia/pbjpedia-non-nursing-staff.md` | explanation | Yes (job codes 1–5+) | Yes | No |
| `PBJPedia/pbjpedia-history.md` | explanation | Yes (45-day deadline) | Yes | No |
| `PBJPedia/pbjpedia-methodology.md` | explanation | Yes (aggregation, exclusion) | Yes | No |
| `PBJPedia/pbjpedia-metrics.md` | explanation | Yes (HPRD formula, definitions) | Yes | No |
| `PBJPedia/pbjpedia-data-limitations.md` | explanation | Yes (caveats) | No | No |
| `MOBILE_PBJPEDIA_PROMPT.md` | temporary / Cursor | No | Yes (app.py, markdown) | No |
| `LINKEDIN_VIDEO_INSTRUCTIONS.md` | how-to | No | Yes (HTML) | No |
| `pbj-wrapped/SETUP.md` | how-to | No | Yes (CSV paths) | Partial |
| `pbj-wrapped/SPEED_UP.md` | how-to | No | Yes (CSV→JSON) | No |
| `pbj-wrapped/README.md` | explanation / how-to | No | Yes (CSV) | Partial |
| `pbj-wrapped/QUICK_START.md` | how-to | No | Yes (CSV) | Partial |
| `SFF_HPRD_ANALYSIS_SUMMARY.md` | discovery / analysis | No | Yes (CMS, PBJ) | No |
| `SERVER_RESTART_REQUIRED.md` | temporary / notes | No | Yes (JSON, CSV routes) | Partial |
| `ROUTING_FIXES.md` | notes / discovery | Yes (route order) | Yes (app.py) | Partial |
| `PRUITTHEALTH_CONSULTING_SERVICES_INC_contributions.md` | discovery / report | No | Yes (FEC) | No |
| `ROUTING_BREAKDOWN.md` | architecture / explanation | No | Yes (app.py, routes) | Partial |
| `pbj-wrapped/SLIDE_ORDER_AND_STYLE.md` | architecture / style | Yes (slide order, durations) | No | No |
| `pbj-wrapped/COPY_DATA_FILES.md` | how-to | No | Yes (CSV) | Partial |
| `wrapped-template/TEMPLATE_README.md` | explanation | No | Yes (config) | Partial |
| `wrapped-template/README.md` | explanation | No | Yes | Partial |
| `wrapped-template/EXAMPLE_CUSTOMIZATION.md` | explanation | No | Yes | No |
| `wrapped-template/TEMPLATE_CUSTOMIZATION.md` | how-to | No | Yes | No |
| `wrapped-template/TEMPLATE_INDEX.md` | reference | No | No | No |
| `CALCULATION_DOCUMENTATION.md` | explanation | Yes (data sources, quarter match) | Yes (CSV) | No |
| `CALCULATION_ANALYSIS.md` | discovery / analysis | Yes (median calc, issues) | Yes (report.html) | Partial |
| `FIXES_SUMMARY.md` | notes / discovery | Yes (fix descriptions) | Yes (report.html) | Partial |

---

## STEP 2 — CLASSIFICATION (LINE-LEVEL)

### A) AUTHORITATIVE RULES (must be preserved verbatim; consider pbj-contract or JSON/CSV)

| File | Content Type | Examples |
|------|--------------|----------|
| `donor/EXAMPLES_FEC_DOCQUERY_URLS.md` | docquery path rules | F13→f132, others→sa/ALL; file_number from schedule_a |
| `donor/DONOR_FEC_LINKS.md` | FEC docquery logic | FORM_TYPES_USE_SCHEDULE_13A, path rules |
| `donor/data/fec_committee_master/README.md` | cycle naming | cm26=2025–2026 |
| `PBJPedia/pbjpedia-methodology.md` | CMS rules | 45-day deadline; 1.5–12 HPRD, 5.25 nurse aide exclusion |
| `PBJPedia/pbjpedia-metrics.md` | HPRD definitions | HPRD formula; Total Nurse HPRD includes DON, RN Admin, … |
| `PBJPedia/pbjpedia-state-standards.md` | policy thresholds | 0.3 federal, 4.1 recommended, state variation |
| `PBJPedia/pbjpedia-non-nursing-staff.md` | job code definitions | Job Code 1=Administrator, 2=Medical Director, … |
| `PBJPedia/pbjpedia-data-limitations.md` | caveats | paid hours only, no wages, quarterly exclusions |
| `CALCULATION_DOCUMENTATION.md` | data source rules | quarter match, weighted median method |
| `CALCULATION_ANALYSIS.md` | median calc description | calculateMedian, facility-level vs state-level |
| `FIXES_SUMMARY.md` | fix descriptions | weighted median, exclude admin/DON |
| `pbj-wrapped/SLIDE_ORDER_AND_STYLE.md` | slide order, durations | USA 15 slides, State 15 slides, durations |
| `RENDER_DEPLOY.md` | health check rule | Health Check Path = `/health` |
| `DEPLOY_AND_RUN.md` | deploy rules | start command, health check |
| `ROUTING_FIXES.md` | route order | JSON/image/CSV before state_slug |

### B) DERIVED EXPLANATIONS (explanations of code/data; may be merged)

| File | Content Type |
|------|--------------|
| `donor/OWNERSHIP_PROVIDER_SEARCH_FIXES.md` | Root cause, fix description |
| `donor/DONOR_FEC_LINKS.md` | Committee master, docquery path explanation |
| `donor/ROOT_CAUSE_ANALYSIS.md` | False attribution analysis |
| `donor/DONATION_SOURCE_TRACEBACK.md` | Data flow traceback |
| `PBJPedia/*` | PBJ system explanation, methodology |
| `CALCULATION_DOCUMENTATION.md` | Data flow, computed vs aggregated |
| `CALCULATION_ANALYSIS.md` | Median calculation walkthrough |
| `ROUTING_BREAKDOWN.md` | Routing architecture |
| `SFF_HPRD_ANALYSIS_SUMMARY.md` | SFF analysis findings |
| `pbj-wrapped/README.md` | Wrapped app overview |
| `wrapped-template/*` | Template structure, customization |

### C) PROCESS NOTES (inventories, TODOs, migration; may be archived)

| File | Content Type |
|------|--------------|
| `Q3_2025_UPDATE_CHECKLIST.md` | Checklist, file list, scripts |
| `MOBILE_PBJPEDIA_PROMPT.md` | Cursor plan for mobile |
| `SERVER_RESTART_REQUIRED.md` | Restart instructions |
| `donor/DONOR_RUN.md` | Pipeline run steps |
| `donor/FEC data/README.md` | Build steps, data priority |
| `pbj-wrapped/COPY_DATA_FILES.md` | File copy instructions |
| `pbj-wrapped/SPEED_UP.md` | Preprocess instructions |

### D) CONTEXT / INTENT (why system exists; one file only)

| File | Content Type |
|------|--------------|
| `PBJPedia/pbjpedia-overview.md` | Why PBJ exists, what it measures |
| `LINKEDIN_VIDEO_INSTRUCTIONS.md` | Why/how create video |
| `wrapped-template/README.md` | Template purpose |

---

## STEP 3 — CONSOLIDATION PLAN (NO EXECUTION)

### Proposed Structure

1. **Retained:** `ARCHITECTURE.md` — Single retained markdown for system context, routing, and high-level architecture (merged from DEPLOY_AND_RUN, ROUTING_BREAKDOWN, RENDER_DEPLOY, pbj-wrapped/README).
2. **Archive:** `_archive_notes.md` — Process notes, checklists, Cursor plans, discovery notes (verbatim).
3. **Rules:** AUTHORITATIVE RULES moved verbatim to:
   - `pbj-contract/` YAML (definitions, formatting, quarter_rules, disclaimers) where shared.
   - Existing JSON/CSV (e.g., fec_committee_master_columns.csv) or new config files where env-specific.

### Per-File Actions

| Original File | Action | Target File | Justification |
|---------------|--------|-------------|---------------|
| `donor/OWNERSHIP_PROVIDER_SEARCH_FIXES.md` | Archive | `_archive_notes.md` | Discovery/notes; no rules to promote |
| `donor/EXAMPLES_FEC_DOCQUERY_URLS.md` | Archive | `_archive_notes.md` | FEC docquery rules; keep for reference. FLAG: docquery path rules may be authoritative—consider fec_api_client.py or config |
| `donor/DONOR_FEC_LINKS.md` | Archive | `_archive_notes.md` | FEC links explanation; rules overlap EXAMPLES |
| `RENDER_DEPLOY.md` | Merge | `ARCHITECTURE.md` | Health check rule; merge into deploy section |
| `DEPLOY_AND_RUN.md` | Retain | `ARCHITECTURE.md` (or keep as README) | Primary deploy doc; merge with RENDER_DEPLOY |
| `donor/DONOR_RUN.md` | Archive | `_archive_notes.md` | Process steps |
| `donor/FEC data/README.md` | Retain | (keep in place) | Location-specific; consumed by donor pipeline |
| `donor/ROOT_CAUSE_ANALYSIS.md` | Archive | `_archive_notes.md` | Discovery |
| `donor/data/fec_committee_master/README.md` | Retain | (keep in place) | Location-specific; data folder README |
| `donor/DONATION_SOURCE_TRACEBACK.md` | Archive | `_archive_notes.md` | Discovery |
| `Q3_2025_UPDATE_CHECKLIST.md` | Archive | `_archive_notes.md` | Temporary checklist |
| `PBJPedia/pbjpedia-*.md` | Retain | (keep in place) | Public-facing reference; source for pbj-contract. DO NOT merge—served as pages |
| `MOBILE_PBJPEDIA_PROMPT.md` | Archive | `_archive_notes.md` | Cursor plan |
| `LINKEDIN_VIDEO_INSTRUCTIONS.md` | Archive | `_archive_notes.md` | How-to; one-off |
| `pbj-wrapped/SETUP.md` | Merge | `pbj-wrapped/README.md` | Redundant with README |
| `pbj-wrapped/SPEED_UP.md` | Merge | `pbj-wrapped/README.md` | Add preprocess section |
| `pbj-wrapped/README.md` | Retain | `pbj-wrapped/README.md` | Primary wrapped doc |
| `pbj-wrapped/QUICK_START.md` | Merge | `pbj-wrapped/README.md` | Redundant |
| `SFF_HPRD_ANALYSIS_SUMMARY.md` | Archive | `_archive_notes.md` | Analysis output |
| `SERVER_RESTART_REQUIRED.md` | Archive | `_archive_notes.md` | Temporary |
| `ROUTING_FIXES.md` | Archive | `_archive_notes.md` | Discovery; route rules in code |
| `PRUITTHEALTH_CONSULTING_SERVICES_INC_contributions.md` | Archive | `_archive_notes.md` | Report output |
| `ROUTING_BREAKDOWN.md` | Merge | `ARCHITECTURE.md` | Routing architecture |
| `pbj-wrapped/SLIDE_ORDER_AND_STYLE.md` | Retain | (keep in place) | FLAG: Contains authoritative slide order/durations; do not condense |
| `pbj-wrapped/COPY_DATA_FILES.md` | Merge | `pbj-wrapped/README.md` | Data setup |
| `wrapped-template/README.md` | Retain | (keep in place) | Template entry |
| `wrapped-template/TEMPLATE_README.md` | Retain | (keep in place) | Template guide |
| `wrapped-template/EXAMPLE_CUSTOMIZATION.md` | Retain | (keep in place) | Template example |
| `wrapped-template/TEMPLATE_CUSTOMIZATION.md` | Retain | (keep in place) | Template how-to |
| `wrapped-template/TEMPLATE_INDEX.md` | Retain | (keep in place) | Template index |
| `CALCULATION_DOCUMENTATION.md` | Retain | (keep in place) | FLAG: Authoritative for report.html logic; do not condense |
| `CALCULATION_ANALYSIS.md` | Archive | `_archive_notes.md` | Discovery; overlaps CALCULATION_DOCUMENTATION |
| `FIXES_SUMMARY.md` | Archive | `_archive_notes.md` | Fix notes |

### Authority Rules (DO NOT condense)

- **PBJPedia/** — Served as public pages; source for pbj-contract. Keep verbatim.
- **CALCULATION_DOCUMENTATION.md** — Defines data sources, quarter match, median method.
- **pbj-wrapped/SLIDE_ORDER_AND_STYLE.md** — Defines slide order and durations.
- **donor/EXAMPLES_FEC_DOCQUERY_URLS.md** — docquery path rules (F13→f132, sa/ALL).

### STOP CONDITIONS

- If any content seems even possibly authoritative, DO NOT condense. Flagged above.
- PBJPedia pages: RETAIN as-is; they are the canonical public reference.
- CALCULATION_DOCUMENTATION, SLIDE_ORDER_AND_STYLE: RETAIN as-is.

---

## STEP 4 — EXECUTION (PENDING APPROVAL)

**DO NOT execute until plan is approved internally.**

When approved:
1. Create `ARCHITECTURE.md` with merged content from DEPLOY_AND_RUN, RENDER_DEPLOY, ROUTING_BREAKDOWN.
2. Create `_archive_notes.md` with verbatim content from archived files, section headers, and top comment: "NON-AUTHORITATIVE — retained for history".
3. Merge pbj-wrapped SETUP, QUICK_START, SPEED_UP, COPY_DATA_FILES into pbj-wrapped/README.md.
4. Do NOT delete original files unless explicitly instructed.
5. Do NOT change wording or infer meaning.
