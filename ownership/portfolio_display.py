"""Shared portfolio snapshot + CMS star distribution HTML for owner and entity pages."""
from __future__ import annotations

import html
from typing import Any

from ownership.owner_portfolio_metrics import (
    PORTFOLIO_HPRD_MAX,
    PORTFOLIO_HPRD_MIN,
    PORTFOLIO_OVERALL_RATING_MAX,
    PORTFOLIO_OVERALL_RATING_MIN,
    PORTFOLIO_STAR_DIST_MIN,
)


def info_button_html(
    title: str, body: str, *, label: str = "?", cls: str = "owner-info-btn"
) -> str:
    extra = ""
    if "owner-info-btn" not in cls.split():
        extra = " owner-info-btn"
    return (
        f'<button type="button" class="{cls}{extra}" data-owner-info '
        f'data-info-title="{html.escape(title, quote=True)}" '
        f'data-info-body="{html.escape(body, quote=True)}">'
        f"{html.escape(label)}</button>"
    )


def portfolio_info_modal_html() -> str:
    return """
      <dialog class="owner-info-modal" id="ownerInfoModal" aria-labelledby="ownerInfoModalTitle">
        <div class="owner-info-modal-card">
          <header class="owner-info-modal-header">
            <h2 id="ownerInfoModalTitle">Details</h2>
            <button type="button" class="owner-info-modal-close" data-owner-info-close aria-label="Close">×</button>
          </header>
          <div class="owner-info-modal-body" id="ownerInfoModalBody"></div>
        </div>
      </dialog>"""


def snapshot_metric_card_html(
    label: str,
    value: str,
    help_title: str,
    help_body: str,
    *,
    tone: str = "",
    value_title: str = "",
) -> str:
    tone_cls = f" owner-snapshot-card--{tone}" if tone else ""
    value_tip = html.escape(value_title, quote=True) if value_title else ""
    value_attrs = f' title="{value_tip}" aria-label="{value_tip}"' if value_tip else ""
    return (
        f'<div class="owner-snapshot-card{tone_cls}">'
        f'<div class="owner-snapshot-label">{html.escape(label)}</div>'
        f'<div class="owner-snapshot-value-row">'
        f'<div class="owner-snapshot-value"{value_attrs}>{value}</div>'
        f"{info_button_html(help_title, help_body)}"
        "</div></div>"
    )


def portfolio_distribution_list_html(
    counts: dict[int, int],
    *,
    row_labels: list[str] | None = None,
) -> str:
    total = sum(int(counts.get(i, 0) or 0) for i in range(1, 6))
    if total < 1:
        return ""
    peak = max(int(counts.get(i, 0) or 0) for i in range(1, 6)) or 1
    rows: list[str] = []
    for star in range(5, 0, -1):
        cnt = int(counts.get(star, 0) or 0)
        pct = int(round(100.0 * cnt / total)) if total else 0
        width = max(4, int(round(100.0 * cnt / peak))) if cnt else 0
        label = (
            row_labels[star - 1]
            if row_labels and len(row_labels) >= star
            else f"{star}\u2605"
        )
        rows.append(
            f'<li class="owner-dist-row">'
            f'<span class="owner-dist-label">{html.escape(label)}</span>'
            f'<span class="owner-dist-bar" role="presentation">'
            f'<span class="owner-dist-bar-fill" style="width:{width}%"></span></span>'
            f'<span class="owner-dist-count">{cnt} <span class="owner-dist-pct">({pct}%)</span></span>'
            f"</li>"
        )
    if not rows:
        return ""
    return f'<ul class="owner-dist-list">{"".join(rows)}</ul>'


def portfolio_distribution_bars_html(
    counts: dict[int, int],
    *,
    title: str,
    row_labels: list[str] | None = None,
) -> str:
    list_html = portfolio_distribution_list_html(counts, row_labels=row_labels)
    if not list_html:
        return ""
    return (
        f'<section class="owner-dist-card" aria-label="{html.escape(title)}">'
        f'<div class="owner-dist-card-head">'
        f'<h3 class="owner-dist-title">{html.escape(title)}</h3>'
        "</div>"
        f"{list_html}"
        "</section>"
    )


