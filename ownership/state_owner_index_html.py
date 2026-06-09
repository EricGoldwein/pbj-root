"""HTML for state ownership index pages (/owners/ny, /owners/ct; draft fl/nj/id)."""
from __future__ import annotations

import html
import json
import random
from typing import Any, Callable

from ownership.chow_display import CHOW_TABLE_INIT_SCRIPT, render_chow_transfer_modal_body
from ownership.chow_lookup import chow_records_for_state, format_chow_date_short_label
from ownership.display_format import format_org_display
from ownership.page_integrations import _facility_link_from_record, _org_link_from_chow_record
from ownership.owner_profile import associate_profile_url, normalize_associate_id
from ownership.state_owner_index import (
    STATE_INDEX_META,
    format_index_owner_name,
    list_state_owner_index_rows,
    state_index_layout_meta,
    state_owner_index_is_draft,
    state_owner_page_context,
)

_TOP_ORGS_LIMIT = 5
_TRY_POOL_LIMIT = 10
_TRY_TOP_TIER = 5
_TRY_SHOW_COUNT = 3
_CHOW_FEED_INITIAL = 3

_CMS_OWNERSHIP_URL = (
    "https://data.cms.gov/provider-characteristics/hospitals-and-other-facilities/"
    "skilled-nursing-facility-all-owners"
)
_CMS_CHOW_URL = (
    "https://data.cms.gov/provider-characteristics/hospitals-and-other-facilities/"
    "skilled-nursing-facility-change-of-ownership"
)
_CMS_PBJ_URL = "https://data.cms.gov/quality-of-care/payroll-based-journal-daily-nurse-staffing"
_FEC_URL = "https://fec.gov/"

_LARGEST_PORTFOLIOS_TITLE: dict[str, tuple[str, str]] = {
    "NY": ("Largest NY portfolios", "Largest New York portfolios"),
    "CT": ("Largest CT portfolios", "Largest Connecticut portfolios"),
    "FL": ("Largest FL portfolios", "Largest Florida portfolios"),
    "NJ": ("Largest NJ portfolios", "Largest New Jersey portfolios"),
    "ID": ("Largest ID portfolios", "Largest Idaho portfolios"),
}


def _render_draft_preview_banner(state_name: str) -> str:
    label = html.escape((state_name or "This state").strip())
    return (
        '<p class="owners-state-draft-banner" role="status">'
        f"<strong>Preview only.</strong> This {label} ownership index is not published on PBJ320 yet."
        "</p>"
    )


def _render_state_outline_inset(state_code: str, state_name: str) -> str:
    """D3 state vector outline (same pattern as state page PBJ takeaway)."""
    state_code_esc = html.escape(state_code, quote=True)
    state_name_esc = html.escape(state_name, quote=True)
    return f"""
    <div class="owners-state-outline" data-state-code="{state_code_esc}" data-state-name="{state_name_esc}" aria-hidden="true">
      <svg class="owners-state-outline-svg" width="100%" height="100%" viewBox="0 0 400 400"></svg>
    </div>
    <script>
    (function(){{
      var wrap = document.querySelector(".owners-state-index .owners-state-outline");
      if (!wrap) return;
      var stateCode = (wrap.getAttribute("data-state-code") || "").toUpperCase();
      var stateName = wrap.getAttribute("data-state-name") || "";
      var svgEl = wrap.querySelector(".owners-state-outline-svg");
      function fallback() {{
        if (svgEl) svgEl.innerHTML = "";
      }}
      function loadScript(src) {{
        return new Promise(function(resolve, reject) {{
          if (document.querySelector('script[src="' + src + '"]')) {{ resolve(); return; }}
          var s = document.createElement("script");
          s.src = src;
          s.onload = resolve;
          s.onerror = reject;
          document.head.appendChild(s);
        }});
      }}
      Promise.all([loadScript("https://d3js.org/d3.v7.min.js"), loadScript("https://cdn.jsdelivr.net/npm/topojson-client@3")]).then(function() {{
        var d3 = window.d3, topojson = window.topojson;
        if (!d3 || !topojson) {{ fallback(); return; }}
        d3.json("https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json").then(function(us) {{
          var states = topojson.feature(us, us.objects.states);
          var feat = states.features.find(function(f) {{ return f.properties.name === stateName; }});
          if (!feat) feat = states.features.find(function(f) {{ return f.properties.abbrev === stateCode; }});
          if (!feat) {{ fallback(); return; }}
          var projection = d3.geoAlbersUsa().fitSize([360, 360], {{ type: "FeatureCollection", features: [feat] }});
          var path = d3.geoPath().projection(projection);
          d3.select(svgEl).selectAll("*").remove();
          d3.select(svgEl).append("g").append("path").datum(feat).attr("d", path)
            .attr("fill", "currentColor").attr("fill-opacity", "0.07")
            .attr("stroke", "currentColor").attr("stroke-opacity", "0.55")
            .attr("stroke-width", "2").attr("stroke-linecap", "round").attr("stroke-linejoin", "round");
        }}).catch(fallback);
      }}).catch(fallback);
    }})();
    </script>
    """


