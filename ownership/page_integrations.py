"""
HTML snippets linking provider / state / entity pages to CHOW and ownership tools.
"""
from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import quote

from ownership.chow_display import (
    CHOW_TABLE_INIT_SCRIPT,
    render_chow_events_table,
)
from ownership.chow_lookup import (
    _load_index,
    _party_list_from_records,
    chow_count_for_state,
    chow_index_date_range_label,
    chow_records_for_ccn,
    chow_records_for_party,
    chow_records_for_state,
    chow_state_stats,
    format_chow_date,
)
from ownership.beta_gate import ownership_beta_enabled_for_state
from ownership.display_format import format_org_display, format_role_text

# Back-compat alias used in this module
_format_org_display = format_org_display


def _chow_filter_url(party: dict[str, Any], side: str, state_code: str | None = None) -> str:
    name = party.get("name") or ""
    q = f"/chow?{side}={quote(name)}"
    if state_code:
        q += f"&state={quote(state_code.upper()[:2])}"
    return q


def _party_org_name_cell(party: dict[str, Any], side: str, state_code: str, name: str) -> str:
    """Organization name links to owner profile when known, else CHOW filter."""
    owner_url = str(party.get("owner_url") or "").strip()
    display = html.escape(name)
    if owner_url:
        title = html.escape("CMS owner / enrollment profile on PBJ320", quote=True)
        return f'<a href="{html.escape(owner_url)}" title="{title}">{display}</a>'
    filter_href = html.escape(_chow_filter_url(party, side, state_code))
    return f'<a href="{filter_href}">{display}</a>'


def _facility_link_from_record(rec: dict[str, Any]) -> str:
    ccn = str(rec.get("ccn") or "").strip().zfill(6)[-6:]
    fac = _format_org_display(
        rec.get("facility_display_name") or rec.get("buyer_dba_name") or ccn or "—"
    )
    if ccn.isdigit():
        return f'<a href="/provider/{html.escape(ccn)}">{html.escape(fac)}</a>'
    return html.escape(fac)


