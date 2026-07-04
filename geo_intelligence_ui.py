"""Premium HTML/CSS/JS for geographic intelligence pages (/premium/<state_slug>)."""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import Any

from geo_intelligence_page import (
    _brand_pill_html,
    _build_facility_table_rows,
    _build_outlier_table_rows,
    _coverage_for_selected_quarter,
    _fmt_hprd,
    _geo_ui_labels,
    _hprd_explainer_block,
    _normalize_region_key,
    _region_display_map,
    _region_label,
    _render_coverage_note,
)

_PREMIUM_CSS_PATH = Path(__file__).with_name("geo_intelligence_premium.css")
_PBJAPP_ROOT = Path(__file__).resolve().parent.parent / "PBJapp"


def _load_premium_css() -> str:
    if _PREMIUM_CSS_PATH.is_file():
        return _PREMIUM_CSS_PATH.read_text(encoding="utf-8")
    return ""


GEO_PREMIUM_CSS = _load_premium_css()


def format_quarter_label(q: str) -> str:
    """User-visible quarter label (e.g. Q4 2025)."""
    from pbj_format import format_quarter_display

    return format_quarter_display(q)


def _last_n_quarters(quarters: list[str], anchor: str, n: int = 4) -> list[str]:
    if not quarters:
        return []
    ordered = sorted(quarters)
    if anchor not in ordered:
        anchor = ordered[-1]
    idx = ordered.index(anchor)
    start = max(0, idx - n + 1)
    return ordered[start : idx + 1]


def _geo_metric_helpers() -> tuple[Any, Any, Any, Any]:
    """Lazy import PBJapp geo metric registry + compat (pbj-root runs with sibling PBJapp)."""
    _ensure_pbjapp_path()
    from geo_intelligence.compat import (
        normalize_bundle,
        region_metric_value,
        resolve_selected_metric,
        selector_metrics,
        state_metric_value,
        trend_series,
    )
    from geo_intelligence.metric_registry import get_metric_entry

    return (
        normalize_bundle,
        region_metric_value,
        resolve_selected_metric,
        selector_metrics,
        state_metric_value,
        trend_series,
        get_metric_entry,
    )


def _fmt_metric_display(value: Any, *, display_format: str) -> str:
    if display_format == "percent_1dp":
        try:
            return f"{float(value):.1f}%"
        except (TypeError, ValueError):
            return "—"
    return _fmt_hprd(value)


def _region_metric_series(
    bundle: dict[str, Any],
    region_key: str,
    anchor_q: str,
    metric_id: str = "total_nurse_hprd",
) -> list[float | None]:
    (
        normalize_bundle,
        _region_metric_value,
        _resolve_selected_metric,
        _selector_metrics,
        _state_metric_value,
        trend_series,
        _get_metric_entry,
    ) = _geo_metric_helpers()
    bundle = normalize_bundle(bundle)
    mid = _resolve_selected_metric(metric_id)
    _qs, vals, _sufficient = trend_series(
        bundle, anchor_quarter=anchor_q, metric_id=mid, region_key=region_key
    )
    return list(vals)


def _sparkline_svg(values: list[float], *, width: int = 56, height: int = 18) -> str:
    """Light-theme inline SVG sparkline for quarterly HPRD trend."""
    pairs: list[tuple[int, float]] = [
        (i, float(v)) for i, v in enumerate(values) if v is not None
    ]
    if len(pairs) < 2:
        return '<span class="pbj-geo-sparkline-empty" aria-hidden="true">—</span>'

    nums = [v for _, v in pairs]
    vmin, vmax = min(nums), max(nums)
    pad = 2
    inner_w = width - 2 * pad
    inner_h = height - 2 * pad
    span = max(vmax - vmin, 1e-9)

    coords: list[str] = []
    for idx, (i, v) in enumerate(pairs):
        x = pad + (i / max(len(values) - 1, 1)) * inner_w
        y = pad + inner_h - ((v - vmin) / span) * inner_h
        coords.append(f"{x:.1f},{y:.1f}")

    polyline = " ".join(coords)
    return (
        f'<svg class="pbj-geo-sparkline" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" aria-hidden="true" focusable="false">'
        f'<polyline fill="none" stroke="#4f46e5" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round" points="{polyline}"/>'
        f"</svg>"
    )


def _ensure_pbjapp_path() -> None:
    if _PBJAPP_ROOT.is_dir() and str(_PBJAPP_ROOT) not in sys.path:
        sys.path.insert(0, str(_PBJAPP_ROOT))