def _compact_updated_label(ctx: dict[str, Any]) -> str:
    """Compact mm/dd/yy date for the index strip (prefer index build date)."""
    import re

    raw = (
        str(ctx.get("index_updated") or "").strip()
        or str(ctx.get("owners_updated") or "").strip()
        or str(ctx.get("chow_updated") or "").strip()
    )
    if not raw:
        return ""
    m = re.match(r"^([A-Za-z]{3,9})\s+(\d{1,2}),\s+(\d{4})$", raw)
    if m:
        months = {
            "jan": 1,
            "feb": 2,
            "mar": 3,
            "apr": 4,
            "may": 5,
            "jun": 6,
            "jul": 7,
            "aug": 8,
            "sep": 9,
            "oct": 10,
            "nov": 11,
            "dec": 12,
        }
        mo = months.get(m.group(1).lower()[:3], 0)
        if mo:
            return f"{mo:02d}/{int(m.group(2)):02d}/{m.group(3)[-2:]}"
    m2 = re.match(r"^(\d{4})-(\d{2})-(\d{2})", raw)
    if m2:
        return f"{m2.group(2)}/{m2.group(3)}/{m2.group(1)[-2:]}"
    if re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", raw):
        mo, day, yr = raw.split("/")
        return f"{int(mo):02d}/{int(day):02d}/{yr[-2:]}"
    return raw


def _render_index_stats_line(ctx: dict[str, Any]) -> str:
    """Compact counts line (below Try chips in search card)."""
    pbj = ctx.get("pbj") or {}
    index_n = int(ctx.get("index_entity_count") or 0)
    prov_n = int(pbj.get("facility_count") or 0)
    updated = _compact_updated_label(ctx)

    dot = ' <span class="owners-state-meta-dot" aria-hidden="true">·</span> '
    parts: list[str] = []
    if index_n:
        parts.append(f"{index_n:,} owners")
    if prov_n:
        parts.append(f"{prov_n:,} providers")
    if updated:
        parts.append(f"Updated {html.escape(updated)}")
    if not parts:
        return ""
    return '<p class="owners-state-search-meta">' + dot.join(parts) + "</p>"


def _render_index_stats_strip(ctx: dict[str, Any]) -> str:
    """Counts below breadcrumb, above page title."""
    stats = _render_index_stats_line(ctx)
    if not stats:
        return ""
    return f'<div class="owners-state-index-stats">{stats}</div>'


def _render_external_data_sources(*, labeled: bool = True) -> str:
    """CMS + FEC outbound links."""
    dot = ' <span class="owners-state-meta-dot" aria-hidden="true">·</span> '
    ext = ' rel="noopener noreferrer" target="_blank"'
    label = '<span class="owners-state-sources-k">Sources:</span> ' if labeled else ""
    return (
        '<p class="owners-state-search-sources">'
        f"{label}"
        f'<a class="owners-state-src-link" href="{html.escape(_CMS_OWNERSHIP_URL, quote=True)}"{ext}>'
        "CMS Ownership</a>"
        f"{dot}"
        f'<a class="owners-state-src-link" href="{html.escape(_CMS_CHOW_URL, quote=True)}"{ext}>'
        "CHOW</a>"
        f"{dot}"
        f'<a class="owners-state-src-link" href="{html.escape(_CMS_PBJ_URL, quote=True)}"{ext}>'
        "PBJ</a>"
        f"{dot}"
        f'<a class="owners-state-src-link" href="{html.escape(_FEC_URL, quote=True)}"{ext}>'
        "FEC</a>"
        "</p>"
    )


