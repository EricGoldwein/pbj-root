"""HTML generation for /geo/<state_slug> geographic intelligence pages."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

_GEO_SHELL_CSS_PATH = Path(__file__).with_name("geo_intelligence_v2_shell.css")


def _load_geo_shell_css() -> str:
    if _GEO_SHELL_CSS_PATH.is_file():
        return _GEO_SHELL_CSS_PATH.read_text(encoding="utf-8")
    return ""


def _geo_intelligence_assets_head() -> str:
    return (
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
        '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">'
    )


# Legacy alias — v2 shell CSS loaded from geo_intelligence_v2_shell.css
GEO_PAGE_EXTRA_CSS = _load_geo_shell_css()

_GEO_MODAL_BINDER_JS = """
(function(){
  document.querySelectorAll('.pbj-casemix-modal').forEach(function(modal){
    var mid = modal.id;
    if (!mid) return;
    var btn = document.querySelector('[aria-controls="'+mid+'"]');
    var closeBtn = modal.querySelector('.pbj-casemix-modal-close');
    function openM(){ modal.setAttribute('aria-hidden','false'); document.body.classList.add('pbj-ai-beta-modal-open'); }
    function closeM(){ modal.setAttribute('aria-hidden','true'); document.body.classList.remove('pbj-ai-beta-modal-open'); }
    if (btn) btn.addEventListener('click', function(e){ e.preventDefault(); openM(); });
    if (closeBtn) closeBtn.addEventListener('click', closeM);
    modal.addEventListener('click', function(e){ if (e.target === modal) closeM(); });
    document.addEventListener('keydown', function(e){
      if (e.key === 'Escape' && modal.getAttribute('aria-hidden') === 'false') closeM();
    });
  });
  function applyRegionView(regionKey) {
    var key = (regionKey || '').trim();
    document.querySelectorAll('.pbj-geo-statewide-view').forEach(function(el) {
      el.classList.toggle('pbj-geo-view-hidden', !!key);
    });
    document.querySelectorAll('.pbj-geo-region-workspace').forEach(function(el) {
      var match = el.getAttribute('data-pbj-geo-region-key') === key;
      el.classList.toggle('pbj-geo-view-hidden', !match);
      el.hidden = !match;
    });
    var select = document.getElementById('pbjGeoRegionSelect');
    if (select && select.value !== key) select.value = key;
    var hidden = document.getElementById('pbjGeoQuarterRegionHidden');
    if (hidden) hidden.value = key;
    var search = document.getElementById('pbjGeoRegionSearch');
    if (search && select) {
      if (key) {
        var opt = select.querySelector('option[value="'+key.replace(/"/g, '')+'"]');
        search.value = opt ? (opt.textContent || '').trim() : '';
      } else {
        search.value = '';
      }
    }
    var params = new URLSearchParams(window.location.search);
    if (key) params.set('region', key); else params.delete('region');
    var qsel = document.getElementById('pbjGeoQuarterSelect');
    if (qsel && qsel.value) params.set('quarter', qsel.value);
    else params.delete('quarter');
    var qs = params.toString();
    var url = window.location.pathname + (qs ? '?' + qs : '');
    if (window.history && window.history.replaceState) {
      window.history.replaceState({}, '', url);
    }
    if (key) {
      var ws = document.querySelector('.pbj-geo-region-workspace[data-pbj-geo-region-key="'+key.replace(/"/g, '')+'"]');
      if (ws) ws.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }
  document.querySelectorAll('.pbj-geo-back-statewide').forEach(function(btn) {
    btn.addEventListener('click', function(e) { e.preventDefault(); applyRegionView(''); });
  });
  var select = document.getElementById('pbjGeoRegionSelect');
  var search = document.getElementById('pbjGeoRegionSearch');
  if (select) {
    select.addEventListener('change', function() { applyRegionView(select.value); });
    var initial = select.value || '';
    if (!initial && location.hash && location.hash.indexOf('#region-') === 0) {
      initial = location.hash.slice(8);
      select.value = initial;
    }
    applyRegionView(initial);
  }
  if (search && select) {
    search.addEventListener('input', function() {
      var q = (search.value || '').trim().toLowerCase();
      if (!q) return;
      for (var i = 0; i < select.options.length; i++) {
        var opt = select.options[i];
        if (!opt.value) continue;
        var lbl = (opt.textContent || '').toLowerCase();
        if (lbl.indexOf(q) >= 0) {
          select.value = opt.value;
          applyRegionView(opt.value);
          break;
        }
      }
    });
    search.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        var q = (search.value || '').trim().toLowerCase();
        if (!q) { applyRegionView(''); return; }
        for (var i = 0; i < select.options.length; i++) {
          var opt = select.options[i];
          if (!opt.value) continue;
          if ((opt.textContent || '').toLowerCase().indexOf(q) >= 0) {
            select.value = opt.value;
            applyRegionView(opt.value);
            break;
          }
        }
      }
    });
  }
  var qform = document.getElementById('pbjGeoQuarterForm');
  if (qform) {
    qform.addEventListener('submit', function() {
      var hidden = document.getElementById('pbjGeoQuarterRegionHidden');
      var sel = document.getElementById('pbjGeoRegionSelect');
      if (hidden && sel) hidden.value = sel.value || '';
    });
  }
})();
"""


def _fmt_hprd(value: Any) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    if v <= 0:
        return "—"
    return f"{v:.2f}"


def _fmt_percentile(value: Any) -> str:
    """Format within-state percentile rank for user-facing tables."""
    try:
        p = float(value)
    except (TypeError, ValueError):
        return "—"
    if p <= 0 or p > 100:
        return "—"
    n = int(round(p))
    n = max(1, min(100, n))
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _staffing_review_flag(percentile: Any, hprd: Any) -> str:
    """Compact PBJ320 review flag for lowest within-state staffing ranks."""
    try:
        p = float(percentile)
        h = float(hprd)
    except (TypeError, ValueError):
        return ""
    if h <= 0 or p <= 0:
        return ""
    if p <= 10:
        return (
            '<span class="pbj-geo-review-flag pbj-geo-review-flag--critical" '
            'title="Lowest within-state total nurse HPRD for this quarter">'
            "Review</span>"
        )
    if p <= 25:
        return (
            '<span class="pbj-geo-review-flag pbj-geo-review-flag--watch" '
            'title="Below-average total nurse HPRD within Connecticut">'
            "Watch</span>"
        )
    return ""


def _region_display_map(bundle: dict[str, Any]) -> dict[str, str]:
    raw = bundle.get("region_display_labels") or {}
    if isinstance(raw, dict) and raw:
        return {str(k): str(v) for k, v in raw.items()}
    st = str(bundle.get("state_code") or "").strip().upper()
    if not st:
        return {}
    try:
        import sys
        from pathlib import Path

        pbjapp = Path(__file__).resolve().parent.parent / "PBJapp"
        if pbjapp.is_dir() and str(pbjapp) not in sys.path:
            sys.path.insert(0, str(pbjapp))
        from geo_intelligence.registry import build_region_display_map, load_geo_scope_registry

        return build_region_display_map(st, load_geo_scope_registry())
    except Exception:
        return {}


def _region_label(
    display_map: dict[str, str],
    county_key: str,
    raw_label: str,
    *,
    row: dict[str, Any] | None = None,
) -> str:
    if row and row.get("display_label"):
        return str(row["display_label"])
    ck = str(county_key or "").strip()
    return display_map.get(ck) or str(raw_label or ck)


def _provider_page_href(ccn: str) -> str:
    return f"/provider/{str(ccn).zfill(6)}"


def _format_facility_name(name: str) -> str:
    try:
        from app import capitalize_facility_name

        return capitalize_facility_name(str(name or "").strip())
    except ImportError:
        return str(name or "").strip()


def _geo_ui_labels(bundle: dict[str, Any]) -> dict[str, str]:
    ui = bundle.get("geography_ui") or {}
    unit = str(ui.get("unit") or bundle.get("county_model_label") or "Region").strip()
    unit_short = str(ui.get("unit_short") or "Region").strip()
    unit_plural = str(ui.get("unit_plural") or "Regions").strip()
    county_model = str(bundle.get("county_model") or ui.get("county_model") or "").strip()
    return {
        "unit": unit,
        "unit_short": unit_short,
        "unit_plural": unit_plural,
        "county_model": county_model,
        "comparison_intro": str(ui.get("comparison_intro") or unit).strip(),
    }


def _coverage_for_selected_quarter(bundle: dict[str, Any], quarter: str) -> dict[str, Any]:
    cov = (bundle.get("coverage_by_quarter") or {}).get(quarter) or {}
    return {
        "total_facilities_in_scope": int(cov.get("total_facilities_in_scope") or 0),
        "assigned_facilities": int(cov.get("assigned_facilities") or 0),
        "unknown_geography_count": int(cov.get("unknown_geography_count") or 0),
        "quarantined_count": int(cov.get("quarantined_count") or 0),
        "usable_for_regional_rollup": int(cov.get("usable_for_regional_rollup") or 0),
        "coverage_rate": float(cov.get("coverage_rate") or 0.0),
        "regions_reporting": int(cov.get("regions_reporting") or 0),
    }


def _render_coverage_note(coverage: dict[str, Any], labels: dict[str, str], quarter: str) -> str:
    unknown = coverage["unknown_geography_count"]
    quarantined = coverage["quarantined_count"]
    if unknown <= 0 and quarantined <= 0:
        return ""
    unit_short = html.escape(labels["unit_short"])
    unit_plural = html.escape(labels["unit_plural"])
    q = html.escape(quarter)
    parts: list[str] = []
    if quarantined > 0:
        parts.append(
            f"{quarantined} facility-quarters with conflicting {unit_short.lower()} assignment"
        )
    if unknown > 0:
        parts.append(
            f"{unknown} with unknown {unit_short.lower()} (excluded from {unit_plural.lower()} totals)"
        )
    detail = "; ".join(parts)
    return (
        f'<p class="pbj-geo-coverage" role="status" '
        f'aria-label="Geography coverage for {q}">'
        f"Coverage ({q}): {detail}."
        f"</p>"
    )


def _hprd_explainer_block(
    *,
    hprd_display: str,
    na_hprd: Any,
    state_name: str,
    uid: str,
) -> tuple[str, str]:
    """Optional HPRD means trigger + modal (uses shared provider/state modal markup)."""
    try:
        from app import build_hprd_floor_analogy_body, render_hprd_means_explainer
    except ImportError:
        return "", ""
    try:
        h = float(hprd_display)
    except (TypeError, ValueError):
        return "", ""
    if h <= 0:
        return "", ""
    body = build_hprd_floor_analogy_body(
        h,
        na_hprd,
        state_name,
        census=None,
        context="state",
    )
    trigger, modal = render_hprd_means_explainer(hprd_display, body, uid=uid)
    if not trigger:
        return "", ""
    return (
        f'<div class="pbj-geo-hprd-explainer">{trigger}</div>',
        modal,
    )


def _brand_pill_html() -> str:
    try:
        from app import PBJ_TAKEAWAY_BRAND_PILL_HTML

        return PBJ_TAKEAWAY_BRAND_PILL_HTML
    except ImportError:
        return (
            '<span class="pbj-takeaway-brand-pill">'
            '<span class="pbj-brand-pbj">PBJ</span><span class="pbj-brand-320">320</span>'
            "</span>"
        )


def _render_facility_header(
    *,
    state_name: str,
    quarter: str,
    coverage: dict[str, Any],
    regions_count: int,
    unit_plural: str,
) -> str:
    """v2-style facility header matching advanced dashboard shell."""
    esc_state = html.escape(state_name)
    esc_q = html.escape(quarter)
    n_fac = int(coverage.get("usable_for_regional_rollup") or 0)
    n_reg = int(coverage.get("regions_reporting") or regions_count or 0)
    unit_label = html.escape(str(unit_plural).lower())
    return f"""