def load_map_paths(state_code: str, app_root: str) -> dict[str, Any] | None:
    """Load SVG path geometry JSON via registry map_geometry config."""
    _ensure_pbjapp_path()
    try:
        from geo_intelligence.registry import (
            map_geometry_config,
            resolve_geo_asset_path,
        )

        cfg = map_geometry_config(state_code)
        rel = str(cfg.get("paths_asset") or "").strip()
        if not rel:
            return None
        pbj_root = Path(app_root).resolve()
        path = resolve_geo_asset_path(
            rel,
            pbjapp_root=_PBJAPP_ROOT,
            pbj_root=pbj_root,
        )
        if path is None or not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def render_premium_nav(*, active: str = "regional") -> str:
    """Top nav matching premium/index.html (pbj-premium-nav-wrap)."""
    premium_cls = " active" if active == "premium" else ""
    sample_cls = " active" if active == "sample" else ""
    regional_cls = " active" if active == "regional" else ""
    about_cls = " active" if active == "about" else ""
    premium_aria = ' aria-current="page"' if active == "premium" else ""
    sample_aria = ' aria-current="page"' if active == "sample" else ""
    regional_aria = ' aria-current="page"' if active == "regional" else ""
    about_aria = ' aria-current="page"' if active == "about" else ""

    return f"""
<div class="pbj-premium-nav-wrap">
  <nav class="pbj-premium-nav-inner pbj-premium-nav-inner--minimal" aria-label="Premium">
    <a class="pbj-premium-brand" href="/" aria-label="PBJ320 home">
      <img src="/pbj_favicon.png" width="22" height="22" alt="" class="pbj-premium-brand-icon">
      <span class="pbj-premium-brand-mark">
        <span class="pbj-premium-brand-pbj">PBJ</span><span class="pbj-premium-brand-320">320</span>
      </span>
    </a>
    <div class="pbj-premium-nav-scroll">
      <div class="pbj-premium-nav-links">
        <a class="nav-pill{premium_cls}" href="/premium"{premium_aria}>Premium</a>
        <a class="nav-pill{sample_cls}" href="/premium/335513"{sample_aria}>Sample dashboard</a>
        <a class="nav-pill{regional_cls}" href="/premium/connecticut"{regional_aria}>Connecticut regions</a>
        <a class="nav-pill{about_cls}" href="/about"{about_aria}>About</a>
      </div>
    </div>
  </nav>
</div>"""


def render_premium_head_extras() -> str:
    """Bootstrap, Inter, premium-site.css, favicon."""
    return (
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
        '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">'
        '<link rel="stylesheet" href="/premium-assets/premium-site.css?v=24">'
        '<link rel="stylesheet" href="/premium-assets/premium-hub.css?v=44">'
        '<link rel="icon" type="image/png" href="/pbj_favicon.png">'
        '<link rel="apple-touch-icon" href="/pbj_favicon.png">'
    )


def _choropleth_color(value: float | None, vmin: float, vmax: float) -> str:
    if value is None:
        return "#e2e8f0"
    if vmax <= vmin:
        t = 0.5
    else:
        t = max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))
    # #dbeafe (low) → #1e3a5f (high)
    stops = [(219, 234, 254), (96, 165, 250), (30, 58, 95)]
    if t <= 0.5:
        t2 = t * 2
        r = int(stops[0][0] + (stops[1][0] - stops[0][0]) * t2)
        g = int(stops[0][1] + (stops[1][1] - stops[0][1]) * t2)
        b = int(stops[0][2] + (stops[1][2] - stops[0][2]) * t2)
    else:
        t2 = (t - 0.5) * 2
        r = int(stops[1][0] + (stops[2][0] - stops[1][0]) * t2)
        g = int(stops[1][1] + (stops[2][1] - stops[1][1]) * t2)
        b = int(stops[1][2] + (stops[2][2] - stops[1][2]) * t2)
    return f"#{r:02x}{g:02x}{b:02x}"


def _metrics_pods(pods: list[tuple[str, str]]) -> str:
    items: list[str] = []
    for label, value in pods:
        items.append(
            '<div class="pbj-geo-premium-pod">'
            f'<div class="pbj-geo-premium-pod-label">{html.escape(label)}</div>'
            f'<div class="pbj-geo-premium-pod-value">{html.escape(value)}</div>'
            "</div>"
        )
    return f'<div class="pbj-geo-premium-pods">{"".join(items)}</div>'