def portfolio_state_distribution_html(
    by_state: list[tuple[str, int]], n_total: int
) -> str:
    if not by_state or n_total < 2 or len(by_state) < 2:
        return ""
    peak = max(c for _, c in by_state) or 1
    rows: list[str] = []
    for st, cnt in by_state[:12]:
        pct = int(round(100.0 * cnt / n_total)) if n_total else 0
        width = max(4, int(round(100.0 * cnt / peak))) if cnt else 0
        rows.append(
            f'<li class="owner-dist-row">'
            f'<span class="owner-dist-label">{html.escape(st)}</span>'
            f'<span class="owner-dist-bar" role="presentation">'
            f'<span class="owner-dist-bar-fill owner-dist-bar-fill--state" style="width:{width}%"></span></span>'
            f'<span class="owner-dist-count">{cnt} <span class="owner-dist-pct">({pct}%)</span></span>'
            f"</li>"
        )
    return (
        '<section class="owner-dist-card" aria-label="Facilities by state">'
        '<div class="owner-dist-card-head">'
        '<h3 class="owner-dist-title">Facilities by state</h3>'
        "</div>"
        f'<ul class="owner-dist-list">{"".join(rows)}</ul>'
        "</section>"
    )


def portfolio_distribution_tabs_html(
    overall_list: str,
    staffing_list: str,
    *,
    overall_title: str,
    staffing_title: str,
    id_prefix: str = "ownerDist",
) -> str:
    o_title = html.escape(overall_title)
    s_title = html.escape(staffing_title)
    tab_overall = f"{id_prefix}TabOverall"
    tab_staffing = f"{id_prefix}TabStaffing"
    panel_overall = f"{id_prefix}PanelOverall"
    panel_staffing = f"{id_prefix}PanelStaffing"
    return (
        '<section class="owner-dist-card owner-dist-card--tabbed" data-owner-dist-tabs '
        'aria-label="CMS rating distributions">'
        '<div class="owner-dist-card-head">'
        f'<h3 class="owner-dist-title" data-owner-dist-title>{o_title}</h3>'
        '<div class="owner-dist-tablist" role="tablist" aria-label="Rating type">'
        f'<button type="button" class="owner-dist-tab is-active" role="tab" id="{tab_overall}" '
        f'data-dist-title="{o_title}" aria-selected="true" aria-controls="{panel_overall}" '
        'tabindex="0">Overall</button>'
        f'<button type="button" class="owner-dist-tab" role="tab" id="{tab_staffing}" '
        f'data-dist-title="{s_title}" aria-selected="false" aria-controls="{panel_staffing}" '
        'tabindex="-1">Staffing</button>'
        "</div></div>"
        f'<div class="owner-dist-tabpanel is-active" role="tabpanel" id="{panel_overall}" '
        f'aria-labelledby="{tab_overall}">{overall_list}</div>'
        f'<div class="owner-dist-tabpanel" role="tabpanel" id="{panel_staffing}" '
        f'aria-labelledby="{tab_staffing}" hidden>{staffing_list}</div>'
        "</section>"
    )


def portfolio_distribution_html(
    ps: dict[str, Any], *, id_prefix: str = "ownerDist"
) -> str:
    overall_title = "Overall CMS star rating"
    staffing_title = "Staffing CMS star rating"
    overall_list = ""
    staffing_list = ""
    n_ovr = int(ps.get("n_with_overall_for_dist") or 0)
    if n_ovr >= PORTFOLIO_STAR_DIST_MIN:
        overall_list = portfolio_distribution_list_html(
            ps.get("overall_star_counts") or {}
        )
    n_stf = int(ps.get("n_with_staffing_for_dist") or 0)
    if n_stf >= PORTFOLIO_STAR_DIST_MIN:
        staffing_list = portfolio_distribution_list_html(
            ps.get("staffing_star_counts") or {}
        )
    if overall_list and staffing_list:
        return portfolio_distribution_tabs_html(
            overall_list,
            staffing_list,
            overall_title=overall_title,
            staffing_title=staffing_title,
            id_prefix=id_prefix,
        )
    if overall_list:
        return portfolio_distribution_bars_html(
            ps.get("overall_star_counts") or {},
            title=overall_title,
        )
    if staffing_list:
        return portfolio_distribution_bars_html(
            ps.get("staffing_star_counts") or {},
            title=staffing_title,
        )
    return portfolio_state_distribution_html(
        list(ps.get("by_state") or []),
        int(ps.get("n_facilities") or 0),
    )