<div class="facility-header" id="pbjGeoFacilityHeader">
  <p class="facility-header-brand-line mb-0 text-center">
    <span class="facility-header-brand-badge rounded-pill border px-2 py-1">
      <a href="/" class="pbj-brand-link facility-header-brand">
        <span class="pbj-brand-mark pbj-brand-mark--on-dark"><span class="pbj-brand-pbj">PBJ</span><span class="pbj-brand-320">320</span></span>
      </a>
    </span>
  </p>
  <p class="facility-header-product-line mb-0">PBJ320 Nursing Home Staffing Intelligence</p>
  <div class="facility-title-wrap">
    <h1 class="facility-title-row mb-0">{esc_state} · Regional staffing workspace</h1>
  </div>
  <div class="facility-locline-wrap mt-1 mb-0">
    <span class="facility-locline-location">{n_reg} {unit_label} · {n_fac} facilities · {esc_q}</span>
  </div>
  <div class="facility-hero-meta-notice" role="note">
    For regional advocates and ombuds — select your planning region to review facilities and staffing in your coverage area.
  </div>
</div>"""


def _metrics_pods_row(pods: list[tuple[str, str]]) -> str:
    cols: list[str] = []
    for label, value in pods:
        cols.append(
            '<div class="col-md-3 col-sm-6">'
            '<div class="pbj-summary-pod h-100">'
            '<div class="pbj-summary-pod-body">'
            f'<div class="text-muted small">{html.escape(label)}</div>'
            f'<div class="pbj-metric-value fs-4 fw-semibold">{html.escape(value)}</div>'
            "</div></div></div>"
        )
    return f'<div class="row g-2 mb-3">{"".join(cols)}</div>'


def _normalize_region_key(region: str, valid_keys: set[str]) -> str:
    rk = str(region or "").strip()
    if not rk:
        return ""
    if rk in valid_keys:
        return rk
    lower = rk.lower()
    for key in valid_keys:
        if key.lower() == lower:
            return key
    return ""


def _build_facility_table_rows(facs: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for fac in sorted(facs, key=lambda r: str(r.get("provnum") or "")):
        ccn_raw = str(fac.get("provnum") or "").zfill(6)
        ccn = html.escape(ccn_raw)
        pname = html.escape(_format_facility_name(str(fac.get("provname") or "")))
        prov_href = html.escape(_provider_page_href(ccn_raw), quote=True)
        rows.append(
            "<tr>"
            f'<td><a href="{prov_href}">{ccn}</a></td>'
            f'<td><a href="{prov_href}">{pname}</a></td>'
            f'<td class="pbj-geo-num">{_fmt_hprd(fac.get("total_nurse_hprd"))}</td>'
            f'<td class="pbj-geo-num">{_fmt_hprd(fac.get("nurse_care_hprd"))}</td>'
            "</tr>"
        )
    return "".join(rows)


def _build_outlier_table_rows(
    outliers: list[dict[str, Any]],
    display_map: dict[str, str],
    *,
    region_key: str = "",
    limit: int = 25,
) -> str:
    rows: list[str] = []
    for row in outliers:
        rk_raw = str(row.get("county_key") or "")
        if region_key and rk_raw and rk_raw != region_key:
            continue
        ccn_raw = str(row.get("provnum") or "").zfill(6)
        ccn = html.escape(ccn_raw)
        prov_href = html.escape(_provider_page_href(ccn_raw), quote=True)
        region_lbl = html.escape(
            _region_label(
                display_map,
                rk_raw,
                str(row.get("county_label") or ""),
            )
        )
        flag = _staffing_review_flag(row.get("percentile"), row.get("total_nurse_hprd"))
        rows.append(
            f'<tr data-pbj-geo-region-key="{html.escape(rk_raw)}">'
            f'<td><a href="{prov_href}">{ccn}</a></td>'
            f'<td><a href="{prov_href}">{html.escape(_format_facility_name(str(row.get("provname") or "")))}</a>'
            f'{f" {flag}" if flag else ""}</td>'
            f"<td>{region_lbl}</td>"
            f'<td class="pbj-geo-num">{_fmt_hprd(row.get("total_nurse_hprd"))}</td>'
            f'<td class="pbj-geo-num">{_fmt_percentile(row.get("percentile"))}</td>'
            "</tr>"
        )
        if len(rows) >= limit:
            break
    return "".join(rows)


def generate_geo_intelligence_content(
    *,
    state_name: str,
    state_slug: str,
    state_code: str,
    bundle: dict[str, Any],
    quarter: str,
    region: str = "",
) -> str:
    """Inner HTML for geographic intelligence (wrap with get_pbj_site_layout in production)."""
    q = quarter or str(bundle.get("canonical_quarter") or "")
    quarters = list(bundle.get("quarters") or [])
    if q not in quarters and quarters:
        q = quarters[-1]

    labels = _geo_ui_labels(bundle)
    unit = html.escape(labels["unit"])
    unit_short = html.escape(labels["unit_short"])
    unit_plural = html.escape(labels["unit_plural"])
    display_map = _region_display_map(bundle)

    regions = list((bundle.get("counties_by_quarter") or {}).get(q) or [])
    valid_region_keys = {str(r.get("county_key") or "") for r in regions if r.get("county_key")}
    selected_region = _normalize_region_key(region, valid_region_keys)
    statewide_hidden = " pbj-geo-view-hidden" if selected_region else ""

    state_metrics = (bundle.get("state_metrics_by_quarter") or {}).get(q) or {}
    national_metrics = (bundle.get("national_metrics_by_quarter") or {}).get(q) or {}
    outliers = list((bundle.get("outliers_by_quarter") or {}).get(q) or [])
    facilities_by_region = (bundle.get("facilities_by_county_quarter") or {}).get(q) or {}
    coverage = _coverage_for_selected_quarter(bundle, q)

    quarter_options = "".join(
        f'<option value="{html.escape(str(qtr))}"{" selected" if qtr == q else ""}>'
        f"{html.escape(str(qtr))}</option>"
        for qtr in quarters
    )

    region_rows = []
    for row in sorted(regions, key=lambda r: str(r.get("display_label") or r.get("county_label") or "")):
        rk_raw = str(row.get("county_key") or "")
        rk = html.escape(rk_raw)
        label_raw = _region_label(display_map, rk_raw, str(row.get("county_label") or ""), row=row)
        label = html.escape(label_raw)
        label_attr = html.escape(label_raw.lower(), quote=True)
        fc = int(row.get("facility_count") or 0)
        region_link_qs = f"region={html.escape(rk_raw, quote=True)}"
        if q:
            region_link_qs = f"quarter={html.escape(q, quote=True)}&{region_link_qs}"
        region_rows.append(
            f'<tr data-pbj-geo-region-key="{rk}" data-pbj-geo-region-label="{label_attr}">'
            f'<td><a href="?{region_link_qs}">{label}</a></td>'
            f'<td class="pbj-geo-num">{fc}</td>'
            f'<td class="pbj-geo-num">{_fmt_hprd(row.get("Total_Nurse_HPRD"))}</td>'
            f'<td class="pbj-geo-num">{_fmt_hprd(row.get("Nurse_Care_HPRD"))}</td>'
            f'<td class="pbj-geo-num">{_fmt_hprd(row.get("RN_HPRD"))}</td>'
            f'<td class="pbj-geo-num">{_fmt_hprd(row.get("Nurse_Assistant_HPRD"))}</td>'
            "</tr>"
        )

    drilldown_sections = []
    region_workspaces = []
    sorted_regions = sorted(
        regions, key=lambda r: str(r.get("display_label") or r.get("county_label") or "")
    )
    region_select_options = [
        '<option value="">Statewide — compare all planning regions</option>'
    ]
    datalist_options: list[str] = []

    for row in sorted_regions:
        rk_raw = str(row.get("county_key") or "")
        rk = html.escape(rk_raw)
        label_raw = _region_label(display_map, rk_raw, str(row.get("county_label") or ""), row=row)
        label = html.escape(label_raw)
        label_attr = html.escape(label_raw.lower(), quote=True)
        sel = " selected" if rk_raw == selected_region else ""
        region_select_options.append(f'<option value="{rk}"{sel}>{label}</option>')
        datalist_options.append(f'<option value="{label}">')

    for region_key, facs in sorted(facilities_by_region.items(), key=lambda x: x[0]):
        rk_raw = str(region_key)
        rk = html.escape(rk_raw)
        raw_label = str((facs[0] or {}).get("county_label") if facs else region_key)
        label_raw = _region_label(display_map, rk_raw, raw_label)
        label = html.escape(label_raw)
        label_attr = html.escape(label_raw.lower(), quote=True)
        fc = len(facs)
        fac_table_body = _build_facility_table_rows(facs)
        region_row = next((r for r in regions if str(r.get("county_key") or "") == rk_raw), {})
        ws_hidden = selected_region != rk_raw
        ws_class = " pbj-geo-view-hidden" if ws_hidden else ""
        regional_outlier_body = _build_outlier_table_rows(
            outliers, display_map, region_key=rk_raw, limit=15
        )
        regional_outlier_section = (
            f'<h3 class="pbj-geo-workspace-subhead">Low staffing flags in this region</h3>'
            f'<p class="pbj-geo-section-lead">Lowest total nurse HPRD percentiles among facilities in {label}.</p>'
            f'<div class="pbj-table-wrap"><table class="pbj-geo-table" aria-label="Regional outlier rankings for {label}">'
            f"<thead><tr><th>CCN</th><th>Facility</th><th class=\"pbj-geo-num\">HPRD</th><th class=\"pbj-geo-num\">Percentile</th></tr></thead>"
            f"<tbody>{regional_outlier_body or '<tr><td colspan=\"4\">No outlier flags for this region.</td></tr>'}</tbody></table></div>"
        )
        region_workspaces.append(
            f'<section class="pbj-geo-region-workspace dashboard-section mb-3{ws_class}" data-pbj-geo-region-key="{rk}" '
            f'data-pbj-geo-region-label="{label_attr}"{" hidden" if ws_hidden else ""} '
            f'aria-label="{html.escape(labels["unit_short"])} workspace for {label}">'
            f'<div class="card pbj-v2-section-surface border"><div class="card-body">'
            f'<div class="pbj-geo-workspace-head">'
            f"<h2>{label}</h2>"
            f'<button type="button" class="pbj-geo-back-statewide">← All planning regions</button>'
            f"</div>"
            + _metrics_pods_row(
                [
                    ("Facilities", str(fc)),
                    ("Total nurse HPRD", _fmt_hprd(region_row.get("Total_Nurse_HPRD"))),
                    ("Direct care HPRD", _fmt_hprd(region_row.get("Nurse_Care_HPRD"))),
                    ("RN HPRD", _fmt_hprd(region_row.get("RN_HPRD"))),
                ]
            )
            + f'<h3 class="pbj-geo-workspace-subhead">Facilities in your region</h3>'
            f'<div class="pbj-table-wrap"><table class="pbj-geo-table" aria-label="Facilities in {label}">'
            f"<thead><tr><th>CCN</th><th>Facility</th>"
            f'<th class="pbj-geo-num">Total nurse HPRD</th>'
            f'<th class="pbj-geo-num">Direct care HPRD</th>'
            f"</tr></thead><tbody>{fac_table_body or '<tr><td colspan=\"4\">No facilities.</td></tr>'}</tbody></table></div>"
            f"{regional_outlier_section}"
            f"</div></div></section>"
        )
        drilldown_sections.append(
            f'<details id="region-{rk}" class="pbj-details pbj-state-staffing-table pbj-geo-region-details" '
            f'data-pbj-geo-region-key="{rk}" data-pbj-geo-region-label="{label_attr}" '
            f'aria-label="{unit_short} {label}">'
            f'<summary><span class="pbj-details-icon" aria-hidden="true">▼</span> '
            f"{label} ({fc} facilities)</summary>"
            f'<div class="pbj-details-content">'
            f'<div class="pbj-table-wrap"><table class="pbj-geo-table" aria-label="Facilities in {label}">'
            f"<thead><tr>"
            f"<th>CCN</th><th>Facility</th>"
            f'<th class="pbj-geo-num">Total nurse HPRD</th>'
            f'<th class="pbj-geo-num">Direct care HPRD</th>'
            f"</tr></thead><tbody>{fac_table_body}</tbody></table></div>"
            f"</div></details>"
        )

    outlier_html = _build_outlier_table_rows(outliers, display_map, limit=25)

    coverage_note = _render_coverage_note(coverage, labels, q)

    empty_region_row = (
        f'<tr><td colspan="6">No {unit_plural.lower()} data for this quarter.</td></tr>'
    )
    empty_outlier_row = (
        '<tr><td colspan="5">Not enough facilities for percentile ranking.</td></tr>'
    )
    empty_drilldown = f"<p>No facility drilldown for this quarter.</p>"

    state_hprd = _fmt_hprd(state_metrics.get("Total_Nurse_HPRD"))
    nat_hprd = _fmt_hprd(national_metrics.get("Total_Nurse_HPRD"))
    canonical = html.escape(str(bundle.get("canonical_quarter") or q))

    hprd_trigger, hprd_modal = _hprd_explainer_block(
        hprd_display=state_hprd,
        na_hprd=state_metrics.get("Nurse_Assistant_HPRD"),
        state_name=state_name,
        uid=f"geo-{state_slug}-{q}",
    )

    bundle_json = json.dumps(
        {
            "quarters": quarters,
            "canonical_quarter": bundle.get("canonical_quarter"),
            "selected_quarter": q,
            "selected_region": selected_region,
            "state_code": state_code,
            "coverage": coverage,
        }
    )

    esc_state = html.escape(state_name)
    esc_slug = html.escape(state_slug)
    esc_code = html.escape(state_code)
    facility_header = _render_facility_header(
        state_name=state_name,
        quarter=q,
        coverage=coverage,
        regions_count=len(regions),
        unit_plural=labels["unit_plural"],
    )
    statewide_metrics = _metrics_pods_row(
        [
            ("State total nurse HPRD", state_hprd),
            ("National total nurse HPRD", nat_hprd),
            (labels["unit_plural"], str(coverage["regions_reporting"] or len(regions))),
        ]
    )
    region_search_value = ""
    if selected_region:
        for row in sorted_regions:
            if str(row.get("county_key") or "") == selected_region:
                region_search_value = html.escape(
                    _region_label(
                        display_map,
                        selected_region,
                        str(row.get("county_label") or ""),
                        row=row,
                    ),
                    quote=True,
                )
                break

    return f"""