def _render_sources_modal() -> str:
    """Mobile sources dialog; desktop uses plain text below About."""
    body = _render_external_data_sources(labeled=False)
    if not body:
        return ""
    return (
        '<dialog class="owners-state-sources-modal" id="ownersStateSourcesModal" '
        'aria-labelledby="ownersStateSourcesModalTitle">'
        '<div class="owners-state-sources-modal-card">'
        '<header class="owners-state-sources-modal-head">'
        '<h2 id="ownersStateSourcesModalTitle">Sources</h2>'
        '<button type="button" class="owners-state-sources-modal-close" '
        'data-owners-sources-close aria-label="Close">×</button>'
        "</header>"
        f'<div class="owners-state-sources-modal-body">{body}</div>'
        "</div></dialog>"
    )


def _render_try_sources_trigger() -> str:
    return (
        '<button type="button" class="owners-state-sources-trigger" '
        'data-owners-sources-open aria-haspopup="dialog">Sources</button>'
    )


def _render_search_card_sources() -> str:
    """CMS + FEC source links for the desktop strip below About."""
    return _render_external_data_sources(labeled=True)


def _try_chip_entry(row: dict[str, Any]) -> dict[str, str] | None:
    """Owner shortcut with canonical /owners/{pac} profile when indexed."""
    pac = normalize_associate_id(str(row.get("associate_id") or ""))
    if len(pac) != 10:
        return None
    display = format_index_owner_name(str(row.get("name") or ""))
    if not display or display == "—":
        return None
    href = str(row.get("profile_url") or "").strip() or associate_profile_url(pac)
    if not href.startswith("/owners/") or href.rstrip("/") == "/owners":
        return None
    return {
        "display_name": display,
        "associate_id": pac,
        "href": href,
        "query": display,
    }


def _chip_key(chip: dict[str, str]) -> str:
    return str(chip.get("associate_id") or chip.get("display_name") or "")


def _pick_try_chips(entries: list[dict[str, str]], count: int) -> list[dict[str, str]]:
    """Random picks from top 10 portfolios; at least one from top 5 when showing 2+."""
    pool = entries[:_TRY_POOL_LIMIT]
    if not pool:
        return []
    want = min(max(1, int(count)), len(pool))
    if want == 1:
        return [random.choice(pool)]

    top_tier = pool[: min(_TRY_TOP_TIER, len(pool))]
    picked: list[dict[str, str]] = []
    used: set[str] = set()

    if want >= 2 and top_tier:
        anchor = random.choice(top_tier)
        picked.append(anchor)
        used.add(_chip_key(anchor))

    rest = [e for e in pool if _chip_key(e) not in used]
    need = want - len(picked)
    if need > 0 and rest:
        picked.extend(random.sample(rest, min(need, len(rest))))

    random.shuffle(picked)
    return picked


def _render_try_chip_link(chip: dict[str, str]) -> str:
    name = html.escape(chip["display_name"])
    href = html.escape(chip["href"])
    label = html.escape(f'View {chip["display_name"]} ownership profile')
    return f'<a class="owners-state-try-chip" href="{href}" aria-label="{label}">{name}</a>'


def _render_panel_tabs(state_code: str) -> str:
    """Mobile tab switcher (portfolios vs recent CHOW); hidden on wide desktop."""
    st = (state_code or "").strip().upper()[:2]
    short, _long = _LARGEST_PORTFOLIOS_TITLE.get(st, ("Largest portfolios", "Largest portfolios"))
    portfolios_label = html.escape(short)
    return (
        '<div class="owners-state-panel-tabs" role="tablist" '
        'aria-label="Ownership index sections">'
        '<button type="button" class="owners-state-panel-tab is-active" role="tab" '
        'id="ownersStateTabPortfolios" aria-selected="true" aria-controls="ownersStatePanelPortfolios" '
        'data-owners-state-tab="portfolios" tabindex="0">'
        f"{portfolios_label}</button>"
        '<button type="button" class="owners-state-panel-tab" role="tab" '
        'id="ownersStateTabChow" aria-selected="false" aria-controls="ownersStatePanelChow" '
        'data-owners-state-tab="chow" tabindex="-1">'
        "Recent ownership changes</button>"
        "</div>"
    )