def _owner_snapshot_help(ps: dict[str, Any]) -> tuple[str, str, str, str]:
    n = int(ps.get("n_facilities") or 0)
    n_matched = int(ps.get("n_pbj_matched") or 0)
    n_suggested = int(ps.get("n_pbj_suggested") or 0)
    fac_help = (
        f"{n} facilities in CMS owner data for this party. "
        f"{n_matched} have a verified PBJ link (enrollment legal name = provider-info legal name)."
    )
    if n_suggested:
        fac_help += f" {n_suggested} use a tentative name match."
    ovr_help = (
        f"Simple average of CMS overall star ratings ({PORTFOLIO_OVERALL_RATING_MIN:g}–"
        f"{PORTFOLIO_OVERALL_RATING_MAX:g}) across PBJ-verified facilities. "
        "Not census-weighted. Missing or out-of-range values excluded."
    )
    hprd_help = (
        "Resident-weighted portfolio average: each facility's latest PBJ total nurse HPRD "
        "is weighted by census (or certified beds when census is missing), then combined. "
        f"PBJ-verified facilities only. HPRD below {PORTFOLIO_HPRD_MIN:g} or above "
        f"{PORTFOLIO_HPRD_MAX:g} excluded as implausible for quarterly PBJ."
    )
    stf_help = (
        "Simple average of CMS staffing star ratings (1–5) across PBJ-verified facilities. "
        "Missing or out-of-range values excluded."
    )
    return fac_help, ovr_help, hprd_help, stf_help


def entity_weighted_hprd_help_body(
    ps: dict[str, Any],
    *,
    wmean: float | None,
    umean: float | None,
    chain_hprd: float | None = None,
) -> str:
    """Help text for weighted HPRD card — notes simple/chain average when it differs."""
    n = int(ps.get("n_facilities") or 0)
    n_states = int(ps.get("n_states") or 0)
    lines = [
        "Resident-weighted average of latest PBJ total nurse HPRD across roster facilities, "
        "weighted by census (or certified beds when census is missing). "
        f"HPRD below {PORTFOLIO_HPRD_MIN:g} or above {PORTFOLIO_HPRD_MAX:g} excluded as implausible.",
    ]
    if chain_hprd is not None and wmean is not None and abs(chain_hprd - wmean) >= 0.01:
        lines.append(
            f"The PBJ Takeaway sentence uses {chain_hprd:.2f} HPRD from the CMS chain performance "
            f"file (CMS-published chain average). This card shows {wmean:.2f} HPRD from the PBJ320 "
            f"roster, weighted by facility size — larger nursing homes count more than small ones."
        )
    elif umean is not None and wmean is not None and abs(umean - wmean) >= 0.01:
        lines.append(
            f"Simple unweighted roster average: {umean:.2f} HPRD across {n} facilities. "
            f"This card shows {wmean:.2f} HPRD weighted by census or certified beds."
        )
    elif wmean is not None and n >= 2:
        lines.append(
            f"Each of the {n} roster facilities in {n_states} state(s) contributes in proportion "
            "to its census (or beds when census is missing)."
        )
    return "\n\n".join(lines)


def entity_takeaway_hprd_help_span_html(
    narrative_hprd: float,
    *,
    entity_name: str,
    weighted_hprd: float | None = None,
) -> str:
    """Dotted-underline HPRD in entity takeaway — hover tooltip like high-risk help."""
    val = f"{narrative_hprd:.2f}"
    entity_esc = html.escape(entity_name or "this chain")
    if weighted_hprd is not None:
        tip = (
            f"{val} is the average total nurse HPRD among {entity_esc} nursing homes. "
            f"The weighted average ({weighted_hprd:.2f} HPRD) weights each facility's census "
            "so that larger nursing homes count more than the smaller ones."
        )
    else:
        tip = f"{val} is the average total nurse HPRD among {entity_esc} nursing homes."
    return (
        f'<span class="pbj-high-risk-help-wrap">'
        f'<span class="pbj-high-risk-help">{html.escape(val)}</span>'
        f'<span class="pbj-high-risk-tooltip" role="tooltip">{html.escape(tip)}</span>'
        f"</span>"
    )