<div class="pbj-geo-page">
  {facility_header}
  <p class="pbj-geo-breadcrumb" aria-label="Breadcrumb">
    <a href="/">Home</a> ·
    <a href="/state/{esc_slug}">{esc_state}</a> ·
    Regional intelligence
  </p>
  <section class="dashboard-section mb-3" aria-labelledby="pbjGeoWorkspaceHeading">
    <div class="pbj-staffing-report-head">
      <h2 id="pbjGeoWorkspaceHeading" class="dashboard-section-title h5 mb-0">1. Regional workspace</h2>
    </div>
    <div class="card pbj-v2-section-surface border">
      <div class="card-body pbj-geo-workspace-toolbar">
        <form method="get" id="pbjGeoQuarterForm" class="pbj-geo-quarter-form">
          <label for="pbjGeoQuarterSelect">Data quarter
            <select id="pbjGeoQuarterSelect" name="quarter" class="form-select form-select-sm d-inline-block w-auto ms-1" aria-label="Select PBJ data quarter" onchange="this.form.submit()">{quarter_options}</select>
          </label>
          <input type="hidden" name="region" id="pbjGeoQuarterRegionHidden" value="{html.escape(selected_region)}">
        </form>
        <div class="pbj-geo-region-picker">
          <label for="pbjGeoRegionSelect">Your planning region</label>
          <div class="pbj-geo-region-picker-row">
            <input type="search" id="pbjGeoRegionSearch" list="pbjGeoRegionDatalist" class="form-control form-control-sm"
              placeholder="Search planning regions…" autocomplete="off"
              aria-label="Search planning regions" value="{region_search_value}">
            <datalist id="pbjGeoRegionDatalist">{''.join(datalist_options)}</datalist>
            <select id="pbjGeoRegionSelect" class="form-select form-select-sm" aria-label="Select your planning region">
              {''.join(region_select_options)}
            </select>
          </div>
          <p class="pbj-geo-region-picker-hint">
            Choose or search for the region you cover. Each region opens its own facility list and staffing flags.
          </p>
        </div>
      </div>
    </div>
  </section>
  {''.join(region_workspaces)}
  <div class="pbj-geo-statewide-view{statewide_hidden}">
    <section class="dashboard-section mb-3" aria-labelledby="pbjGeoStatewideHeading">
      <div class="pbj-staffing-report-head">
        <h2 id="pbjGeoStatewideHeading" class="dashboard-section-title h5 mb-0">2. Statewide comparison</h2>
      </div>
      <div class="card pbj-v2-section-surface border">
        <div class="card-body">
          <p class="pbj-geo-methodology">
            Data quarter <strong>{html.escape(q)}</strong>
            {f' (latest available: {canonical})' if q == bundle.get('canonical_quarter') else ''}.
            {unit} rollups from CMS PBJ quarterly data.
            Staffing by role (RN, LPN, aide) appears as fixed columns below;
            this page does not provide an interactive position-group filter.
          </p>
          {statewide_metrics}
          {hprd_trigger}
          {coverage_note}
          <h3 class="dashboard-section-title h6 mt-3">{unit_plural} comparison</h3>
          <div class="pbj-table-wrap" id="pbjGeoRegionTable">
            <table class="pbj-geo-table" aria-label="{unit_plural} staffing comparison">
              <thead><tr>
                <th>{unit_short}</th>
                <th class="pbj-geo-num">Facilities</th>
                <th class="pbj-geo-num">Total nurse HPRD</th>
                <th class="pbj-geo-num">Direct care HPRD</th>
                <th class="pbj-geo-num">RN HPRD</th>
                <th class="pbj-geo-num">Aide HPRD</th>
              </tr></thead>
              <tbody>{''.join(region_rows) if region_rows else empty_region_row}</tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
    <section class="dashboard-section mb-3">
      <details class="pbj-details pbj-state-staffing-table">
        <summary><span class="pbj-details-icon" aria-hidden="true">▼</span> Facility outliers (statewide)</summary>
        <div class="pbj-details-content">
          <p class="pbj-geo-section-lead">Lowest total nurse HPRD percentiles within {esc_code} (n≥5).</p>
          <div class="pbj-table-wrap">
            <table class="pbj-geo-table" aria-label="Statewide facility outlier rankings">
              <thead><tr><th>CCN</th><th>Facility</th><th>{unit_short}</th><th class="pbj-geo-num">HPRD</th><th class="pbj-geo-num">Percentile</th></tr></thead>
              <tbody>{outlier_html or empty_outlier_row}</tbody>
            </table>
          </div>
        </div>
      </details>
    </section>
    <section class="dashboard-section mb-3">
      <h3 class="dashboard-section-title h6">Facilities by {unit_short.lower()}</h3>
      {''.join(drilldown_sections) if drilldown_sections else empty_drilldown}
    </section>
  </div>
  {hprd_modal}
  <script type="application/json" id="pbjGeoBundleMeta">{bundle_json}</script>
  <script>{_GEO_MODAL_BINDER_JS}</script>
