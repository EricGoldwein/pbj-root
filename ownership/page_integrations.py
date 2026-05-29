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
    render_chow_paginate_footer,
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
from ownership.owner_profile import _ccn_to_state_from_search_index
from ownership.display_format import format_org_display, format_role_short, format_role_text


def _ownership_pct_own_label(raw: str) -> str:
    """Human-readable stake, e.g. 50 → '50% own' (omit empty/dash/zero)."""
    s = str(raw or "").strip()
    if not s or s in ("—", "-", "N/A", "n/a"):
        return ""
    if s.endswith("%"):
        core = s[:-1].strip().replace(",", "")
        if not core:
            return ""
        try:
            if float(core) == 0:
                return ""
        except ValueError:
            pass
        return f"{s} own"
    try:
        v = float(s.replace(",", ""))
        if v == 0:
            return ""
        if v == int(v):
            return f"{int(v)}% own"
        return f"{v:g}% own"
    except ValueError:
        return f"{s}% own" if "%" not in s else f"{s} own"


def _is_threshold_ownership_role(role: str) -> bool:
    """CMS threshold bucket (≥5% owner), not the reported stake — redundant when % is shown."""
    low = str(role or "").lower()
    if "5%" not in low and "5 percent" not in low:
        return False
    return (
        "greater" in low
        or "≥" in low
        or ">=" in low
        or ("ownership" in low and "interest" in low)
    )


def _party_role_and_ownership_cell(party: dict[str, Any]) -> str:
    """Stake first, then compact governance roles; drop ≥5% threshold labels when % is known."""
    pct_bits = [
        lbl
        for lbl in (_ownership_pct_own_label(x) for x in (party.get("pcts") or [])[:2])
        if lbl
    ]
    has_stake = bool(pct_bits)
    role_bits: list[str] = []
    for raw in party.get("roles") or []:
        if has_stake and _is_threshold_ownership_role(raw):
            continue
        short = format_role_short(raw)
        if not short or short == "—":
            continue
        if short not in role_bits:
            role_bits.append(short)
        if len(role_bits) >= 2:
            break
    parts: list[str] = []
    if pct_bits:
        parts.append(", ".join(html.escape(l) for l in pct_bits))
    if role_bits:
        parts.append("; ".join(html.escape(r) for r in role_bits))
    return "; ".join(parts) if parts else "—"


def _norm_name_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def _abbrev_provider_ownership_type(ownership_type: str) -> str:
    o = (ownership_type or "").lower()
    if "for profit" in o or "for-profit" in o:
        return "For-profit"
    if "non" in o and "profit" in o:
        return "Non-profit"
    if "government" in o:
        return "Government"
    return (ownership_type or "").strip()


def _provider_ownership_intro_html(ownership_type: str, cms: dict[str, Any] | None) -> str:
    """One scannable lead line; legal-name match in nested details when it adds information."""
    _ = ownership_type
    chips: list[str] = []
    match_details = ""
    if cms:
        en_name = _format_org_display(cms.get("enrollment_name") or "")
        en_url = html.escape(str(cms.get("enrollment_profile_url") or ""))
        if en_name and en_url:
            chips.append(
                f'<span class="pbj-ownership-chip">'
                f'<a href="{en_url}">{html.escape(en_name)}</a></span>'
            )
        matched = _format_org_display(str(cms.get("matched_via") or ""))
        matched_raw = str(cms.get("matched_via") or "")
        if matched_raw.startswith("ccn:"):
            match_details = ""
        elif matched and _norm_name_key(matched) != _norm_name_key(en_name):
            match_details = (
                '<details class="pbj-ownership-mini-details">'
                '<summary>Legal name match</summary>'
                f'<p class="pbj-ownership-mini-text">CMS enrollment matched on legal name '
                f"{html.escape(matched)}.</p></details>"
            )
    if not chips:
        return match_details
    lead = (
        '<p class="pbj-ownership-lead">'
        + '<span class="pbj-ownership-middot" aria-hidden="true">·</span>'.join(chips)
        + "</p>"
    )
    return lead + match_details


