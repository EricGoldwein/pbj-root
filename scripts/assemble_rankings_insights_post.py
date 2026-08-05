"""Assemble the rankings insights markdown from the table fragment."""
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAG_MINI = ROOT / "insights_posts" / "_rankings_mini_q1_2026.fragment.html"
FRAG_TABLE = ROOT / "insights_posts" / "_rankings_table_q1_2026.fragment.html"
OUT = ROOT / "insights_posts" / "2026-us-nursing-home-staffing-rankings.md"

# Verified from: national_quarterly_metrics.csv CY_Qtr=2026Q1
# facility_count=14487, Total_Nurse_HPRD=3.746459, RN_HPRD=0.624039,
# Nurse_Assistant_HPRD=2.26315 (state_quarterly_metrics facility_count sum also 14487).
NATIONAL_FACILITIES = "14,487"
NATIONAL_TOTAL_HPRD = "3.75"
NATIONAL_RN_HPRD = "0.62"
NATIONAL_AIDE_HPRD = "2.26"
# Publish date = day the post is assembled/shipped.
PUBLISH_DATE = date.today().isoformat()

FRONT = f"""---
slug: 2026-us-nursing-home-staffing-rankings
title: "Q1 2026 U.S. Nursing Home Staffing Data"
description: "PBJ320 nursing home report: facility staffing, state trends, chain data"
published: true
hideFromHub: false
date: {PUBLISH_DATE}
author: Eric Goldwein
previewImage: /insights-rankings-state-hprd-tilemap-q1-2026.svg
showCover: false
readTime: 5 min read
category: pbj
tags: PBJ, HPRD, state rankings, CMS, nursing home staffing, Q1 2026
referenceTitle: "Why Staffing HPRD is the Batting Average of Nursing Homes"
referenceUrl: "https://320insight.substack.com/p/2025-us-nursing-home-staffing-rankings"
---

<div class="insight-context" role="list">
  <div class="insight-context__item" role="listitem">
    <span class="insight-context__icon insight-context__icon--q" aria-hidden="true"></span>
    <span class="insight-context__text">
      <span class="insight-context__header">Quarter</span>
      <span class="insight-context__value">Q1 2026</span>
    </span>
  </div>
  <div class="insight-context__item" role="listitem">
    <span class="insight-context__icon insight-context__icon--sample" aria-hidden="true"></span>
    <span class="insight-context__text">
      <span class="insight-context__header">Sample</span>
      <span class="insight-context__value" title="{NATIONAL_FACILITIES} facilities">
        <span class="insight-context__sample-full">{NATIONAL_FACILITIES} facilities</span>
        <span class="insight-context__sample-short">{NATIONAL_FACILITIES}</span>
      </span>
    </span>
  </div>
  <div class="insight-context__item" role="listitem">
    <span class="insight-context__icon insight-context__icon--metric" aria-hidden="true"></span>
    <span class="insight-context__text">
      <span class="insight-context__header">Metric</span>
      <span class="insight-context__value" title="Hours Per Resident Day (HPRD)">
        <span class="insight-context__metric-full">Hours Per Resident Day (HPRD)</span>
        <span class="insight-context__metric-short">HPRD</span>
      </span>
    </span>
  </div>
  <div class="insight-context__item" role="listitem">
    <span class="insight-context__icon insight-context__icon--src" aria-hidden="true"></span>
    <span class="insight-context__text">
      <span class="insight-context__header">Source</span>
      <span class="insight-context__value">CMS PBJ</span>
    </span>
  </div>
</div>

"""

INTRO = f"""
<p>PBJ stands for Payroll-Based Journal, the federal government’s system for tracking nursing home staffing. Every quarter, CMS publishes daily staffing data for nearly every nursing home in the country. PBJ320 compiles that data back to 2017 so you can see staffing levels and trends at the facility, state, and entity level.</p>

<p>In Q1 2026, CMS reported PBJ data for <strong>{NATIONAL_FACILITIES}</strong> facilities with a nationwide ratio of <strong>{NATIONAL_TOTAL_HPRD} Total Nurse hours per resident day (HPRD)</strong>, including <strong>{NATIONAL_RN_HPRD} RN</strong> and <strong>{NATIONAL_AIDE_HPRD} nurse aide</strong> HPRD.</p>

<p>This page shows how states have fared, not just vs. each other, but vs. themselves over time. <strong><a href="/">Head to PBJ320</a></strong> to dive deeper into facility, state, and entity-level data, and <a href="/sff">click here</a> to see the list of Special Focus Facilities.</p>

<hr class="insight-section-rule" />

"""

GLANCE_OPEN = """
<section class="insight-glance" aria-labelledby="insight-glance-title">
  <h2 id="insight-glance-title" class="insight-data-section__title">State staffing picture, Q1 2026</h2>

"""

GLANCE_CLOSE = """
</section>

"""

# Horizontal map slider below the table (internal-only: hidden publicly; unlock with ?internal=1).
# Click opens an in-page lightbox (not /report). Caption sits above the chart; dots + autoscroll.
MAP_QUARTER = "Q1 2026"


def _map_slide(*, src: str, metric: str, alt: str) -> str:
    full = f"PBJ by state: {metric} ({MAP_QUARTER})"
    return f"""      <figure class="insight-map-slider__slide">
        <button type="button" class="insight-map-slider__open" data-map-src="{src}" data-map-title="{full}" aria-label="Enlarge {full} map">
          <span class="insight-map-slider__caption">
            <span class="insight-map-slider__title">PBJ by state</span>
            <span class="insight-map-slider__metric">{metric} ({MAP_QUARTER})</span>
          </span>
          <img src="{src}" alt="{alt}" width="860" height="560" loading="lazy" decoding="async" />
        </button>
      </figure>
"""


MAP_BLOCK = f"""
<!-- Internal map carousel: kept in markup for LinkedIn/drafts; public page hides it. Unlock: ?internal=1 -->
<div class="insight-map-slider" id="insight-map-carousel" data-insight-map-slider="1" data-pbj-internal="1" hidden>
  <div class="insight-map-slider__viewport">
    <div class="insight-map-slider__track">
{_map_slide(src="/insights-rankings-state-hprd-tilemap-q1-2026.svg?v=3", metric="Total Nurse HPRD", alt=f"{MAP_QUARTER} U.S. states shaded by Total Nurse HPRD.")}
{_map_slide(src="/insights-rankings-state-census-tilemap-q1-2026.svg?v=2", metric="Total avg daily census", alt=f"{MAP_QUARTER} U.S. states shaded by total average daily census.")}
{_map_slide(src="/insights-rankings-state-contract-tilemap-q1-2026.svg?v=1", metric="Contract staff %", alt=f"{MAP_QUARTER} U.S. states shaded by contract staffing percentage.")}
    </div>
  </div>
  <div class="insight-map-slider__dots" role="tablist" aria-label="Map slides"></div>
</div>

"""


def main() -> None:
    mini = FRAG_MINI.read_text(encoding="utf-8")
    table = FRAG_TABLE.read_text(encoding="utf-8")
    # Order: glance (mini movers) → full rankings table (+ note) → map carousel
    OUT.write_text(
        FRONT + INTRO + GLANCE_OPEN + mini + GLANCE_CLOSE + table + MAP_BLOCK,
        encoding="utf-8",
    )
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