def _render_largest_portfolios_title(state_code: str) -> str:
    """Short state abbrev in panel header; full state name when layout has room."""
    st = (state_code or "").strip().upper()[:2]
    short, long = _LARGEST_PORTFOLIOS_TITLE.get(st, ("Largest portfolios", "Largest portfolios"))
    return (
        '<h2 id="ownersStateTopHeading" class="owners-state-panel-title">'
        f'<span class="owners-state-panel-title-short">{html.escape(short)}</span>'
        f'<span class="owners-state-panel-title-long">{html.escape(long)}</span>'
        "</h2>"
    )


def _render_state_h1(h1: str) -> str:
    """Two-line mobile stack: '{state} Nursing Home' / 'Ownership Search' (one line on desktop)."""
    suffix = " Ownership Search"
    if h1.endswith(suffix):
        primary = html.escape(h1[: -len(suffix)])
        return (
            '<h1 class="owners-state-h1 owners-state-h1--split">'
            f'<span class="owners-state-h1-primary">{primary}</span>'
            '<span class="owners-state-h1-secondary">Ownership Search</span>'
            "</h1>"
        )
    return f'<h1 class="owners-state-h1">{html.escape(h1)}</h1>'


def _render_try_search_hints(try_pool: list[dict[str, Any]], *, state_slug: str) -> str:
    """Crawlable owner shortcuts; JS may refresh from the same pool JSON."""
    entries: list[dict[str, str]] = []
    for row in try_pool:
        chip = _try_chip_entry(row)
        if chip:
            entries.append(chip)
    if not entries:
        return ""
    entries = entries[:_TRY_POOL_LIMIT]
    shown = _pick_try_chips(entries, _TRY_SHOW_COUNT)
    pool_json = html.escape(json.dumps(entries), quote=True)
    chips_html = "".join(_render_try_chip_link(chip) for chip in shown)
    return (
        f'<div class="owners-state-try" data-try-pool="{pool_json}" '
        f'data-try-count="{_TRY_SHOW_COUNT}" data-try-count-mobile="2" '
        f'data-try-top-tier="{_TRY_TOP_TIER}" '
        f'data-state-slug="{html.escape(state_slug)}">'
        '<span class="owners-state-try-k">Try</span>'
        f'<span class="owners-state-try-chips" data-try-chips aria-live="polite">{chips_html}</span>'
        f"{_render_try_sources_trigger()}"
        "</div>"
    )


def _chow_row_subline(rec: dict[str, Any]) -> str:
    """One-line hint for what the transfer row is about."""
    buyer_raw = str(rec.get("buyer_org_name") or rec.get("buyer_dba_name") or "").strip()
    if buyer_raw:
        buyer = format_org_display(buyer_raw)
        return f"Reported buyer: {html.escape(buyer)}"
    return "CMS change of ownership"


def _render_top_orgs(rows: list[dict[str, Any]], *, state_name: str) -> str:
    if not rows:
        return '<p class="owners-state-empty">No ownership-linked entities in this index yet.</p>'
    count_tip = html.escape(
        f"Distinct CMS-linked facilities in {state_name or 'this state'}",
        quote=True,
    )
    items: list[str] = []
    for i, row in enumerate(rows, start=1):
        name = html.escape(format_index_owner_name(str(row.get("name") or "—")))
        url = html.escape(str(row.get("profile_url") or f"/owners/{row.get('associate_id') or ''}"))
        cnt = int(row.get("facility_count") or 0)
        fac_lbl = "facility" if cnt == 1 else "facilities"
        items.append(
            f'<li class="owners-state-ranked-item">'
            f'<a class="owners-state-ranked-row" href="{url}">'
            f'<span class="owners-state-ranked-n" aria-hidden="true">{i}</span>'
            f'<span class="owners-state-ranked-name">{name}</span>'
            f'<span class="owners-state-ranked-meta" title="{count_tip}" '
            f'aria-label="{count_tip}">{cnt} {fac_lbl}</span>'
            f"</a></li>"
        )
    return f'<ol class="owners-state-ranked">{"".join(items)}</ol>'