def _render_map_svg(
    map_data: dict[str, Any],
    region_metrics: dict[str, dict[str, Any]],
    *,
    display_map: dict[str, str],
    selected_region: str,
    metric_display_name: str = "Total nurse HPRD",
) -> str:
    view_box = str(map_data.get("viewBox") or "0 0 520 680")
    regions_geom = map_data.get("regions") or {}
    metric_vals = [
        float(m.get("value"))
        for m in region_metrics.values()
        if m.get("value") is not None
    ]
    vmin = min(metric_vals) if metric_vals else 0.0
    vmax = max(metric_vals) if metric_vals else 1.0

    paths: list[str] = []
    for rk, geom in regions_geom.items():
        if not isinstance(geom, dict):
            continue
        d = str(geom.get("d") or "").strip()
        if not d:
            continue
        metrics = region_metrics.get(rk) or {}
        hprd = metrics.get("value")
        fill = _choropleth_color(hprd, vmin, vmax)
        label_raw = _region_label(
            display_map,
            rk,
            str(geom.get("display_label") or metrics.get("label") or rk),
        )
        label = html.escape(label_raw)
        hprd_txt = metrics.get("value_display") or (
            _fmt_hprd(hprd) if hprd is not None else "—"
        )
        fc = int(metrics.get("facility_count") or 0)
        esc_metric = html.escape(metric_display_name)
        title = html.escape(f"{label_raw}: {hprd_txt} {metric_display_name} ({fc} facilities)")
        sel_cls = " is-selected" if rk == selected_region else ""
        paths.append(
            f'<path class="pbj-geo-map-region{sel_cls}" '
            f'id="pbjGeoMapRegion-{html.escape(rk)}" '
            f'data-pbj-geo-region-key="{html.escape(rk)}" '
            f'd="{d}" fill="{fill}" tabindex="0" role="button" '
            f'aria-label="{label}, {html.escape(str(hprd_txt))} {esc_metric}" '
            f'title="{title}" '
            f'aria-describedby="pbjGeoMapDesc-{html.escape(rk)}"/>'
            f'<desc id="pbjGeoMapDesc-{html.escape(rk)}">{label}: {html.escape(str(hprd_txt))}</desc>'
        )

    esc_metric = html.escape(metric_display_name)
    return (
        f'<svg class="pbj-geo-premium-map" viewBox="{html.escape(view_box)}" '
        f'preserveAspectRatio="xMidYMid meet" '
        f'role="img" aria-label="Planning region map colored by {esc_metric}">'
        f'<g class="pbj-geo-map-regions">{"".join(paths)}</g></svg>'
        f'<div class="pbj-geo-premium-map-legend" aria-hidden="true">'
        f'<span>Lower</span><span class="pbj-geo-premium-map-legend-bar"></span>'
        f'<span>Higher {esc_metric}</span>'
        f"</div>"
    )


def _render_bar_chart(
    region_metrics: dict[str, dict[str, Any]],
    *,
    state_value: float | None,
    selected_region: str,
    metric_display_name: str = "Total nurse HPRD",
    display_format: str = "hprd_2dp",
) -> str:
    sorted_rows = sorted(
        region_metrics.items(),
        key=lambda x: float(x[1].get("value") or 0),
        reverse=True,
    )
    max_val = max(
        [float(r[1].get("value") or 0) for r in sorted_rows] + ([state_value] if state_value else [0]),
        default=1.0,
    )
    if max_val <= 0:
        max_val = 1.0

    ref_pct = (state_value / max_val * 100) if state_value and state_value > 0 else None
    rows: list[str] = []
    for rk, metrics in sorted_rows:
        label = html.escape(str(metrics.get("label") or rk))
        val = metrics.get("value")
        val_txt = metrics.get("value_display") or _fmt_hprd(val)
        pct = (float(val) / max_val * 100) if val is not None else 0
        sel = " is-selected" if rk == selected_region else ""
        ref_line = ""
        if ref_pct is not None:
            ref_line = (
                f'<span class="pbj-geo-premium-bar-ref-line" '
                f'style="left:{ref_pct:.1f}%;" aria-hidden="true"></span>'
            )
        rows.append(
            f'<div class="pbj-geo-premium-bar-row{sel}" data-pbj-geo-region-key="{html.escape(rk)}" '
            f'tabindex="0" role="button" aria-label="{label}, {html.escape(str(val_txt))}">'
            f'<span class="pbj-geo-premium-bar-label">{label}</span>'
            f'<div class="pbj-geo-premium-bar-track-wrap">'
            f'{ref_line}'
            f'<div class="pbj-geo-premium-bar-fill" style="width:{pct:.1f}%;"></div>'
            f"</div>"
            f'<span class="pbj-geo-premium-bar-value">{html.escape(str(val_txt))}</span>'
            f"</div>"
        )

    ref_label = ""
    if state_value is not None and state_value > 0:
        state_txt = _fmt_metric_display(state_value, display_format=display_format)
        ref_label = (
            f'<p class="pbj-geo-premium-bar-ref-label">'
            f"State average: {html.escape(str(state_txt))} {html.escape(metric_display_name)}"
            f"</p>"
        )

    return f'<div class="pbj-geo-premium-bars">{"".join(rows)}</div>{ref_label}'