def _party_chow_events(
    party: dict[str, Any], side: str, state_code: str, st_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    norm = str(party.get("normalized") or "").strip()
    events = chow_records_for_party(norm, side, state_code, limit=0)
    if not events and norm:
        norm_key = f"{side}_normalized"
        events = [r for r in st_rows if str(r.get(norm_key) or "").strip() == norm]
        events.sort(key=lambda r: r.get("effective_date") or "", reverse=True)
    return events


def _chow_event_line(rec: dict[str, Any], side: str) -> str:
    eff = html.escape(format_chow_date(str(rec.get("effective_date") or "")))
    fac = _facility_link_from_record(rec)
    if side == "buyer":
        other = html.escape(_format_org_display(rec.get("seller_org_name") or "—"))
        other_lbl = "seller"
    else:
        other = html.escape(
            _format_org_display(rec.get("buyer_org_name") or rec.get("buyer_dba_name") or "—")
        )
        other_lbl = "buyer"
    return (
        f'<span class="chow-party-ev-date">{eff}</span> {fac} '
        f'<span class="chow-party-ev-muted">({other_lbl}: {other})</span>'
    )


def _party_latest_date(
    party: dict[str, Any], side: str, state_code: str, st_rows: list[dict[str, Any]]
) -> str:
    events = _party_chow_events(party, side, state_code, st_rows)
    if not events:
        return ""
    return max(str(r.get("effective_date") or "") for r in events)


def _render_party_chow_cell(
    party: dict[str, Any],
    side: str,
    state_code: str,
    st_rows: list[dict[str, Any]],
) -> str:
    """Latest transaction first; older events in one expandable list (consistent layout)."""
    events = _party_chow_events(party, side, state_code, st_rows)
    n = len(events)
    if n == 0:
        return "—"

    events = sorted(events, key=lambda r: str(r.get("effective_date") or ""), reverse=True)
    latest = events[0]
    filter_href = html.escape(_chow_filter_url(party, side, state_code))

    latest_block = (
        '<div class="chow-party-stack">'
        '<span class="chow-party-stack-label">Latest</span> '
        f'<div class="chow-party-stack-line">{_chow_event_line(latest, side)}</div>'
        "</div>"
    )

    if n == 1:
        return latest_block

    older = events[1:8]
    items = [f"<li>{_chow_event_line(rec, side)}</li>" for rec in older]
    if n > 8:
        items.append(
            f'<li class="chow-party-ev-more"><a href="{filter_href}">'
            f"All {n:,} on CHOW monitor</a></li>"
        )
    older_label = f"{n - 1} earlier transaction{'s' if n - 1 != 1 else ''}"
    return (
        latest_block
        + f'<details class="chow-party-roll chow-party-roll--older">'
        f'<summary class="chow-party-roll-summary">{older_label}</summary>'
        f'<ul class="chow-party-events-list">{"".join(items)}</ul>'
        f"</details>"
        + f'<p class="chow-party-roll-foot">'
        f'<a href="{filter_href}">Filter on CHOW monitor</a></p>'
    )


def _sort_parties_for_display(
    parties: list[dict[str, Any]],
    *,
    side: str = "buyer",
    state_code: str = "",
    st_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Sort by most recent CHOW date (primary), then event count."""
    if not parties:
        return []
    st = st_rows or []

    def sort_key(p: dict[str, Any]) -> tuple:
        latest = _party_latest_date(p, str(p.get("side") or side), state_code, st)
        return (
            latest,
            -int(p.get("count") or 0),
            str(p.get("name") or "").upper(),
        )

    return sorted(parties, key=sort_key, reverse=True)


def _org_link_from_chow_record(rec: dict[str, Any], side: str) -> str:
    """Buyer or seller name with owner profile or CHOW filter link."""
    st = str(rec.get("state") or "").strip().upper()[:2]
    if side == "buyer":
        raw = rec.get("buyer_org_name") or rec.get("buyer_dba_name") or ""
        url = str(rec.get("buyer_owner_url") or "").strip()
        filter_side = "buyer"
    else:
        raw = rec.get("seller_org_name") or ""
        url = str(rec.get("seller_owner_url") or "").strip()
        filter_side = "seller"
    display = html.escape(_format_org_display(str(raw).strip() or "—"))
    if url:
        return f'<a href="{html.escape(url)}">{display}</a>'
    if not str(raw).strip():
        return "—"
    href = html.escape(_chow_filter_url({"name": raw}, filter_side, st))
    return f'<a href="{href}">{display}</a>'


def _render_state_chow_recent_table(state_code: str, *, limit: int = 10) -> str:
    """One row per CMS transaction (not separate buyer/seller party rows)."""
    st = state_code.upper()[:2]
    recent = chow_records_for_state(st, limit=limit)
    if not recent:
        return '<p class="pbj-meta-line">No transactions in this state index.</p>'

    table_inner = render_chow_events_table(
        recent, org_link_fn=_org_link_from_chow_record, max_rows=limit
    )
    total = chow_count_for_state(st)
    more = ""
    if total > len(recent):
        more = (
            f'<p class="chow-state-tx-more">'
            f"Showing {len(recent)} most recent of {total:,}. "
            f'<a href="/chow?state={html.escape(st)}">Browse all</a></p>'
        )

    return table_inner + more + CHOW_TABLE_INIT_SCRIPT


def render_state_top_owners_block(state_code: str, state_name: str = "") -> str:
    """Top ownership organizations in this state (by CHOW transaction count)."""
    st = str(state_code or "").strip().upper()[:2]
    if not ownership_beta_enabled_for_state(st):
        return ""
    if not st:
        return ""
    st_rows = chow_records_for_state(st, limit=0)
    if not st_rows:
        return ""

    merged: dict[str, dict[str, Any]] = {}
    for side in ("buyer", "seller"):
        for p in _party_list_from_records(st_rows, side, 10):
            key = str(p.get("normalized") or p.get("name") or "").strip()
            if not key:
                continue
            prev = merged.get(key)
            if not prev or int(p.get("count") or 0) > int(prev.get("count") or 0):
                merged[key] = {**p, "side": side}

    top = sorted(merged.values(), key=lambda x: (-int(x.get("count") or 0), str(x.get("name") or "")))[:8]
    if not top:
        return ""

    label = html.escape(state_name or st)
    trs: list[str] = []
    for p in top:
        name = _format_org_display(str(p.get("name") or "—"))
        side = str(p.get("side") or "buyer")
        side_lbl = "Buyer" if side == "buyer" else "Seller"
        cnt = int(p.get("count") or 0)
        name_cell = _party_org_name_cell(p, side, st, name)
        trs.append(
            f"<tr><td class=\"chow-org-name\">{name_cell}</td>"
            f"<td class=\"num\">{cnt}</td>"
            f"<td>{html.escape(side_lbl)}</td></tr>"
        )

    return (
        f'<details class="pbj-details pbj-details-top-owners" style="margin-top:1.25rem;">'
        f'<summary><span class="pbj-details-icon" aria-hidden="true">▼</span> '
        f"Top ownership organizations · {label}</summary>"
        f'<div class="pbj-details-content chow-state-block">'
        f'<p class="chow-state-lead">Organizations with the most reported ownership transactions in {label}.</p>'
        f'<div class="chow-table-scroll chow-state-owners-scroll">'
        f'<table class="chow-table chow-state-owners-table">'
        f"<thead><tr><th>Organization</th><th class=\"num\">Txns</th><th>Role</th></tr></thead>"
        f"<tbody>{''.join(trs)}</tbody></table></div></div></details>"
    )


def render_state_chow_block(state_code: str, state_name: str = "") -> str:
    """Collapsible CHOW summary at bottom of state pages."""
    st = str(state_code or "").strip().upper()[:2]
    if not ownership_beta_enabled_for_state(st):
        return ""
    cnt = chow_count_for_state(state_code)
    if cnt <= 0:
        return ""
    label = html.escape(state_name or st)
    stats = chow_state_stats(st)
    events = stats.get("events") or cnt
    u_ccn = stats.get("unique_facilities") or 0

    date_rng = html.escape(chow_index_date_range_label())
    meta_bits = [f"{events:,} CMS transactions", f"{u_ccn:,} facilities"]
    if date_rng:
        meta_bits.append(date_rng)
    lead = (
        f'<p class="chow-state-lead">{" · ".join(meta_bits)} in {label}. '
        "Reported enrollment changes—not proof of staffing or care quality.</p>"
    )

    table_html = _render_state_chow_recent_table(st, limit=10)
    summary_label = f"Ownership changes · {events:,}"

    return (
        f'<details class="pbj-details pbj-details-ownership-chow" style="margin-top:1.5rem;">'
        f'<summary><span class="pbj-details-icon" aria-hidden="true">▼</span> '
        f"{html.escape(summary_label)}</summary>"
        f'<div class="pbj-details-content chow-state-block">'
        f"{lead}"
        f"{table_html}"
        f'<p class="chow-state-foot">'
        f'<a href="/chow?state={html.escape(st)}">Browse all {html.escape(st)} CHOW records</a>'
        f"</p></div></details>"
    )


def render_state_chow_line(state_code: str, state_name: str = "") -> str:
    """Legacy one-line CHOW link (prefer render_state_chow_block)."""
    st = str(state_code or "").strip().upper()[:2]
    if not ownership_beta_enabled_for_state(st):
        return ""
    cnt = chow_count_for_state(state_code)
    if cnt <= 0:
        return ""
    st = html.escape(str(state_code).upper()[:2])
    label = html.escape(state_name or state_code)
    return (
        f'<p class="pbj-meta-line" style="margin-top:0.5rem;">'
        f"<strong>Ownership changes:</strong> {cnt:,} reported CMS CHOW events for {label}. "
        f'<a href="/chow?state={st}">View {st} CHOW records</a>'
        "</p>"
    )


def _render_control_parties_table(parties: list[dict[str, Any]], *, preview: int = 15) -> str:
    if not parties:
        return '<p class="pbj-meta-line">No owner or control parties listed for this enrollment.</p>'
    trs: list[str] = []
    for p in parties[:preview]:
        raw_name = p.get("name") or "—"
        pname = html.escape(
            format_org_display(str(raw_name)) if raw_name != "—" else "—"
        )
        ptype = html.escape(p.get("party_type") or "—")
        roles = "; ".join(
            html.escape(format_role_text(r)) for r in (p.get("roles") or [])[:2]
        )
        pcts = ", ".join(html.escape(x) for x in (p.get("pcts") or [])[:2] if x)
        dates = (p.get("association_dates") or [])[:1]
        since = html.escape(format_chow_date(dates[0]) if dates else "—")
        owner_url = p.get("profile_url") or ""
        name_cell = (
            f'<a href="{html.escape(owner_url)}">{pname}</a>'
            if owner_url and p.get("is_owner_control_pac")
            else pname
        )
        trs.append(
            f"<tr><td>{name_cell}</td><td>{ptype}</td><td>{roles or '—'}</td>"
            f'<td class="num">{pcts or "—"}</td><td>{since}</td></tr>'
        )
    extra = ""
    if len(parties) > preview:
        extra = (
            f'<p class="pbj-meta-line" style="margin:0.5rem 0 0;">'
            f"Showing {preview} of {len(parties)} parties.</p>"
        )
    return (
        f"{extra}"
        '<div class="chow-table-scroll" style="max-height:360px;">'
        '<table class="chow-table chow-provider-owners-table"><thead><tr>'
        "<th>Name</th><th>Type</th><th>Role(s)</th><th>%</th><th>Since</th>"
        "</tr></thead><tbody>"
        + "".join(trs)
        + "</tbody></table></div>"
    )


def _render_provider_chow_block(ccn_norm: str) -> str:
    """Inline CHOW table on provider ownership section (toggle via button)."""
    rows = chow_records_for_ccn(ccn_norm, limit=0) if ccn_norm else []
    if not rows:
        return ""
    n = len(rows)
    uid = re.sub(r"[^a-zA-Z0-9_-]", "", ccn_norm)[:12]
    panel_id = f"providerChowPanel-{uid}"
    btn_id = f"providerChowBtn-{uid}"
    label = f"View {n:,} CHOW record{'s' if n != 1 else ''} for this facility"
    table = render_chow_events_table(
        rows[:40],
        org_link_fn=_org_link_from_chow_record,
        max_rows=40,
        table_class="chow-table chow-tx-table chow-tx-table--provider",
    )
    more = ""
    if n > 40:
        more = (
            f'<p class="pbj-meta-line chow-tx-more">Showing 40 of {n:,} records.</p>'
        )
    return (
        '<div class="provider-chow-block">'
        '<p class="provider-chow-heading"><strong>Ownership changes (CHOW)</strong></p>'
        f'<button type="button" class="chow-btn chow-btn-chow chow-btn-chow-toggle" '
        f'id="{btn_id}" aria-controls="{panel_id}" aria-expanded="false">'
        f"{html.escape(label)}</button>"
        f'<div id="{panel_id}" class="provider-chow-panel" hidden>'
        f"{table}{more}</div></div>"
        + CHOW_TABLE_INIT_SCRIPT
    )


def render_provider_ownership_chow_block(
    ccn: str,
    *,
    provider_info_row: dict[str, Any] | None = None,
) -> str:
    """CMS all-owners + CHOW footer for provider pages (collapsed by default)."""
    from ownership.owner_profile import lookup_cms_ownership_for_provider

    pi = provider_info_row or {}
    prov_state = str(
        pi.get("state")
        or pi.get("STATE")
        or pi.get("Provider State")
        or ""
    ).strip().upper()[:2]
    if not ownership_beta_enabled_for_state(prov_state):
        return ""
    ccn_norm = str(ccn or "").strip().zfill(6)[-6:]

    ownership_type = str(
        pi.get("ownership_type") or pi.get("Ownership_Type") or ""
    ).strip()
    chow_flag = str(
        pi.get("provider_changed_ownership_in_last_12_months")
        or pi.get("Provider Changed Ownership in Last 12 Months")
        or ""
    ).strip().upper()
    chow_all = chow_records_for_ccn(ccn_norm, limit=0) if ccn_norm else []
    cms = lookup_cms_ownership_for_provider(pi)

    if not ownership_type and chow_flag != "Y" and not chow_all and not cms:
        return ""

    lines: list[str] = []
    if ownership_type:
        lines.append(
            f'<p class="pbj-meta-line" style="margin:0 0 0.5rem;">'
            f"<strong>Ownership type (Care Compare):</strong> {html.escape(ownership_type)}</p>"
        )

    if cms:
        en_name = html.escape(_format_org_display(cms.get("enrollment_name") or ""))
        en_url = html.escape(str(cms.get("enrollment_profile_url") or ""))
        matched = html.escape(_format_org_display(str(cms.get("matched_via") or "")))
        lines.append(
            f'<p class="pbj-meta-line" style="margin:0.75rem 0 0.35rem;">'
            f"<strong>CMS enrollment:</strong> "
            f'<a href="{en_url}">{en_name}</a>'
            f' <span class="chow-top-scope">(matched on legal name: {matched})</span></p>'
        )
        lines.append(
            '<p class="pbj-meta-line" style="margin:0 0 0.5rem;">'
            "Reported owners and control parties:</p>"
        )
        lines.append(_render_control_parties_table(cms.get("control_parties") or []))

    if chow_flag == "Y":
        lines.append(
            '<p class="pbj-meta-line" style="margin:0.75rem 0 0.5rem;">'
            "Care Compare: ownership change in the last 12 months.</p>"
        )
    chow_html = _render_provider_chow_block(ccn_norm) if chow_all else ""

    return (
        '<details class="pbj-details pbj-details-ownership pbj-page-bottom-details">'
        '<summary><span class="pbj-details-icon" aria-hidden="true">▼</span> '
        "Ownership</summary>"
        '<div class="pbj-details-content pbj-ownership-chow-content">'
        + "".join(lines)
        + chow_html
        + '<p class="pbj-meta-line" style="margin:0.5rem 0 0;font-size:0.82rem;">'
        "CMS-reported roles only—not proof of who operates the facility or care quality."
        "</p>"
        "</div>"
        "</details>"
    )


def render_entity_ownership_tools_block() -> str:
    return ""