def _render_chow_feed(
    state_code: str,
    *,
    state_name: str,
    state_staffing_href: str,
) -> str:
    st = (state_code or "").strip().upper()[:2]
    all_rows = chow_records_for_state(st, limit=0)
    if not all_rows:
        return '<p class="owners-state-empty">No recent ownership changes in the index.</p>'
    rows = all_rows[:_CHOW_FEED_INITIAL]
    items: list[str] = []
    stores: list[str] = []
    for i, rec in enumerate(rows):
        rid = html.escape(str(rec.get("chow_id") or f"row-{i}"), quote=True)
        eff = html.escape(format_chow_date_short_label(str(rec.get("effective_date") or "")) or "—")
        facility = _facility_link_from_record(rec)
        panel_id = f"chow-detail-{rid}"
        subline = _chow_row_subline(rec)
        items.append(
            f'<li class="owners-state-chow-item">'
            f'<span class="owners-state-chow-date">{eff}</span>'
            f'<span class="owners-state-chow-facility">{facility}</span>'
            f'<button type="button" class="owners-state-chow-view chow-view-details" '
            f'data-chow-detail-store="{panel_id}" aria-expanded="false" '
            f'title="Transfer details" aria-label="Transfer details">'
            f'<span class="owners-state-chow-view-label" aria-hidden="true">'
            f'<span class="owners-state-chow-view-line">Transfer</span>'
            f'<span class="owners-state-chow-view-line">details</span>'
            f"</span></button>"
            f'<span class="owners-state-chow-sub">{subline}</span>'
            f"</li>"
        )
        body = render_chow_transfer_modal_body(
            rec,
            org_link_fn=_org_link_from_chow_record,
            facility_link_fn=_facility_link_from_record,
        )
        stores.append(f'<div id="{panel_id}" class="chow-detail-store" hidden>{body}</div>')
    store_html = f'<div class="chow-detail-stores" hidden aria-hidden="true">{"".join(stores)}</div>'
    return (
        f'<ul class="owners-state-chow-list">{"".join(items)}</ul>'
        f"{store_html}{CHOW_TABLE_INIT_SCRIPT}"
    )