def _entity_snapshot_help(ps: dict[str, Any]) -> tuple[str, str, str, str]:
    n = int(ps.get("n_facilities") or 0)
    n_states = int(ps.get("n_states") or 0)
    fac_help = (
        f"{n} nursing home{'s' if n != 1 else ''} in this CMS affiliated-entity roster on PBJ320 "
        f"across {n_states} state{'s' if n_states != 1 else ''}. "
        "Counts match the facility table below."
    )
    ovr_help = (
        f"Simple average of CMS overall star ratings ({PORTFOLIO_OVERALL_RATING_MIN:g}–"
        f"{PORTFOLIO_OVERALL_RATING_MAX:g}) across roster facilities. "
        "Not census-weighted. Missing or out-of-range values excluded. "
        "Derived from PBJ320 provider info — not the CMS chain performance file."
    )
    hprd_help = (
        "Resident-weighted average of latest PBJ total nurse HPRD across roster facilities, "
        "weighted by census (or certified beds when census is missing). "
        f"HPRD below {PORTFOLIO_HPRD_MIN:g} or above {PORTFOLIO_HPRD_MAX:g} excluded as implausible."
    )
    stf_help = (
        "Simple average of CMS staffing star ratings (1–5) across roster facilities. "
        "Missing or out-of-range values excluded."
    )
    return fac_help, ovr_help, hprd_help, stf_help