def _provider_ownership_about_html() -> str:
    return (
        '<div class="pbj-ownership-about-callout" role="note">'
        '<p class="pbj-ownership-about-text">'
        '<span class="pbj-ownership-about-text--full">'
        "CMS owner data roles and percentages are reported filings, "
        "not proof of who operates the facility or care quality."
        "</span>"
        '<span class="pbj-ownership-about-text--short">'
        "CMS owner filings; not proof of who operates the facility."
        "</span>"
        "</p></div>"
    )


# Back-compat alias used in this module
_format_org_display = format_org_display


def _party_org_name_cell(party: dict[str, Any], side: str, state_code: str, name: str) -> str:
    """Organization name links to owner profile when known; otherwise plain text."""
    owner_url = str(party.get("owner_url") or "").strip()
    display = html.escape(name)
    if owner_url:
        title = html.escape("CMS owner / enrollment profile on PBJ320", quote=True)
        return f'<a href="{html.escape(owner_url)}" title="{title}">{display}</a>'
    tip = html.escape(
        "No CMS owner profile link yet—verify name and role on CMS enrollment records.",
        quote=True,
    )
    return f'<span title="{tip}">{display}</span>'


def _facility_link_from_record(rec: dict[str, Any]) -> str:
    from ownership.chow_lookup import chow_facility_label

    ccn = str(rec.get("ccn") or "").strip().zfill(6)[-6:]
    fac_raw = chow_facility_label(rec)
    if fac_raw.startswith("CCN "):
        fac_label = fac_raw
    else:
        fac_label = _format_org_display(fac_raw) if fac_raw and fac_raw != "—" else "—"
    fac = fac_label
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
    *,
    preview: int = 2,
) -> str:
    events = _party_chow_events(party, side, state_code, st_rows)
    if not events:
        return "—"
    n = len(events)
    name = _format_org_display(str(party.get("name") or "—"))
    filter_href = html.escape(_chow_filter_url(party, side, state_code))
    latest = events[0]
    latest_block = (
        f'<div class="chow-party-ev-latest">{_chow_event_line(latest, side)}</div>'
    )
    if n <= 1:
        return latest_block
    items = "".join(
        f'<li>{_chow_event_line(r, side)}</li>' for r in events[1 : preview + 1]
    )
    if n > preview + 1:
        items += (
            f'<li class="chow-party-ev-more"><a href="{filter_href}">'
            f"+ {n - preview - 1} more</a></li>"
        )
    older_label = f"{n - 1} earlier transaction{'s' if n - 1 != 1 else ''}"
    return (
        latest_block
        + f'<details class="chow-party-roll chow-party-roll--older">'
        f'<summary class="chow-party-roll-summary">{older_label}</summary>'
        f'<ul class="chow-party-events-list">{items}</ul>'
        f"</details>"
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


def _facility_col_from_record(rec: dict[str, Any]) -> str:
    return _facility_link_from_record(rec)


def _state_ownership_summary_label(
    state_code: str,
    state_name: str,
    *,
    variant: str,
    count: int,
) -> str:
    """Compact one-line <summary> text for state ownership sections."""
    st = str(state_code or "").strip().upper()[:2]
    if len(st) == 2:
        short = f"{st}'s"
    else:
        short = html.escape((state_name or st).strip())
    if variant == "top_orgs":
        return f"{short} Top Ownership Orgs ({count})"
    return f"Recent Ownership Changes · {st} ({count:,})"


def _render_state_chow_recent_table(
    state_code: str,
    *,
    initial_visible: int = 10,
    page_size: int = 10,
) -> str:
    """One row per CMS transaction; inline pagination (no /chow monitor link)."""
    st = state_code.upper()[:2]
    all_rows = chow_records_for_state(st, limit=0)
    if not all_rows:
        return '<p class="pbj-meta-line">No transactions in this state index.</p>'

    initial = max(1, int(initial_visible))
    table_inner = render_chow_events_table(
        all_rows,
        org_link_fn=_org_link_from_chow_record,
        facility_link_fn=_facility_col_from_record,
        max_rows=len(all_rows),
        initial_visible=initial,
        mobile_change_stack=True,
    )
    foot = render_chow_paginate_footer(
        total=len(all_rows),
        initial_visible=initial,
        page_size=page_size,
    )
    return table_inner + foot + CHOW_TABLE_INIT_SCRIPT


def render_state_top_owners_block(state_code: str, state_name: str = "") -> str:
    """Top owner/control organizations in this state by linked facility count (CMS SNF All Owners)."""
    from ownership.owner_profile import top_owner_organizations_for_state

    st = str(state_code or "").strip().upper()[:2]
    if not ownership_beta_enabled_for_state(st):
        return ""
    if not st:
        return ""

    top = top_owner_organizations_for_state(st, limit=8)
    if not top:
        return ""

    label = html.escape(state_name or st)
    trs: list[str] = []
    for p in top:
        name = html.escape(_format_org_display(str(p.get("name") or "—")))
        cnt = int(p.get("facility_count") or 0)
        url = html.escape(str(p.get("profile_url") or ""))
        name_cell = f'<a href="{url}">{name}</a>' if url else name
        trs.append(
            f'<tr><td class="chow-org-name" data-label="Organization">{name_cell}</td>'
            f'<td class="num" data-label="Facilities">{cnt}</td></tr>'
        )

    org_count = len(top)
    summary = _state_ownership_summary_label(st, state_name, variant="top_orgs", count=org_count)
    from ownership.state_owner_index import state_index_canonical_path

    index_href = html.escape(state_index_canonical_path(st))
    index_link = (
        f'<p class="chow-state-actions">'
        f'<a href="{index_href}" class="chow-state-all-link">{label} nursing home ownership search</a>'
        f"</p>"
    )
    return (
        f'<details class="pbj-details pbj-page-bottom-details pbj-details-top-owners">'
        f'<summary><span class="pbj-details-icon" aria-hidden="true">▼</span> '
        f'<span class="chow-state-summary-text">{summary}</span></summary>'
        f'<div class="pbj-details-content chow-state-block">'
        f'<p class="chow-state-lead chow-state-lead--compact">Most facilities linked in CMS owner data ({label}).</p>'
        f'<div class="chow-table-scroll chow-table-scroll--touch chow-state-owners-scroll">'
        f'<table class="chow-table chow-state-owners-table chow-table--compact-sm">'
        f"<thead><tr><th>Organization</th><th class=\"num\">Facilities</th></tr></thead>"
        f"<tbody>{''.join(trs)}</tbody></table></div>"
        f"{index_link}</div></details>"
    )


def render_state_chow_block(state_code: str, state_name: str = "") -> str:
    """Collapsible recent CHOW transactions on state pages (CT + ownership preview states)."""
    st = str(state_code or "").strip().upper()[:2]
    if not ownership_beta_enabled_for_state(st):
        return ""
    cnt = chow_count_for_state(state_code)
    if cnt <= 0:
        return ""
    label = html.escape(state_name or st)
    stats = chow_state_stats(st)
    events = int(stats.get("events") or cnt)
    u_ccn = int(stats.get("unique_facilities") or 0)
    chow_initial = 10
    chow_page_size = 10

    date_rng = chow_index_date_range_label()
    date_bit = (
        f' · {html.escape(date_rng)}'
        if date_rng
        else ""
    )
    lead = (
        f'<p class="chow-state-lead chow-state-lead--compact">{events:,} ownership changes '
        f'at {u_ccn:,} {label} facilities{date_bit}.</p>'
    )

    table_html = _render_state_chow_recent_table(
        st,
        initial_visible=chow_initial,
        page_size=chow_page_size,
    )
    summary_label = _state_ownership_summary_label(st, state_name, variant="recent", count=events)

    return (
        f'<details class="pbj-details pbj-page-bottom-details pbj-details-ownership-chow">'
        f'<summary><span class="pbj-details-icon" aria-hidden="true">▼</span> '
        f'<span class="chow-state-summary-text">{summary_label}</span></summary>'
        f'<div class="pbj-details-content chow-state-block">'
        f"{lead}"
        f"{table_html}"
        f"</div></details>"
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
        f"<strong>Ownership changes:</strong> {cnt:,} reported CMS CHOW events for {label}."
        "</p>"
    )


def _party_stake_sort_value(party: dict[str, Any]) -> float:
    """Highest reported ownership % for sort order (control roles without % sort last)."""
    best = -1.0
    for raw in party.get("pcts") or []:
        s = str(raw or "").strip().replace("%", "").replace(",", "")
        if not s or s in ("—", "-", "N/A", "n/a"):
            continue
        try:
            v = float(s)
            if v > best:
                best = v
        except ValueError:
            continue
    return best


def _party_pct_display_short(party: dict[str, Any]) -> str:
    for raw in party.get("pcts") or []:
        lbl = _ownership_pct_own_label(raw)
        if lbl:
            return lbl.replace(" own", "").strip()
    for raw in party.get("pcts") or []:
        s = str(raw or "").strip()
        if s and s.lower() not in ("nan", "none", "—", "-"):
            return s if "%" in s else f"{s}%"
    return "—"


def _party_type_short(party_type: str) -> str:
    low = str(party_type or "").strip().lower()
    if "individ" in low:
        return "Individ."
    if "org" in low:
        return "Org."
    t = str(party_type or "").strip()
    return t[:10] if t else "—"


def _party_since_display(party: dict[str, Any]) -> str:
    dates = (party.get("association_dates") or [])[:1]
    since_raw = format_chow_date(dates[0]) if dates else ""
    return since_raw if since_raw else "—"


def sort_parties_by_stake(parties: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        parties,
        key=lambda p: (
            -_party_stake_sort_value(p),
            str(p.get("name") or "").upper(),
        ),
    )


def render_provider_owners_subtitle_control(
    parties: list[dict[str, Any]],
    *,
    ccn: str = "",
) -> tuple[str, str]:
    """Compact [Owners] subtitle button + modal (returned separately to avoid duplicate DOM)."""
    ranked = sort_parties_by_stake([p for p in parties if p.get("name")])
    if not ranked:
        return "", ""
    uid = re.sub(r"[^a-zA-Z0-9_-]", "", str(ccn or "fac"))[:12] or "fac"
    modal_id = f"pbjProviderOwnersModal-{uid}"
    btn_id = f"pbjProviderOwnersBtn-{uid}"
    rows: list[str] = []
    for p in ranked[:30]:
        raw_name = str(p.get("name") or "—")
        name = html.escape(format_org_display(raw_name) if raw_name != "—" else "—")
        pct = html.escape(_party_pct_display_short(p))
        typ = html.escape(_party_type_short(str(p.get("party_type") or "")))
        since = html.escape(_party_since_display(p))
        url = str(p.get("profile_url") or "").strip()
        if url and p.get("is_owner_control_pac"):
            name_cell = f'<a href="{html.escape(url)}">{name}</a>'
        else:
            name_cell = name
        rows.append(
            f"<tr>"
            f'<td class="pbj-provider-owners-modal-name">{name_cell}</td>'
            f'<td class="pbj-provider-owners-modal-pct">{pct}</td>'
            f'<td class="pbj-provider-owners-modal-type">{typ}</td>'
            f'<td class="pbj-provider-owners-modal-since">{since}</td>'
            f"</tr>"
        )
    extra = ""
    if len(ranked) > 30:
        extra = (
            f'<p class="pbj-provider-owners-more">Showing 30 of {len(ranked)} parties. '
            f"See Ownership below for the full table.</p>"
        )
    list_html = (
        '<div class="pbj-provider-owners-modal-scroll">'
        '<table class="pbj-provider-owners-modal-table">'
        "<thead><tr>"
        "<th>Name</th><th>Stake</th><th>Type</th><th>Since</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
        + extra
    )
    btn_html = (
        f' &bull; <button type="button" class="pbj-provider-owners-btn" id="{btn_id}" '
        f'aria-haspopup="dialog" aria-controls="{modal_id}" aria-expanded="false">Owners</button>'
    )
    modal_html = (
        f'<div class="pbj-casemix-modal pbj-provider-owners-modal" id="{modal_id}" aria-hidden="true">'
        f'<div class="pbj-casemix-modal-card pbj-provider-owners-modal-card" role="dialog" '
        f'aria-modal="true" aria-labelledby="{modal_id}Title">'
        f'<button type="button" class="pbj-casemix-modal-close pbj-provider-owners-close" '
        f'data-pbj-owners-close="{modal_id}" aria-label="Close">&times;</button>'
        f'<h3 id="{modal_id}Title">Reported owners</h3>'
        f'<p class="pbj-provider-owners-lead">Roles and ownership stakes from CMS owner data '
        f"for this facility&rsquo;s enrollment.</p>"
        f"{list_html}"
        f"</div></div>"
        f"<script>(function(){{"
        f'var b=document.getElementById("{btn_id}");var m=document.getElementById("{modal_id}");'
        f"if(!b||!m)return;"
        f'function openM(){{m.setAttribute("aria-hidden","false");b.setAttribute("aria-expanded","true");}}'
        f'function closeM(){{m.setAttribute("aria-hidden","true");b.setAttribute("aria-expanded","false");}}'
        f'b.addEventListener("click",function(e){{e.preventDefault();openM();}});'
        f'm.querySelectorAll("[data-pbj-owners-close]").forEach(function(x){{'
        f'x.addEventListener("click",closeM);}});'
        f'm.addEventListener("click",function(e){{if(e.target===m)closeM();}});'
        f'document.addEventListener("keydown",function(e){{'
        f'if(e.key==="Escape"&&m.getAttribute("aria-hidden")==="false")closeM();}});'
        f"}})();</script>"
    )
    return btn_html, modal_html


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
        role_cell = _party_role_and_ownership_cell(p)
        dates = (p.get("association_dates") or [])[:1]
        since_raw = format_chow_date(dates[0]) if dates else ""
        since = html.escape(since_raw) if since_raw else "—"
        owner_url = p.get("profile_url") or ""
        name_cell = (
            f'<a href="{html.escape(owner_url)}">{pname}</a>'
            if owner_url and p.get("is_owner_control_pac")
            else pname
        )
        meta_sep = '<span class="chow-party-meta-sep" aria-hidden="true"> · </span>'
        meta_bits: list[str] = []
        if ptype and ptype != "—":
            meta_bits.append(ptype)
        if role_cell and role_cell != "—":
            meta_bits.append(role_cell)
        if since != "—":
            meta_bits.append(f"Since {since}")
        meta_html = (
            f'<span class="chow-party-meta-line">{meta_sep.join(meta_bits)}</span>'
            if meta_bits
            else '<span class="chow-party-meta-line">—</span>'
        )
        trs.append(
            f'<tr class="chow-provider-owner-row">'
            f'<td class="chow-org-name" data-label="Name">{name_cell}</td>'
            f'<td class="chow-party-meta" data-label="">{meta_html}</td>'
            f'<td class="chow-party-col-desktop" data-label="Type">{ptype}</td>'
            f'<td class="chow-party-col-desktop" data-label="Role">{role_cell}</td>'
            f'<td class="chow-party-col-desktop" data-label="Since">{since}</td>'
            f"</tr>"
        )
    extra = ""
    if len(parties) > preview:
        extra = (
            f'<p class="pbj-meta-line" style="margin:0.5rem 0 0;">'
            f"Showing {preview} of {len(parties)} parties.</p>"
        )
    return (
        f"{extra}"
        '<div class="chow-table-scroll chow-table-scroll--touch chow-provider-owners-scroll">'
        '<table class="chow-table chow-provider-owners-table chow-table--cards-sm">'
        "<thead><tr>"
        "<th>Name</th><th class=\"chow-party-col-desktop\">Type</th>"
        "<th class=\"chow-party-col-desktop\">Role</th>"
        "<th class=\"chow-party-col-desktop\">Since</th>"
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
    from ownership.chow_display import render_provider_chow_cards

    table = render_provider_chow_cards(
        rows[:40],
        org_link_fn=_org_link_from_chow_record,
        max_rows=40,
    )
    more = ""
    if n > 40:
        more = (
            f'<p class="pbj-meta-line chow-tx-more">Showing 40 of {n:,} records.</p>'
        )
    return (
        '<div class="provider-chow-block">'
        f'<button type="button" class="chow-btn chow-btn-chow chow-btn-chow-toggle" '
        f'id="{btn_id}" aria-controls="{panel_id}" aria-expanded="false">'
        f"View Facility Ownership Changes</button>"
        f'<div id="{panel_id}" class="provider-chow-panel" hidden>'
        f"{table}{more}</div></div>"
        + CHOW_TABLE_INIT_SCRIPT
    )


def render_provider_ownership_chow_block(
    ccn: str,
    *,
    provider_info_row: dict[str, Any] | None = None,
    state_code: str = "",
    cms: dict[str, Any] | None = None,
) -> str:
    """CMS all-owners + CHOW footer for provider pages (collapsed by default)."""
    from ownership.owner_profile import lookup_cms_ownership_for_provider

    pi = provider_info_row or {}
    ccn_norm = str(ccn or "").strip().zfill(6)[-6:]
    prov_state = str(
        state_code
        or pi.get("state")
        or pi.get("STATE")
        or pi.get("Provider State")
        or ""
    ).strip().upper()[:2]
    if not prov_state and ccn_norm:
        prov_state = (_ccn_to_state_from_search_index().get(ccn_norm) or "").strip().upper()[:2]
    if not ownership_beta_enabled_for_state(prov_state):
        return ""

    ownership_type = str(
        pi.get("ownership_type") or pi.get("Ownership_Type") or ""
    ).strip()
    chow_flag = str(
        pi.get("provider_changed_ownership_in_last_12_months")
        or pi.get("Provider Changed Ownership in Last 12 Months")
        or ""
    ).strip().upper()
    chow_all = chow_records_for_ccn(ccn_norm, limit=0) if ccn_norm else []
    if cms is None:
        cms = lookup_cms_ownership_for_provider(pi, ccn=ccn_norm)

    if not ownership_type and chow_flag != "Y" and not chow_all and not cms:
        return ""

    lines: list[str] = []
    intro = _provider_ownership_intro_html(ownership_type, cms)
    if intro:
        lines.append(intro)
    lines.append(_provider_ownership_about_html())
    if chow_flag == "Y":
        lines.append(
            '<p class="pbj-ownership-flag">Ownership change reported in last 12 months (CMS Provider Info).</p>'
        )
    if cms:
        lines.append(_render_control_parties_table(cms.get("control_parties") or []))
    chow_html = _render_provider_chow_block(ccn_norm) if chow_all else ""

    open_attr = ""
    if cms and (cms.get("control_parties") or ownership_type):
        open_attr = " open"
    return (
        f'<details class="pbj-details pbj-details-ownership pbj-page-bottom-details"{open_attr}>'
        '<summary><span class="pbj-details-icon" aria-hidden="true">▼</span> '
        "Ownership</summary>"
        '<div class="pbj-details-content pbj-ownership-chow-content">'
        + "".join(lines)
        + chow_html
        + "</div>"
        + "</details>"
    )


def render_entity_ownership_tools_block() -> str:
    return ""