GEO_PREMIUM_JS = """
(function(){
  function applyRegionView(regionKey) {
    var key = (regionKey || '').trim();
    document.querySelectorAll('.pbj-geo-statewide-only').forEach(function(el) {
      el.classList.toggle('pbj-geo-view-hidden', !!key);
    });
    document.querySelectorAll('.pbj-geo-region-workspace').forEach(function(el) {
      var match = el.getAttribute('data-pbj-geo-region-key') === key;
      el.classList.toggle('pbj-geo-view-hidden', !match);
      el.hidden = !match;
    });
    document.querySelectorAll('.pbj-geo-region-prompt').forEach(function(el) {
      el.classList.toggle('pbj-geo-view-hidden', !!key);
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
    syncRegionHighlight(key);
    var params = new URLSearchParams(window.location.search);
    if (key) params.set('region', key); else params.delete('region');
    var qsel = document.getElementById('pbjGeoQuarterSelect');
    if (qsel && qsel.value) params.set('quarter', qsel.value);
    else params.delete('quarter');
    var msel = document.getElementById('pbjGeoMetricSelect');
    if (msel && msel.value) params.set('metric', msel.value);
    else params.delete('metric');
    var qs = params.toString();
    var url = window.location.pathname + (qs ? '?' + qs : '');
    if (window.history && window.history.replaceState) {
      window.history.replaceState({}, '', url);
    }
    if (key) {
      var ws = document.querySelector('.pbj-geo-region-workspace[data-pbj-geo-region-key="'+key.replace(/"/g, '')+'"]');
      if (ws) ws.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  function syncRegionHighlight(key) {
    var selectors = [
      '.pbj-geo-map-region',
      '.pbj-geo-premium-bar-row',
      '.pbj-geo-premium-table tbody tr[data-pbj-geo-region-key]'
    ];
    selectors.forEach(function(sel) {
      document.querySelectorAll(sel).forEach(function(el) {
        var rk = el.getAttribute('data-pbj-geo-region-key') || '';
        var selected = key && rk === key;
        el.classList.toggle('is-selected', selected);
        el.classList.toggle('is-dimmed', !!key && rk !== key);
      });
    });
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
        if ((opt.textContent || '').toLowerCase().indexOf(q) >= 0) {
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

  function bindRegionClick(el) {
    el.addEventListener('click', function() {
      var rk = el.getAttribute('data-pbj-geo-region-key') || '';
      if (select) select.value = rk;
      applyRegionView(rk);
    });
    el.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        el.click();
      }
    });
  }

  document.querySelectorAll('.pbj-geo-map-region, .pbj-geo-premium-bar-row').forEach(bindRegionClick);

  document.querySelectorAll('.pbj-geo-premium-table tbody tr[data-pbj-geo-region-key]').forEach(function(row) {
    row.style.cursor = 'pointer';
    row.addEventListener('click', function(e) {
      if (e.target.closest('a')) return;
      var rk = row.getAttribute('data-pbj-geo-region-key') || '';
      if (select) select.value = rk;
      applyRegionView(rk);
    });
  });

  var qform = document.getElementById('pbjGeoQuarterForm');
  if (qform) {
    qform.addEventListener('submit', function() {
      var hidden = document.getElementById('pbjGeoQuarterRegionHidden');
      var sel = document.getElementById('pbjGeoRegionSelect');
      if (hidden && sel) hidden.value = sel.value || '';
      var msel = document.getElementById('pbjGeoMetricSelect');
      var mhidden = document.getElementById('pbjGeoQuarterMetricHidden');
      if (mhidden && msel) mhidden.value = msel.value || '';
    });
  }

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
})();
"""