def render_state_owner_index_body(
    state_code: str,
    *,
    get_canonical_slug: Callable[[str], str],
    default_browse_limit: int = _TOP_ORGS_LIMIT,
) -> tuple[str, dict[str, str]]:
    """
    Return (body_html, layout_meta) where layout_meta has page_title, meta_description, canonical_path.
    """
    st = (state_code or "").strip().upper()[:2]
    meta = STATE_INDEX_META.get(st) or {}
    layout = state_index_layout_meta(st)
    state_name = layout["state_name"]
    state_slug = layout["state_slug"]
    state_page_slug = meta.get("state_page_slug") or get_canonical_slug(st)
    page_title = layout["page_title"]
    meta_description = layout["meta_description"]
    h1 = layout["h1"]
    subtitle = layout["subtitle"]
    canon = layout["canonical_path"]

    try_pool_rows, index_total = list_state_owner_index_rows(st, limit=_TRY_POOL_LIMIT, offset=0)
    top_rows, _ = list_state_owner_index_rows(st, limit=default_browse_limit, offset=0)
    page_ctx = state_owner_page_context(st)
    top_html = _render_top_orgs(top_rows, state_name=state_name)
    try_search_html = _render_try_search_hints(try_pool_rows, state_slug=state_slug)
    owners_hub_href = "/owners"
    state_staffing_path = f"/state/{state_page_slug}"
    state_staffing_href = html.escape(state_staffing_path)
    chow_body_html = _render_chow_feed(
        st,
        state_name=state_name,
        state_staffing_href=state_staffing_path,
    )
    search_label = html.escape(f"Search {state_name} owners")
    search_placeholder = html.escape("Owner name or 10-digit PAC")
    index_stats_html = _render_index_stats_strip(page_ctx)
    sources_modal_html = _render_sources_modal()
    method_sources_html = _render_search_card_sources()
    draft_banner_html = (
        _render_draft_preview_banner(state_name) if state_owner_index_is_draft(st) else ""
    )

    body = f"""
    <div class="owners-hub owners-state-index" data-state-code="{html.escape(st)}" data-state-slug="{html.escape(state_slug)}" data-state-name="{html.escape(state_name)}">
      {draft_banner_html}
      {_render_state_outline_inset(st, state_name)}
      <nav class="owners-state-crumb" aria-label="Breadcrumb">
        <a href="/">Home</a><span aria-hidden="true"> / </span>
        <a href="{owners_hub_href}">Ownership</a><span aria-hidden="true"> / </span>
        <span>{html.escape(state_name)}</span>
      </nav>
      {index_stats_html}

      <div class="owners-state-intro">
        <header class="owners-state-hero">
          <div class="owners-state-hero-copy">
            {_render_state_h1(h1)}
            <div class="owners-state-hero-rail" aria-hidden="true"></div>
            <p class="owners-state-subtitle">{html.escape(subtitle)}</p>
          </div>
        </header>

        <div class="owners-hub-search owners-state-search-card" role="search" aria-label="{search_label}">
          <div class="owners-state-search-field">
            <label class="visually-hidden" for="ownersHubSearchInput">{search_label}</label>
            <span class="owners-state-search-icon" aria-hidden="true">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3-3"/></svg>
            </span>
            <input type="search" id="ownersHubSearchInput" class="owners-hub-search-input owners-state-search-input"
              placeholder="{search_placeholder}" autocomplete="off" spellcheck="false"
              aria-label="{search_label}"
              aria-autocomplete="list" aria-controls="ownersHubSearchResults" aria-expanded="false">
          </div>
          <ul id="ownersHubSearchResults" class="owners-hub-search-results owners-state-search-results" role="listbox" hidden></ul>
          {try_search_html}
        </div>
      </div>

      {_render_panel_tabs(st)}
      <div class="owners-state-panels">
        <section class="owners-state-panel is-active" id="ownersStatePanelPortfolios" role="tabpanel"
          aria-labelledby="ownersStateTopHeading ownersStateTabPortfolios" data-owners-state-panel="portfolios">
          <header class="owners-state-panel-head owners-state-panel-head--desktop">
            {_render_largest_portfolios_title(st)}
          </header>
          <div class="owners-state-panel-body">
            {top_html}
          </div>
        </section>
        <section class="owners-state-panel owners-state-panel--chow" id="ownersStatePanelChow" role="tabpanel"
          aria-labelledby="ownersStateChowHeading ownersStateTabChow" data-owners-state-panel="chow" hidden>
          <header class="owners-state-panel-head owners-state-panel-head--desktop">
            <h2 id="ownersStateChowHeading" class="owners-state-panel-title">Recent ownership changes</h2>
          </header>
          <div class="owners-state-panel-body">
            {chow_body_html}
          </div>
        </section>
      </div>

      <details class="owners-state-method">
        <summary class="owners-state-method-trigger" aria-expanded="false">
          <span class="owners-state-method-label">About this {html.escape(state_name)} ownership index</span>
          <span class="owners-state-method-chevron" aria-hidden="true"></span>
        </summary>
        <div class="owners-state-method-body">
          <p>
            PBJ320 maps CMS nursing home ownership records to facilities in {html.escape(state_name)}.
            Search by owner or organization name, or by 10-digit CMS associate ID/PAC. Owner profiles show
            affiliated facilities and, when available, related Payroll-Based Journal staffing and CMS rating
            context.
          </p>
          <p>
            CMS ownership records may include legal owners, organizations, managing employees, and other reported
            associations. They do not, by themselves, prove beneficial ownership, operational control, or care
            quality.
          </p>
          <p>
            Recent ownership changes are based on CMS change-of-ownership records. Staffing trends use the same
            public PBJ data used across PBJ320.
          </p>
        </div>
      </details>
      <div class="owners-state-desktop-sources">{method_sources_html}</div>
      {sources_modal_html}
    </div>
    """
    layout_meta = {
        **layout,
        "total": str(index_total),
    }
    return body, layout_meta


def render_state_owner_index_locked_body(state_name: str = "") -> str:
    label = html.escape(state_name or "This state")
    return f"""
    <div class="owners-hub owners-state-index owners-state-index--locked">
      <h1>Ownership index not available</h1>
      <p class="owners-hub-lead">
        Ownership pages are currently available for
        <a href="/owners/ny">New York nursing home ownership search</a> and
        <a href="/owners/ct">Connecticut nursing home ownership search</a> only.
        {label} does not have a published ownership index on PBJ320 yet.
      </p>
      <p class="owners-hub-aside">
        <a href="/owners">Ownership indexes</a> ·
        <a href="/">Facility search</a>
      </p>
    </div>
    """