</div>
"""


def _wrap_with_site_layout(
    content: str,
    *,
    page_title: str,
    meta_description: str,
    canonical_url: str,
    state_code: str,
    state_name: str,
    state_slug: str,
) -> str | None:
    """Wrap geo content in shared PBJ site chrome. Returns None if app layout unavailable."""
    try:
        from app import HAS_CSRF, generate_csrf, get_pbj_site_layout
    except ImportError:
        return None

    extra_head = (
        _geo_intelligence_assets_head()
        + f"<style>{_load_geo_shell_css()}</style>"
    )
    layout = get_pbj_site_layout(
        page_title,
        meta_description,
        canonical_url,
        extra_head=extra_head,
        route_context_overrides={
            "kind": "geo",
            "stateAbbr": state_code,
            "stateName": state_name,
            "stateSlug": state_slug,
        },
    )
    footer_tail = re.sub(
        r"^\s*</div>\s*</div>\s*",
        "",
        layout["content_close"],
        count=1,
    )
    intel_open = (
        '<script>document.documentElement.classList.add("pbj-geo-intel-route");'
        'document.body.classList.add("pbj-geo-intel-route");</script>'
        '<div class="pbj-geo-intel-shell">'
        '<div class="container-fluid pbj-v2-main">'
        '<div class="main-container">'
    )
    intel_close = "</div></div></div>" + footer_tail
    html_out = layout["head"] + layout["nav"] + intel_open + content + intel_close
    try:
        from flask import has_app_context

        if HAS_CSRF and generate_csrf and has_app_context():
            html_out = html_out.replace("__CSRF_TOKEN_PLACEHOLDER__", generate_csrf())
        else:
            html_out = html_out.replace("__CSRF_TOKEN_PLACEHOLDER__", "")
    except Exception:
        html_out = html_out.replace("__CSRF_TOKEN_PLACEHOLDER__", "")
    return html_out


def generate_geo_intelligence_html(
    *,
    state_name: str,
    state_slug: str,
    state_code: str,
    bundle: dict[str, Any],
    quarter: str,
    region: str = "",
    site_origin: str = "https://www.pbj320.com",
) -> str:
    """Render full geographic intelligence page with shared PBJ site shell when available."""
    q = quarter or str(bundle.get("canonical_quarter") or "")
    quarters = list(bundle.get("quarters") or [])
    if q not in quarters and quarters:
        q = quarters[-1]

    content = generate_geo_intelligence_content(
        state_name=state_name,
        state_slug=state_slug,
        state_code=state_code,
        bundle=bundle,
        quarter=q,
        region=region,
    )

    page_title = f"{state_name} regional staffing intelligence | PBJ320"
    meta_description = (
        f"PBJ320 regional staffing workspace for {state_name}: select a planning region to review "
        f"nursing home HPRD, facilities, and low-staffing flags from CMS PBJ data."
    )
    canonical_url = f"{site_origin.rstrip('/')}/geo/{state_slug}"
    query: list[str] = []
    if q and q != bundle.get("canonical_quarter"):
        query.append(f"quarter={q}")
    region_key = str(region or "").strip()
    if region_key:
        query.append(f"region={region_key}")
    if query:
        canonical_url = f"{canonical_url}?{'&'.join(query)}"

    wrapped = _wrap_with_site_layout(
        content,
        page_title=page_title,
        meta_description=meta_description,
        canonical_url=canonical_url,
        state_code=state_code,
        state_name=state_name,
        state_slug=state_slug,
    )
    if wrapped:
        return wrapped

    # Fallback: minimal document when imported outside Flask app (tests/tools only).
    shell_css = _load_geo_shell_css()
    return (
        f"<!DOCTYPE html><html lang=\"en\" class=\"pbj-geo-intel-route\"><head><meta charset=\"utf-8\">"
        f"<title>{html.escape(page_title)}</title>"
        f"{_geo_intelligence_assets_head()}"
        f"<style>{shell_css}</style></head><body class=\"pbj-geo-intel-route\">"
        f'<div class="pbj-geo-intel-shell"><div class="container-fluid pbj-v2-main"><div class="main-container">'
        f"{content}</div></div></div></body></html>"
    )


def visible_text_forbidden_county_terms(html_body: str, *, county_model: str) -> list[str]:
    """
    Return user-visible 'county' matches when geography model is not census county.

    Strips script/style tags before scan.
    """
    if county_model not in ("pbj_planning_region",):
        return []
    stripped = re.sub(r"<script[\s\S]*?</script>", " ", html_body, flags=re.I)
    stripped = re.sub(r"<style[\s\S]*?</style>", " ", stripped, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", stripped)
    text = re.sub(r"\s+", " ", text).strip().lower()
    hits = []
    for m in re.finditer(r"\bcounty\b", text):
        start = max(0, m.start() - 40)
        hits.append(text[start : m.end() + 40])
    return hits