def generate_premium_geo_content(
    *,
    state_name: str,
    state_slug: str,
    state_code: str,
    bundle: dict[str, Any],
    quarter: str,
    region: str = "",
    metric: str = "",
    app_root: str = "",
) -> tuple[str, str]:
    """Premium page inner HTML and body-root modal markup."""
    (
        normalize_bundle,
        region_metric_value,
        resolve_selected_metric,
        selector_metrics,
        state_metric_value,
        _trend_series,
        get_metric_entry,
    ) = _geo_metric_helpers()
    bundle = normalize_bundle(bundle)

    selected_metric_id = resolve_selected_metric(metric or None)
    metric_entry = get_metric_entry(selected_metric_id)
    metric_display_name = str(metric_entry.get("display_name") or selected_metric_id)
    metric_description = str(metric_entry.get("description") or "")
    display_format = str(metric_entry.get("display_format") or "hprd_2dp")
    v2_col = str(metric_entry.get("v2_county_column") or "")

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

    state_metrics = (bundle.get("state_metrics_by_quarter") or {}).get(q) or {}
    national_metrics = (bundle.get("national_metrics_by_quarter") or {}).get(q) or {}
    outliers = list((bundle.get("outliers_by_quarter") or {}).get(q) or [])
    facilities_by_region = (bundle.get("facilities_by_county_quarter") or {}).get(q) or {}
    coverage = _coverage_for_selected_quarter(bundle, q)

    q_display = format_quarter_label(q)
    canonical = bundle.get("canonical_quarter")
    canonical_note = ""
    if canonical and q == canonical:
        canonical_note = f" (latest available: {html.escape(format_quarter_label(str(canonical)))})"

    n_fac = int(coverage.get("usable_for_regional_rollup") or 0)
    n_regions = len(regions)
    esc_state = html.escape(state_name)

    quarter_options = "".join(
        f'<option value="{html.escape(str(qtr))}"{" selected" if qtr == q else ""}>'
        f"{html.escape(format_quarter_label(str(qtr)))}</option>"
        for qtr in quarters
    )

    sorted_regions = sorted(
        regions, key=lambda r: str(r.get("display_label") or r.get("county_label") or "")
    )
    region_select_options = [
        '<option value="">Statewide — compare all planning regions</option>',
    ]
    region_metrics: dict[str, dict[str, Any]] = {}

    metric_options = "".join(
        f'<option value="{html.escape(str(m["metric_id"]))}"'
        f'{" selected" if str(m["metric_id"]) == selected_metric_id else ""}>'
        f'{html.escape(str(m["display_name"]))}</option>'
        for m in selector_metrics()
    )

    for row in sorted_regions:
        rk_raw = str(row.get("county_key") or "")
        rk = html.escape(rk_raw)
        label_raw = _region_label(display_map, rk_raw, str(row.get("county_label") or ""), row=row)
        label = html.escape(label_raw)
        sel = " selected" if rk_raw == selected_region else ""
        region_select_options.append(f'<option value="{rk}"{sel}>{label}</option>')
        mval = region_metric_value(
            bundle, quarter=q, region_key=rk_raw, metric_id=selected_metric_id
        )
        region_metrics[rk_raw] = {
            "label": label_raw,
            "value": mval,
            "value_display": _fmt_metric_display(mval, display_format=display_format),
            "facility_count": int(row.get("facility_count") or 0),
            "nurse_care_hprd": row.get("Nurse_Care_HPRD"),
            "rn_hprd": row.get("RN_HPRD"),
            "aide_hprd": row.get("Nurse_Assistant_HPRD"),
        }

    state_metric_float = state_metric_value(bundle, quarter=q, metric_id=selected_metric_id)

    app_root = str(app_root or Path(__file__).resolve().parent)
    map_data = load_map_paths(state_code, app_root) or {}

    map_html = _render_map_svg(
        map_data,
        region_metrics,
        display_map=display_map,
        selected_region=selected_region,
        metric_display_name=metric_display_name,
    )
    bar_html = _render_bar_chart(
        region_metrics,
        state_value=state_metric_float,
        selected_region=selected_region,
        metric_display_name=metric_display_name,
        display_format=display_format,
    )

    col_total = "Total_Nurse_HPRD"
    col_direct = "Nurse_Care_HPRD"
    col_rn = "RN_HPRD"
    emphasis_col = v2_col or col_total

    comparison_rows: list[str] = []
    for row in sorted(
        sorted_regions,
        key=lambda r: -float(
            region_metric_value(
                bundle,
                quarter=q,
                region_key=str(r.get("county_key") or ""),
                metric_id=selected_metric_id,
            )
            or 0
        ),
    ):
        rk_raw = str(row.get("county_key") or "")
        rk = html.escape(rk_raw)
        label_raw = _region_label(display_map, rk_raw, str(row.get("county_label") or ""), row=row)
        label = html.escape(label_raw)
        fc = int(row.get("facility_count") or 0)
        emph_val = region_metric_value(
            bundle, quarter=q, region_key=rk_raw, metric_id=selected_metric_id
        )
        emph_cell = _fmt_metric_display(emph_val, display_format=display_format)
        emph_cls = " pbj-geo-metric-emphasis"
        spark = _sparkline_svg(
            _region_metric_series(bundle, rk_raw, q, metric_id=selected_metric_id)
        )
        comparison_rows.append(
            f'<tr data-pbj-geo-region-key="{rk}">'
            f"<td>{label}</td>"
            f'<td class="pbj-geo-num">{fc}</td>'
            f'<td class="pbj-geo-num{emph_cls}">{html.escape(str(emph_cell))}</td>'
            f'<td class="pbj-geo-num">{spark}</td>'
            f'<td class="pbj-geo-num">{_fmt_hprd(row.get(col_direct))}</td>'
            f'<td class="pbj-geo-num">{_fmt_hprd(row.get(col_rn))}</td>'
            f"</tr>"
        )

    empty_region_row = (
        f'<tr><td colspan="6">No {unit_plural.lower()} data for this quarter.</td></tr>'
    )

    outlier_html = _build_outlier_table_rows(outliers, display_map, limit=25)
    empty_outlier_row = (
        '<tr><td colspan="5">Not enough facilities for percentile ranking.</td></tr>'
    )

    empty_fac_row = '<tr><td colspan="4">No facilities.</td></tr>'
    empty_reg_outlier_row = '<tr><td colspan="4">No outlier flags for this region.</td></tr>'

    region_workspaces: list[str] = []
    for region_key, facs in sorted(facilities_by_region.items(), key=lambda x: x[0]):
        rk_raw = str(region_key)
        rk = html.escape(rk_raw)
        raw_label = str((facs[0] or {}).get("county_label") if facs else region_key)
        label_raw = _region_label(display_map, rk_raw, raw_label)
        label = html.escape(label_raw)
        fc = len(facs)
        fac_table_body = _build_facility_table_rows(facs)
        region_row = next((r for r in regions if str(r.get("county_key") or "") == rk_raw), {})
        ws_hidden = selected_region != rk_raw
        ws_class = " pbj-geo-view-hidden" if ws_hidden else ""
        regional_outlier_body = _build_outlier_table_rows(
            outliers, display_map, region_key=rk_raw, limit=15
        )
        fac_tbody = fac_table_body or empty_fac_row
        outlier_tbody = regional_outlier_body or empty_reg_outlier_row
        region_workspaces.append(
            f'<div class="pbj-geo-region-workspace{ws_class}" data-pbj-geo-region-key="{rk}"'
            f'{" hidden" if ws_hidden else ""}>'
            f'<div class="pbj-geo-premium-card">'
            f'<div class="pbj-geo-premium-workspace-head">'
            f"<h3>{label}</h3>"
            f'<button type="button" class="pbj-geo-back-statewide">← Statewide view</button>'
            f"</div>"
            + _metrics_pods(
                [
                    ("Facilities", str(fc)),
                    ("Total nurse HPRD", _fmt_hprd(region_row.get("Total_Nurse_HPRD"))),
                    ("Direct care HPRD", _fmt_hprd(region_row.get("Nurse_Care_HPRD"))),
                ]
            )
            + f'<h4 class="pbj-geo-premium-workspace-subhead">Facilities in this {unit_short.lower()}</h4>'
            f'<div class="pbj-geo-premium-table-wrap">'
            f'<table class="pbj-geo-premium-table" aria-label="Facilities in {label}">'
            f"<thead><tr><th>CCN</th><th>Facility</th>"
            f'<th class="pbj-geo-num">Total nurse HPRD</th>'
            f'<th class="pbj-geo-num">Direct care HPRD</th>'
            f"</tr></thead>"
            f"<tbody>{fac_tbody}</tbody>"
            f"</table></div>"
            f'<h4 class="pbj-geo-premium-workspace-subhead">Low staffing flags in this {unit_short.lower()}</h4>'
            f'<p class="pbj-geo-premium-section-lead">Lowest total nurse HPRD percentiles among facilities in {label}.</p>'
            f'<div class="pbj-geo-premium-table-wrap">'
            f'<table class="pbj-geo-premium-table" aria-label="Regional outlier rankings for {label}">'
            f"<thead><tr><th>CCN</th><th>Facility</th>"
            f'<th class="pbj-geo-num">HPRD</th><th class="pbj-geo-num">Percentile</th>'
            f"</tr></thead>"
            f"<tbody>{outlier_tbody}</tbody>"
            f"</table></div>"
            f"</div></div>"
        )

    state_hprd = _fmt_metric_display(state_metric_float, display_format=display_format)
    nat_hprd = _fmt_hprd(national_metrics.get("Total_Nurse_HPRD"))
    regions_count = str(coverage.get("regions_reporting") or len(regions))

    hprd_trigger, hprd_modal = ("", "")
    if selected_metric_id == "total_nurse_hprd":
        hprd_trigger, hprd_modal = _hprd_explainer_block(
            hprd_display=state_hprd,
            na_hprd=state_metrics.get("Nurse_Assistant_HPRD"),
            state_name=state_name,
            uid=f"geo-premium-{state_slug}-{q}",
        )

    coverage_note = _render_coverage_note(coverage, labels, q_display)

    map_json = json.dumps(
        {
            "quarter": q,
            "quarterDisplay": q_display,
            "stateCode": state_code,
            "metricId": selected_metric_id,
            "metricDisplayName": metric_display_name,
            "stateValue": state_metric_float,
            "selectedRegion": selected_region,
            "regions": region_metrics,
            "viewBox": map_data.get("viewBox"),
            "paths": {
                rk: {"d": (geom or {}).get("d")}
                for rk, geom in (map_data.get("regions") or {}).items()
                if isinstance(geom, dict)
            },
        }
    )

    region_prompt_hidden = " pbj-geo-view-hidden" if selected_region else ""

    brand_pill = _brand_pill_html()
    hprd_inner = ""
    if hprd_trigger:
        hprd_inner = hprd_trigger.replace('<div class="pbj-geo-hprd-explainer">', "", 1)
        if hprd_inner.endswith("</div>"):
            hprd_inner = hprd_inner[:-6]
    hprd_wrap = (
        f'<div class="pbj-geo-premium-hprd-explainer">{hprd_inner}</div>'
        if hprd_inner
        else ""
    )

    page_html = f"""
<div class="pbj-geo-premium-page">
  <header class="pbj-geo-premium-hero">
    <p class="pbj-geo-premium-product-line">
      <img src="/pbj_favicon.png" width="28" height="28" alt="" class="pbj-geo-premium-product-icon" decoding="async">
      <span class="pbj-geo-premium-product-text">PBJ320 Nursing Home Staffing Intelligence</span>
      <span class="pbj-geo-premium-product-badge">Premium</span>
    </p>
    <p class="pbj-geo-premium-eyebrow">
      {brand_pill}
      <span class="pbj-geo-premium-eyebrow-suffix">Regional intelligence</span>
    </p>
    <h1 class="pbj-geo-premium-title">{esc_state} Staffing by Planning Region</h1>
    <p class="pbj-geo-premium-subtitle">
      Compare nursing-home staffing across {esc_state}&rsquo;s {n_regions} planning regions
      and review facility-level patterns.
    </p>
    <p class="pbj-geo-premium-meta">
      <strong>{html.escape(q_display)}</strong>
      &middot; {n_fac} facilities
      &middot; CMS PBJ quarterly staffing data
    </p>
  </header>

  <div class="pbj-geo-premium-filters">
    <form method="get" id="pbjGeoQuarterForm" class="pbj-geo-premium-filter-group">
      <label for="pbjGeoQuarterSelect">Data period</label>
      <select id="pbjGeoQuarterSelect" name="quarter"
        class="form-select form-select-sm pbj-geo-premium-filter-control" aria-label="Select PBJ data quarter"
        onchange="this.form.submit()">{quarter_options}</select>
      <input type="hidden" name="region" id="pbjGeoQuarterRegionHidden" value="{html.escape(selected_region)}">
      <input type="hidden" name="metric" id="pbjGeoQuarterMetricHidden" value="{html.escape(selected_metric_id)}">
    </form>
    <div class="pbj-geo-premium-filter-group">
      <label for="pbjGeoMetricSelect">Staffing metric</label>
      <select id="pbjGeoMetricSelect" name="metric"
        class="form-select form-select-sm pbj-geo-premium-filter-control"
        aria-label="Select PBJ quarterly staffing metric"
        title="{html.escape(metric_description)}"
        onchange="document.getElementById('pbjGeoQuarterForm').submit()">{metric_options}</select>
    </div>
    <div class="pbj-geo-premium-filter-group">
      <label for="pbjGeoRegionSelect">Planning region</label>
      <select id="pbjGeoRegionSelect" class="form-select form-select-sm pbj-geo-premium-filter-control"
        aria-label="Select planning region or statewide">
        {''.join(region_select_options)}
      </select>
    </div>
  </div>

  <section class="pbj-geo-premium-section" aria-labelledby="pbjGeoGlanceHeading">
    <h2 id="pbjGeoGlanceHeading" class="pbj-geo-premium-section-title">Regional {html.escape(metric_display_name)} at a glance</h2>
    <div class="pbj-geo-premium-glance-grid">
      <div class="pbj-geo-premium-card pbj-geo-premium-map-wrap">{map_html}</div>
      <div class="pbj-geo-premium-card">{bar_html}</div>
    </div>
  </section>

  <section class="pbj-geo-premium-section" aria-labelledby="pbjGeoSummaryHeading">
    <h2 id="pbjGeoSummaryHeading" class="pbj-geo-premium-section-title">{esc_state} summary</h2>
    <div class="pbj-geo-premium-card">
      {_metrics_pods([
          (f"{esc_state} {metric_display_name}", state_hprd),
          ("National total nurse HPRD", nat_hprd),
          (labels["unit_plural"], regions_count),
      ])}
      {hprd_wrap}
    </div>
  </section>

  <section class="pbj-geo-premium-section" aria-labelledby="pbjGeoComparisonHeading">
    <h2 id="pbjGeoComparisonHeading" class="pbj-geo-premium-section-title">{unit_plural} comparison</h2>
    <div class="pbj-geo-premium-table-wrap" id="pbjGeoRegionTable">
      <table class="pbj-geo-premium-table" aria-label="{unit_plural} staffing comparison">
        <thead><tr>
          <th>{unit_short}</th>
          <th class="pbj-geo-num">Facilities</th>
          <th class="pbj-geo-num pbj-geo-metric-emphasis">{html.escape(metric_display_name)}</th>
          <th class="pbj-geo-num">4-q trend</th>
          <th class="pbj-geo-num">Direct care HPRD</th>
          <th class="pbj-geo-num">RN HPRD</th>
        </tr></thead>
        <tbody>{''.join(comparison_rows) if comparison_rows else empty_region_row}</tbody>
      </table>
    </div>
  </section>

  <section class="pbj-geo-premium-section" aria-labelledby="pbjGeoOutliersHeading">
    <h2 id="pbjGeoOutliersHeading" class="pbj-geo-premium-section-title">Facilities to review statewide</h2>
    <p class="pbj-geo-premium-section-lead">Facilities with the lowest within-state total nurse HPRD for {html.escape(q_display)}.</p>
    <div class="pbj-geo-premium-table-wrap">
      <table class="pbj-geo-premium-table" aria-label="Statewide facility outlier rankings">
        <thead><tr>
          <th>CCN</th><th>Facility</th><th>Region</th>
          <th class="pbj-geo-num">Total nurse HPRD</th><th class="pbj-geo-num">Within-state rank</th>
        </tr></thead>
        <tbody>{outlier_html or empty_outlier_row}</tbody>
      </table>
    </div>
  </section>

  <section class="pbj-geo-premium-section" aria-labelledby="pbjGeoRegionFacHeading">
    <h2 id="pbjGeoRegionFacHeading" class="pbj-geo-premium-section-title">Facilities in selected planning region</h2>
    <p class="pbj-geo-premium-region-note pbj-geo-region-prompt{region_prompt_hidden}">
      Select a {unit_short.lower()} on the map, bar chart, or comparison table
      to review facility-level staffing in that area.
    </p>
    {''.join(region_workspaces)}
  </section>

  <p class="pbj-geo-premium-methodology">
    Data period <strong>{html.escape(q_display)}</strong>{canonical_note}.
    {unit} rollups from CMS PBJ quarterly data.
    Map and ranked comparison use <strong>{html.escape(metric_display_name)}</strong>
    ({html.escape(metric_description)}).
    Additional role columns remain fixed; this is not an employee headcount or ownership selector.
  </p>
  {coverage_note}
  <script type="application/json" id="pbjGeoMapData">{map_json}</script>
  <script>{GEO_PREMIUM_JS}</script>
</div>
"""
    return page_html, hprd_modal or ""