def portfolio_snapshot_section_html(
    ps: dict[str, Any],
    *,
    context: str = "owner",
    chain_hprd: float | None = None,
) -> str:
    """Metric cards + star/state distribution. Empty when no facilities."""
    if not ps or not ps.get("n_facilities"):
        return ""

    n = int(ps.get("n_facilities") or 0)
    wmean = ps.get("wmean_hprd")
    umean = ps.get("umean_hprd")
    mean_ovr = ps.get("umean_overall_rating")
    if mean_ovr is None:
        mean_ovr = ps.get("mean_overall_rating")
    mean_stf = ps.get("umean_staffing_rating")
    if mean_stf is None:
        mean_stf = ps.get("mean_staffing_rating")

    cards: list[str] = []
    if context == "entity":
        _efac, ovr_help, _ehprd, stf_help = _entity_snapshot_help(ps)
        hprd_help = entity_weighted_hprd_help_body(
            ps, wmean=wmean, umean=umean, chain_hprd=chain_hprd
        )
        dist_prefix = "entityDist"
        aria = "Entity portfolio metrics"
        hprd_label = "Weighted total nurse HPRD" if n >= 2 else "Total nurse HPRD"
        if wmean is not None:
            cards.append(
                snapshot_metric_card_html(
                    hprd_label,
                    html.escape(f"{wmean:.2f}"),
                    hprd_label,
                    hprd_help,
                )
            )
        elif umean is not None:
            cards.append(
                snapshot_metric_card_html(
                    "Avg total nurse HPRD" if n >= 2 else "Total nurse HPRD",
                    html.escape(f"{umean:.2f}"),
                    hprd_label,
                    hprd_help.replace("Resident-weighted", "Unweighted"),
                )
            )
        if mean_ovr is not None and n >= 2:
            cards.append(
                snapshot_metric_card_html(
                    "Avg overall rating",
                    html.escape(f"{mean_ovr:.1f}"),
                    "Avg overall rating",
                    ovr_help,
                    tone="warn",
                )
            )
        elif mean_ovr is not None and n == 1:
            cards.append(
                snapshot_metric_card_html(
                    "Overall rating",
                    html.escape(f"{mean_ovr:.1f}"),
                    "Overall rating",
                    "CMS overall star rating for this facility.",
                    tone="warn",
                )
            )
        if mean_stf is not None and n >= 2:
            cards.append(
                snapshot_metric_card_html(
                    "Avg staffing rating",
                    html.escape(f"{mean_stf:.1f}"),
                    "Avg staffing rating",
                    stf_help,
                )
            )
    else:
        fac_help, ovr_help, hprd_help, stf_help = _owner_snapshot_help(ps)
        dist_prefix = "ownerDist"
        aria = "Portfolio metrics"
        cards.append(
            snapshot_metric_card_html(
                "Total Facilities",
                str(n),
                "Total Facilities",
                fac_help,
                tone="accent",
                value_title="Distinct CMS-linked facilities nationwide",
            )
        )
        if mean_ovr is not None and n >= 2:
            cards.append(
                snapshot_metric_card_html(
                    "Avg overall rating",
                    html.escape(f"{mean_ovr:.1f}"),
                    "Avg overall rating",
                    ovr_help,
                    tone="warn",
                )
            )
        elif mean_ovr is not None and n == 1:
            cards.append(
                snapshot_metric_card_html(
                    "Overall rating",
                    html.escape(f"{mean_ovr:.1f}"),
                    "Overall rating",
                    "CMS overall star rating for this facility.",
                    tone="warn",
                )
            )
        if wmean is not None:
            hprd_label = (
                "Weighted total nurse HPRD"
                if n >= 2
                else "Total nurse HPRD"
            )
            cards.append(
                snapshot_metric_card_html(
                    hprd_label,
                    html.escape(f"{wmean:.2f}"),
                    hprd_label,
                    hprd_help,
                )
            )
        elif umean is not None:
            hprd_label = "Avg total nurse HPRD" if n >= 2 else "Total nurse HPRD"
            cards.append(
                snapshot_metric_card_html(
                    hprd_label,
                    html.escape(f"{umean:.2f}"),
                    hprd_label,
                    hprd_help.replace("Resident-weighted", "Unweighted"),
                )
            )
        if mean_stf is not None and n >= 2:
            cards.append(
                snapshot_metric_card_html(
                    "Avg staffing rating",
                    html.escape(f"{mean_stf:.1f}"),
                    "Avg staffing rating",
                    stf_help,
                )
            )

    if context == "entity":
        grid_cols = "owner-portfolio-grid--3 entity-portfolio-grid--3"
    elif len(cards) >= 4:
        grid_cols = "owner-portfolio-grid--4"
    elif len(cards) == 2:
        grid_cols = "owner-portfolio-grid--2"
    else:
        grid_cols = "owner-portfolio-grid--3"

    dist_html = portfolio_distribution_html(ps, id_prefix=dist_prefix)
    roster_note = ""
    if context == "entity" and n < PORTFOLIO_STAR_DIST_MIN:
        roster_note = (
            '<p class="pbj-meta-line" style="margin:0.5rem 0 0;font-size:0.8125rem;">'
            "Star distributions appear when at least "
            f"{PORTFOLIO_STAR_DIST_MIN} facilities have CMS ratings. "
            "See per-facility ratings in the table below."
            "</p>"
        )

    return f"""
      <section class="owner-snapshot-section" aria-label="{html.escape(aria)}">
        <div class="owner-portfolio-grid {grid_cols}" aria-label="Portfolio summary metrics">
          {"".join(cards)}
        </div>
        {dist_html}
        {roster_note}
      </section>"""


def entity_portfolio_block_html(
    ps: dict[str, Any],
    *,
    chain_hprd: float | None = None,
    include_modal: bool = True,
) -> str:
    """Wrapper for entity pages: modal + portfolio snapshot (reuses owner CSS)."""
    section = portfolio_snapshot_section_html(
        ps, context="entity", chain_hprd=chain_hprd
    )
    if not section.strip():
        return ""
    modal = portfolio_info_modal_html() if include_modal else ""
    return (
        f'<div class="entity-portfolio-root">{modal}{section}</div>'
    )


def owner_portfolio_snapshot_html(profile: dict[str, Any]) -> str:
    ps = profile.get("portfolio_summary") or {}
    return portfolio_snapshot_section_html(ps, context="owner")