def generate_geo_intelligence_premium_html(
    *,
    state_name: str,
    state_slug: str,
    state_code: str,
    bundle: dict[str, Any],
    quarter: str,
    region: str = "",
    metric: str = "",
    site_origin: str = "https://www.pbj320.com",
    app_root: str = "",
) -> str:
    """Full premium geographic intelligence HTML document."""
    q = quarter or str(bundle.get("canonical_quarter") or "")
    quarters = list(bundle.get("quarters") or [])
    if q not in quarters and quarters:
        q = quarters[-1]

    content, hprd_modal = generate_premium_geo_content(
        state_name=state_name,
        state_slug=state_slug,
        state_code=state_code,
        bundle=bundle,
        quarter=q,
        region=region,
        metric=metric,
        app_root=app_root,
    )

    page_title = f"{state_name} Staffing by Planning Region | PBJ320 Premium"
    meta_description = (
        f"Compare nursing-home staffing across {state_name} planning regions. "
        f"Regional map, HPRD comparison, and facility-level patterns from CMS PBJ data."
    )
    canonical_url = f"{site_origin.rstrip('/')}/premium/{state_slug}"
    query: list[str] = []
    if q and q != bundle.get("canonical_quarter"):
        query.append(f"quarter={q}")
    if str(region or "").strip():
        query.append(f"region={region.strip()}")
    if str(metric or "").strip():
        query.append(f"metric={metric.strip()}")
    if query:
        canonical_url = f"{canonical_url}?{'&'.join(query)}"

    head = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#312e81">
<meta name="color-scheme" content="light">
<title>{html.escape(page_title)}</title>
<meta name="description" content="{html.escape(meta_description)}">
<link rel="canonical" href="{html.escape(canonical_url, quote=True)}">
{render_premium_head_extras()}
<style>{GEO_PREMIUM_CSS}</style>
</head>
<body class="pbj-premium-hub pbj-geo-premium-body">
<a href="#main-content" class="visually-hidden-focusable btn btn-sm btn-primary position-fixed top-0 start-0 m-2" style="z-index:1080;">Skip to main content</a>
{render_premium_nav(active="regional")}
<div class="pbj-premium-shell" style="padding-top: var(--pbj-static-nav-pad, 4rem);">
<main id="main-content" class="pbj-premium-main" style="max-width:1200px;margin:0 auto;padding:0 clamp(0.75rem,2vw,1.25rem) 2.5rem;">
{content}
</main>
</div>
{hprd_modal}
</body>
</html>"""
    return head
