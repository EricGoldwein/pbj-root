"""HTML rendering for /owners/<pac> — portfolio-first CMS owner profiles."""
from __future__ import annotations

# Allow `python ownership/owner_profile_html.py` from repo root (package imports).
if __name__ == "__main__" and not __package__:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import html
import json
from typing import Any

import re

from ownership.beta_gate import profile_has_public_state
from ownership.owner_fec_section import render_owner_fec_contributions_section
from utils.seo_utils import owner_page_seo_from_profile
from ownership.display_format import (
    cms_rating_stars_html,
    cms_ratings_compact_html,
    cms_ratings_stack_html,
    format_cms_star_rating,
    format_org_display,
    format_role_text,
)

PREVIEW_CONTROL_PARTIES = 25
PREVIEW_FACILITIES = 50
FACILITIES_FILTER_MIN = 12
FACILITIES_MOBILE_PREVIEW = 20
FACILITIES_MOBILE_FILTER_MIN = 8

_FLAG_EXPLAINERS: dict[str, tuple[str, str]] = {
    "sff": (
        "Special Focus Facility (SFF)",
        "Nursing homes with a history of serious quality problems. CMS assigns enhanced "
        "oversight until the facility graduates or is terminated from the program.",
    ),
    "sffc": (
        "SFF Candidate",
        "Facilities CMS is monitoring for potential SFF designation based on sustained "
        "poor survey and quality trends.",
    ),
    "abuse": (
        "Abuse",
        "Flagged for abuse on CMS.",
    ),
    "star_overall": (
        "1-Star Overall",
        "CMS overall star rating is 1 (lowest tier).",
    ),
    "star_staff": (
        "1-Star Staffing",
        "CMS staffing star rating is 1 (lowest tier).",
    ),
}

_DBA_ABBR_TITLE = (
    "Doing Business As (DBA) — the name the facility uses publicly; "
    "CMS may list a different legal business name."
)


def _fmt_rating(val: Any) -> str:
    return format_cms_star_rating(val)


def _fmt_date_mmddyyyy(val: Any) -> str:
    s = str(val or "").strip()
    if not s or s.lower() in ("nan", "none", "—", "-"):
        return "—"
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(2)}-{m.group(3)}-{m.group(1)}"
    return s


def _fmt_date_mdyy(val: Any) -> str:
    """Compact CMS dates for tables, e.g. 4/1/88."""
    s = str(val or "").strip()
    if not s or s.lower() in ("nan", "none", "—", "-"):
        return "—"
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{mo}/{d}/{y % 100}"
    return s


_MONTH_ABBR = (
    "Jan.",
    "Feb.",
    "Mar.",
    "Apr.",
    "May",
    "Jun.",
    "Jul.",
    "Aug.",
    "Sep.",
    "Oct.",
    "Nov.",
    "Dec.",
)


def _parse_ymd(val: Any) -> tuple[int, int, int] | None:
    s = str(val or "").strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if mo < 1 or mo > 12:
        return None
    return y, mo, d


def _fmt_since_long(val: Any) -> str:
    """e.g. Since Feb. 2020"""
    parts = _parse_ymd(val)
    if not parts:
        return ""
    y, mo, _d = parts
    return f"Since {_MONTH_ABBR[mo - 1]} {y}"


def _fmt_since_short(val: Any) -> str:
    """e.g. Since 2/20 (month/year for narrow columns)"""
    parts = _parse_ymd(val)
    if not parts:
        return ""
    y, mo, _d = parts
    return f"Since {mo}/{y % 100:02d}"


def _role_since_html(val: Any) -> str:
    long_txt = _fmt_since_long(val)
    if not long_txt:
        return ""
    short_txt = _fmt_since_short(val) or long_txt
    return (
        f'<span class="owner-role-since" aria-hidden="false">'
        f'<span class="owner-role-since-long">{html.escape(long_txt)}</span>'
        f'<span class="owner-role-since-short">{html.escape(short_txt)}</span>'
        "</span>"
    )


def _sort_attr(val: Any) -> str:
    return html.escape(str(val or "").strip().lower())


def _fmt_census(val: Any) -> str:
    if val is None:
        return "—"
    try:
        f = float(str(val).strip().replace(",", ""))
    except ValueError:
        return "—"
    if f != f:
        return "—"
    return f"{int(round(f)):,}"


def _fmt_hprd(val: Any) -> str:
    if val is None:
        return "—"
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "—", "-"):
        return "—"
    try:
        f = float(s.replace(",", ""))
    except ValueError:
        return "—"
    if f != f:
        return "—"
    return f"{f:.2f}"


def _owner_table_dual(*, desktop_html: str, mobile_html: str) -> str:
    mobile_block = mobile_html or ""
    return (
        f'<div class="owner-table-only-desktop">{desktop_html}</div>'
        f'<div class="owner-table-only-mobile">{mobile_block}</div>'
    )


def _owner_mobile_card_list(items: list[str], list_class: str = "") -> str:
    if not items:
        return ""
    extra = f" {list_class}" if list_class else ""
    return f'<ul class="owner-mobile-card-list{extra}" role="list">{"".join(items)}</ul>'


def _format_party_type(ptype: str) -> str:
    low = str(ptype or "").strip().lower()
    if low.startswith("org"):
        return "Organization"
    if low.startswith("ind"):
        return "Individual"
    if not low or low == "—":
        return "—"
    return format_org_display(str(ptype))


def _dedupe_chow_transactions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for rec in rows:
        key = (
            str(rec.get("effective_date") or "").strip(),
            str(rec.get("ccn") or "").strip().zfill(6)[-6:],
            str(rec.get("buyer_org_name") or "").strip(),
            str(rec.get("seller_org_name") or "").strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out


def _control_party_mobile_card(p: dict[str, Any]) -> str:
    owner_pac = html.escape(p.get("owner_associate_id") or "—")
    raw_name = p.get("name") or "—"
    pname = html.escape(format_org_display(str(raw_name)) if raw_name != "—" else "—")
    ptype = html.escape(_format_party_type(p.get("party_type") or ""))
    roles = "; ".join(
        html.escape(format_role_text(r)) for r in (p.get("roles") or [])[:2]
    )
    pcts = ", ".join(html.escape(x) for x in (p.get("pcts") or [])[:3] if x)
    profile_url = p.get("profile_url") or ""
    if profile_url and p.get("is_owner_control_pac"):
        name_html = f'<a class="owner-m-card__title" href="{html.escape(profile_url)}">{pname}</a>'
        pac_inner = f'<a href="{html.escape(profile_url)}">{owner_pac}</a>'
    else:
        name_html = f'<span class="owner-m-card__title">{pname}</span>'
        pac_inner = owner_pac
    pac_html = f'<span class="owner-m-card__meta">PAC {pac_inner}</span>'
    aside_bits = [f'<span class="owner-m-card__pill">{ptype}</span>']
    if pcts:
        pct_label = pcts if str(pcts).strip().lower().startswith("own") else f"Own. {pcts}"
        aside_bits.append(
            f'<span class="owner-m-card__metric">{html.escape(pct_label)}</span>'
        )
    if roles:
        aside_bits.append(f'<span class="owner-m-card__muted">{roles}</span>')
    return (
        '<li class="owner-m-card owner-m-card--party">'
        '<div class="owner-m-card__main">'
        f"{name_html}{pac_html}"
        "</div>"
        '<div class="owner-m-card__aside">'
        + "".join(aside_bits)
        + "</div></li>"
    )


def _facility_location_short(f: dict[str, Any]) -> str:
    """Compact place label for table/mobile (e.g. Bronx, NY)."""
    county = str(f.get("county") or "").strip()
    st = str(f.get("state") or "").strip().upper()[:2]
    co = county
    if co.lower().endswith(" county"):
        co = co[: -len(" county")].strip()
    if co and len(st) == 2:
        return f"{co}, {st}"
    if len(st) == 2:
        return st
    return co or "—"


def _facility_location_tooltip(f: dict[str, Any]) -> str:
    """Full location line for hover (city, county, state when known)."""
    city = str(f.get("city") or "").strip()
    county = str(f.get("county") or "").strip()
    st = str(f.get("state") or "").strip().upper()[:2]
    parts: list[str] = []
    if city:
        parts.append(city)
    if county:
        parts.append(county if "county" in county.lower() else f"{county} County")
    if len(st) == 2:
        parts.append(st)
    return ", ".join(parts)


def _facility_location_cell(f: dict[str, Any]) -> tuple[str, str]:
    label = _facility_location_short(f)
    tip = _facility_location_tooltip(f)
    esc = html.escape(label)
    if tip and tip != label:
        return (
            f'<span class="owner-facility-location" title="{html.escape(tip, quote=True)}">{esc}</span>',
            _sort_attr(f"{f.get('county') or ''} {f.get('state') or ''}"),
        )
    return f'<span class="owner-facility-location">{esc}</span>', _sort_attr(label)


def _facility_location_residents_line(f: dict[str, Any], *, verified: bool) -> str:
    """Mobile / narrow: census under facility name when present."""
    census = _fmt_census(f.get("census") if verified else None)
    if not census or census == "—":
        return ""
    return (
        f'<div class="owner-facility-meta-line">{html.escape(census)} residents</div>'
    )


def _facility_mobile_meta_line(f: dict[str, Any]) -> str:
    """Legacy hook — location line is rendered via _facility_location_residents_line."""
    return ""


def _format_own_pct_label(value: str) -> str:
    """Prefix numeric CMS ownership stake with Own. for scanability."""
    s = str(value or "").strip()
    if not s or s == "—":
        return s
    low = s.lower()
    if low.startswith("own"):
        return s
    if "%" in s or any(ch.isdigit() for ch in s):
        return f"Own. {s}"
    return s


def _facility_mobile_own_chip(f: dict[str, Any]) -> str:
    """Inline ownership % for compact mobile cards (tap for CMS role when available)."""
    role_raw = str(f.get("role") or "")
    role_text = format_role_text(role_raw) if role_raw else ""
    adate = _fmt_date_mdyy(f.get("association_date"))
    pct_raw = str(f.get("pct") or "").strip()
    pct = ""
    if pct_raw and pct_raw.lower() not in ("nan", "none", "—", "-", ""):
        pct = pct_raw if "%" in pct_raw else f"{pct_raw}%"
    pct_label = _format_own_pct_label(pct) if pct else _pct_fallback_label(role_raw) or ""
    pct_display = html.escape(pct_label)
    if not pct_display:
        return ""
    label = pct_display
    if role_text or (adate and adate != "—"):
        modal_title = html.escape(pct or "Ownership", quote=True)
        return (
            f'<button type="button" class="owner-m-card-chip owner-m-card-chip--own owner-role-pct-btn" '
            f'data-owner-info data-info-format="ownership" '
            f'data-info-title="{modal_title}" '
            f'data-role-text="{html.escape(role_text, quote=True)}" '
            f'data-role-since="{html.escape(adate if adate != "—" else "", quote=True)}" '
            f'aria-label="Ownership {label} (tap for role)">{label}</button>'
        )
    return f'<span class="owner-m-card-chip owner-m-card-chip--own">{label}</span>'


def _facility_mobile_primary_block(f: dict[str, Any]) -> str:
    """Title + optional legal subline (no location line — folded into stats)."""
    legal_raw = format_org_display(str(f.get("facility_name") or "—"))
    provider_raw = format_org_display(str(f.get("provider_name") or "").strip())
    ccn = str(f.get("ccn") or "").strip().zfill(6)[-6:]
    method = str(f.get("ccn_match_method") or "")
    legal_esc = html.escape(legal_raw)
    provider_esc = html.escape(provider_raw) if provider_raw else ""
    same = bool(provider_esc) and provider_esc.upper() == legal_esc.upper()
    href = (
        f"/provider/{html.escape(ccn)}"
        if ccn.isdigit() and method in ("legal_exact", "name_exact", "fuzzy")
        else ""
    )
    link_label = provider_esc or legal_esc
    place = _facility_location_short(f)
    display_label = link_label
    if place and place != "—" and link_label and f"({place})" not in link_label:
        display_label = f"{link_label} ({html.escape(place)})"
    loc_tip = _facility_location_tooltip(f)
    title_bits = []
    if href and display_label:
        title_bits.append(f"View staffing data for {display_label}")
    if loc_tip:
        title_bits.append(loc_tip)
    title_attr = (
        f' title="{html.escape(" — ".join(title_bits), quote=True)}"'
        if title_bits
        else ""
    )
    if href:
        primary_html = (
            f'<a href="{href}" class="owner-m-card__title"{title_attr}>{display_label}</a>'
        )
    else:
        primary_html = f'<span class="owner-m-card__title">{display_label}</span>'
    sub_html = ""
    if provider_esc and not same:
        sub_html = f'<span class="owner-m-card__sub">{legal_esc}</span>'
    return primary_html + sub_html


def _facility_mobile_stats_line(f: dict[str, Any], *, verified: bool) -> str:
    """Single scannable metrics line: Own. 50% · 81 res · 3.16 HPRD · Ovr 4★ · Stf 1★."""
    bits: list[str] = []
    own = _facility_mobile_own_chip(f)
    if own:
        bits.append(own)
    census = _fmt_census(f.get("census") if verified else None)
    if census and census != "—":
        bits.append(f'<span class="owner-m-card-chip">{html.escape(census)} res</span>')
    hprd = _fmt_hprd(f.get("hprd") if verified else None)
    if hprd and hprd != "—":
        bits.append(f'<span class="owner-m-card-chip">{html.escape(hprd)} HPRD</span>')
    ratings = cms_ratings_compact_html(
        f.get("overall_rating"),
        f.get("staffing_rating"),
        verified=verified,
    )
    if ratings:
        bits.append(ratings)
    if not bits:
        return ""
    return '<div class="owner-m-card__stats">' + '<span class="owner-m-card__sep" aria-hidden="true"> · </span>'.join(bits) + "</div>"


def _facility_mobile_flags_inline(f: dict[str, Any], *, verified: bool) -> str:
    flags = _facility_flags_cell(f, verified=verified, skip_star_flags=True)
    if not flags:
        return ""
    return f'<div class="owner-m-card__flags-inline">{flags}</div>'


def _facility_mobile_card(f: dict[str, Any]) -> str:
    method = str(f.get("ccn_match_method") or "")
    verified = method == "legal_exact"
    title_block = _facility_mobile_primary_block(f)
    stats = _facility_mobile_stats_line(f, verified=verified)
    flags = _facility_mobile_flags_inline(f, verified=verified)
    metrics = ""
    if stats or flags:
        sep = '<span class="owner-m-card__sep" aria-hidden="true"> · </span>' if stats and flags else ""
        metrics = '<div class="owner-m-card__metrics">' + (stats or "") + sep + (flags or "") + "</div>"
    search = " ".join(
        [
            str(f.get("facility_name") or ""),
            str(f.get("provider_name") or ""),
            str(f.get("state") or ""),
            str(f.get("county") or ""),
            str(f.get("role") or ""),
        ]
    ).lower()
    return (
        f'<li class="owner-m-card owner-m-card--facility owner-m-card--facility-compact" '
        f'data-search="{html.escape(search)}">'
        f'<div class="owner-m-card__body">{title_block}{metrics}</div></li>'
    )


def _enrollment_facility_mobile_card(f: dict[str, Any]) -> str:
    names_html, _ = _facility_names_cell(f)
    names_html = names_html.replace('class="owner-facility-names"', 'class="owner-m-card__names"', 1)
    enr = html.escape(f.get("enrollment_id") or "—")
    place = html.escape(_facility_location_short(f))
    city = html.escape(str(f.get("city") or "").strip() or "—")
    loc_bits = [b for b in (place, city) if b and b != "—"]
    loc = " · ".join(loc_bits) if loc_bits else "—"
    meta = f'<span class="owner-m-card__meta">Enrollment {enr} · {loc}</span>'
    return (
        '<li class="owner-m-card owner-m-card--facility">'
        '<div class="owner-m-card__main">'
        f"{names_html}{meta}"
        "</div></li>"
    )


def _ownership_timeline_item_html(rec: dict[str, Any]) -> str:
    from ownership.chow_lookup import format_chow_date

    eff = html.escape(format_chow_date(str(rec.get("effective_date") or "")) or "—")
    ccn = str(rec.get("ccn") or "").strip().zfill(6)[-6:]
    fac_raw = format_org_display(
        str(rec.get("facility_display_name") or rec.get("buyer_dba_name") or "—")
    )
    fac_esc = html.escape(fac_raw)
    if ccn.isdigit():
        fac_html = (
            f'<a class="owner-timeline-facility" href="/provider/{html.escape(ccn)}">{fac_esc}</a>'
        )
    else:
        fac_html = f'<span class="owner-timeline-facility">{fac_esc}</span>'
    seller = html.escape(format_org_display(str(rec.get("seller_org_name") or "—")))
    buyer = html.escape(format_org_display(str(rec.get("buyer_org_name") or "—")))
    side = _chow_transaction_side_label(str(rec.get("chow_role") or ""))
    parties = f'<span class="owner-timeline-seller">{seller}</span> \u2192 <span class="owner-timeline-buyer">{buyer}</span>'
    side_html = (
        f'<span class="owner-timeline-side">{html.escape(side)}</span>'
        if side
        else ""
    )
    return (
        f'<li class="owner-timeline-item">'
        f'<div class="owner-timeline-date">{eff}</div>'
        f'<div class="owner-timeline-body">'
        f'<div class="owner-timeline-facility-row">{fac_html}{side_html}</div>'
        f'<div class="owner-timeline-parties">{parties}</div>'
        "</div></li>"
    )


def _ownership_tx_mobile_card(rec: dict[str, Any]) -> str:
    return _ownership_timeline_item_html(rec)


def _associate_mobile_card(r: dict[str, Any], *, n_facilities: int) -> str:
    name = format_org_display(str(r.get("name") or "—"))
    url = str(r.get("profile_url") or "").strip()
    if url:
        name_html = (
            f'<a class="owner-m-card__title" href="{html.escape(url)}">{html.escape(name)}</a>'
        )
    else:
        name_html = f'<span class="owner-m-card__title">{html.escape(name)}</span>'
    shared = html.escape(_associate_shared_facilities_cell(r, n_facilities=n_facilities))
    link_type = html.escape(_associate_source_label(r) or "—")
    meta = f'<span class="owner-m-card__meta">{shared} shared · {link_type}</span>'
    return (
        '<li class="owner-m-card owner-m-card--associate">'
        f"{name_html}{meta}"
        "</li>"
    )


def render_owner_profile_body(profile: dict[str, Any]) -> tuple[str, str, str, str]:
    """Return (body_html, page_title, meta_desc, canonical_path_suffix)."""
    kind = profile.get("profile_kind") or "owner_control"
    name = html.escape(format_org_display(profile.get("display_name") or "Organization"))
    pac = html.escape(profile.get("associate_id") or "")
    owner_type = html.escape(profile.get("owner_type") or "")
    states = profile.get("states") or []
    facilities = profile.get("facilities") or []
    en_raw = str(profile.get("enrollment_pac_label") or "Enrollment PAC")
    ow_raw = str(profile.get("owner_pac_label") or "Owner PAC")
    en_label = html.escape(en_raw)
    ow_label = html.escape(ow_raw)
    page_title, meta_desc, owner_intro_html = owner_page_seo_from_profile(profile)
    states_meta = _states_meta_html(profile)
    states_modal = _states_breakdown_modal_html(profile)

    is_chow_only = bool(profile.get("is_chow_only"))

    kind_banner = _kind_banner(kind, is_chow_only)
    preview_banner = _internal_preview_banner_html(profile)
    portfolio_html = _portfolio_snapshot_html(profile)
    owners_primary_html = _owners_primary_section_html(profile, kind, ow_label)
    facilities_html = _facilities_sections_html(
        profile, kind, facilities, ow_label, skip_control_parties=bool(owners_primary_html)
    )
    associates_html = _related_associates_html(profile)
    owner_section_html = _owner_dual_section_html(profile, kind)

    header_html = _owner_profile_header_html(
        profile,
        name=name,
        owner_type=owner_type,
        states_meta=states_meta,
        kind=kind,
        pac=pac,
        en_label=en_raw,
        ow_label=ow_raw,
    )
    body = f"""
      <div class="owner-profile-root">
      {header_html}
      {owner_intro_html}
      {states_modal}
      {_owner_info_modal_html()}
      {kind_banner}
      {preview_banner}
      {portfolio_html}
      {owners_primary_html}
      {facilities_html}
      {associates_html}
      {owner_section_html}
      {render_owner_fec_contributions_section(profile)}
      </div>
    """
    return body, page_title, meta_desc, f"/owners/{pac}"


def _states_meta_html(profile: dict[str, Any]) -> str:
    ps = profile.get("portfolio_summary") or {}
    n_states = int(ps.get("n_states") or 0)
    states = list(profile.get("states") or [])
    if not n_states:
        n_states = len(states)
    if not n_states:
        return ""
    if n_states == 1:
        st = (states[0] if states else "").strip().upper()[:2]
        if not st:
            by_state = ps.get("by_state") or []
            if by_state:
                st = str(by_state[0][0] or "").strip().upper()[:2]
        if st:
            try:
                from app import STATE_CODE_TO_NAME, get_canonical_slug

                label = STATE_CODE_TO_NAME.get(st, st)
                slug = get_canonical_slug(st)
            except Exception:
                label, slug = st, st.lower()
            return (
                f'<a class="owner-state-link" href="/state/{html.escape(slug)}">'
                f"{html.escape(label)}</a>"
            )
    label = "state" if n_states == 1 else "states"
    return (
        f'<button type="button" class="owner-states-trigger" data-owner-states-open '
        f'aria-haspopup="dialog">{n_states} {label}</button>'
    )


def _states_breakdown_modal_html(profile: dict[str, Any]) -> str:
    ps = profile.get("portfolio_summary") or {}
    by_state: list[tuple[str, int]] = list(ps.get("by_state") or [])
    if not by_state:
        states = profile.get("states") or []
        if not states:
            return ""
        by_state = [(st, 0) for st in states]
    rows = []
    total = 0
    for st, cnt in by_state:
        total += cnt
        rows.append(
            f"<tr><td>{html.escape(st)}</td><td class=\"num\">{cnt if cnt else '—'}</td></tr>"
        )
    total_row = (
        f'<tr class="owner-states-total"><td><strong>Total</strong></td>'
        f'<td class="num"><strong>{total or len(by_state)}</strong></td></tr>'
        if total
        else ""
    )
    return f"""
      <dialog class="owner-states-modal" id="ownerStatesModal" aria-labelledby="ownerStatesModalTitle">
        <div class="owner-states-modal-card">
          <header class="owner-states-modal-header">
            <h2 id="ownerStatesModalTitle">By state</h2>
            <button type="button" class="owner-states-modal-close" data-owner-states-close aria-label="Close">×</button>
          </header>
          <div class="chow-table-scroll chow-table-scroll--touch owner-states-modal-body">
            <table class="chow-table owner-states-table">
              <thead><tr><th>State</th><th class="num">#</th></tr></thead>
              <tbody>{"".join(rows)}{total_row}</tbody>
            </table>
          </div>
        </div>
      </dialog>"""


def _pac_meta_html(
    profile: dict[str, Any],
    kind: str,
    pac: str,
    en_label: str,
    ow_label: str,
    *,
    page_help: str = "",
) -> str:
    enrollment_ids = profile.get("enrollment_ids") or []
    rows: list[str] = []
    if kind == "both":
        label = "PAC"
    elif kind == "owner_control":
        label = ow_label
    else:
        label = en_label

    rows.append(
        f'<span class="owner-pac-block owner-meta-item">'
        f'<span class="owner-pac-block__label">{label}</span>'
        f'<span class="owner-pac-block__value-line">'
        f'<span class="owner-pac-block__value">{pac}</span>'
        f"{page_help}"
        "</span></span>"
    )
    if enrollment_ids:
        ids = ", ".join(html.escape(e) for e in enrollment_ids[:4])
        if len(enrollment_ids) > 4:
            ids += f" (+{len(enrollment_ids) - 4})"
        rows.append(
            f'<span class="owner-meta-item owner-meta-row">'
            f'<span class="owner-meta-k">Enrollment ID</span>'
            f'<span class="owner-meta-v">{ids}</span>'
            "</span>"
        )
    return f'<span class="owner-profile-pac-meta">{"".join(rows)}</span>'


def _internal_preview_banner_html(profile: dict[str, Any]) -> str:
    if profile_has_public_state(profile):
        return ""
    states = profile.get("states") or []
    label = ", ".join(html.escape(str(s)) for s in states[:6]) if states else "non-CT"
    extra = f" (+{len(states) - 6} more)" if len(states) > 6 else ""
    return (
        '<div class="owner-scope-note owner-scope-note--preview" role="status">'
        "<strong>Internal preview.</strong> This profile is visible for review only "
        f"({label}{extra}) and is not part of the public CT/NY ownership launch."
        "</div>"
    )


def _kind_banner(kind: str, is_chow_only: bool) -> str:
    if kind == "enrollment":
        text = (
            "<strong>Enrollment entity.</strong> CMS facility enrollment PAC with linked "
            "owners, facilities, and any ownership transactions in CMS data."
        )
    elif kind == "both":
        text = (
            "<strong>Enrollment and owner PAC.</strong> This number appears as both "
            "the facility enrollment and an owner/control party in CMS data."
        )
    elif is_chow_only:
        text = (
            "<strong>Ownership profile.</strong> Listed in CMS ownership-change records; "
            "may not appear in the current CMS owner data enrollment or owner PAC file."
        )
    elif kind == "owner_control":
        return ""
    else:
        return ""
    return f'<div class="owner-scope-note" role="status">{text}</div>'



def _snf_owners_source_line(profile: dict[str, Any]) -> str:
    from ownership.owner_profile import snf_owners_source_citation

    return snf_owners_source_citation()


def _owner_page_help_body(
    profile: dict[str, Any],
    kind: str,
    *,
    en_label: str,
    ow_label: str,
) -> str:
    """Page-level methodology (? help on owner profile header)."""
    n = len(profile.get("facilities") or [])
    snf_src = _snf_owners_source_line(profile)
    kind_line = {
        "owner_control": (
            f"Owner/control party with {n} linked nursing homes in {snf_src}."
        ),
        "enrollment": (
            f"CMS enrollment entity with {n} linked facilities, owners, and control parties "
            f"in {snf_src}."
        ),
        "both": (
            f"Enrollment and owner/control PAC with {n} linked facilities in {snf_src}."
        ),
        "chow_only": (
            f"Party in CMS ownership-change records with {n} linked facility references; "
            "may be absent from the current CMS owner data file."
        ),
    }.get(kind, f"CMS ownership profile with {n} linked records in {snf_src}.")

    pac_line = (
        f"{en_label} — facility enrollment in CMS (typical buyer/seller in ownership changes). "
        f"{ow_label} — reported owner or control party."
    )

    return (
        f"{kind_line}\n\n"
        f"{pac_line}\n\n"
        "State index counts are state-specific; owner profile counts are nationwide unless "
        "otherwise noted.\n\n"
        "Facility table: ownership %, CMS role, PBJ staffing (HPRD), star ratings, and flags "
        "where linked.\n\n"
        "Portfolio summary: PBJ-verified facilities only (enrollment legal name matches "
        "provider-info). Means omit missing HPRD or stars; exclude implausible HPRD "
        "(below 1.5 or above 12) and overall stars outside 1–5. Weighted means use census "
        "when published, else certified beds.\n\n"
        f"Sources: {snf_src}; CMS PBJ; CMS provider data; PBJ320 CHOW index."
    )


def _owner_profile_header_html(
    profile: dict[str, Any],
    *,
    name: str,
    owner_type: str,
    states_meta: str,
    kind: str,
    pac: str,
    en_label: str,
    ow_label: str,
) -> str:
    page_help = _info_button(
        "PBJ320 Ownership",
        _owner_page_help_body(profile, kind, en_label=en_label, ow_label=ow_label),
        label="?",
        cls="owner-info-btn owner-info-btn--section owner-page-help",
    )
    pac_meta = _pac_meta_html(
        profile,
        kind,
        pac,
        html.escape(en_label),
        html.escape(ow_label),
        page_help=page_help,
    )
    meta_parts: list[str] = []
    if owner_type:
        meta_parts.append(f'<span class="owner-profile-type">{owner_type}</span>')
    if states_meta:
        meta_parts.append(states_meta)
    meta_row = (
        f'<div class="owner-profile-meta-row">{"".join(meta_parts)}</div>'
        if meta_parts
        else ""
    )
    header_actions = ""
    if pac_meta:
        header_actions = (
            f'<div class="owner-profile-header-aside">'
            f'<div class="owner-profile-header-actions">{pac_meta}</div>'
            "</div>"
        )
    return f"""
      <header class="owner-profile-header owner-profile-header--branded">
        <div class="owner-profile-header-top">
          <a class="owner-profile-brand" href="/state/connecticut" aria-label="Connecticut PBJ320">
            <img class="owner-profile-brand-icon" src="/pbj_favicon.png" alt="" width="28" height="28" decoding="async">
            <span class="owner-profile-brand-lockup">
              <span class="owner-profile-brand-mark"><span class="owner-profile-brand-pbj">PBJ</span><span class="owner-profile-brand-320">320</span></span>
              <span class="owner-profile-brand-suffix">Ownership</span>
            </span>
          </a>
          <div class="owner-profile-header-identity">
            <h1 class="owner-profile-name">{name}</h1>
            {meta_row}
          </div>
          {header_actions}
        </div>
      </header>"""


def _info_button(title: str, body: str, *, label: str = "?", cls: str = "owner-info-btn") -> str:
    extra = ""
    if "owner-info-btn" not in cls.split():
        extra = " owner-info-btn"
    return (
        f'<button type="button" class="{cls}{extra}" data-owner-info '
        f'data-info-title="{html.escape(title, quote=True)}" '
        f'data-info-body="{html.escape(body, quote=True)}">'
        f"{html.escape(label)}</button>"
    )


def _associate_shared_facilities_cell(r: dict[str, Any], *, n_facilities: int) -> str:
    snf = int(r.get("snf_shared") or 0)
    chow = int(r.get("chow_count") or 0)
    if snf:
        if n_facilities and snf <= n_facilities:
            return f"{snf}/{n_facilities}"
        return str(snf)
    if chow:
        return f"{chow} CHOW"
    return "—"


def _associate_source_label(r: dict[str, Any]) -> str:
    bits: list[str] = []
    if int(r.get("snf_shared") or 0):
        bits.append("Ownership")
    if int(r.get("chow_count") or 0):
        bits.append("CMS ownership change")
    return " · ".join(bits)


def _related_associates_html(profile: dict[str, Any]) -> str:
    """Co-owners and CHOW counterparties — compact list below the facilities portfolio."""
    rows = profile.get("related_associates") or []
    if not rows:
        return ""

    n_facilities = int((profile.get("portfolio_summary") or {}).get("n_facilities") or 0)
    trs: list[str] = []
    mobile_cards: list[str] = []
    for r in rows[:20]:
        name = format_org_display(str(r.get("name") or "—"))
        url = str(r.get("profile_url") or "").strip()
        name_html = (
            f'<a class="owner-associate-name" href="{html.escape(url)}">{html.escape(name)}</a>'
            if url
            else f'<span class="owner-associate-name">{html.escape(name)}</span>'
        )
        shared = html.escape(_associate_shared_facilities_cell(r, n_facilities=n_facilities))
        link_type = html.escape(_associate_source_label(r) or "—")
        trs.append(
            f"<tr><td class=\"owner-associate-col-name\">{name_html}</td>"
            f'<td class="num owner-associate-col-shared">{shared}</td>'
            f'<td class="owner-associate-col-link">{link_type}</td></tr>'
        )
        mobile_cards.append(_associate_mobile_card(r, n_facilities=n_facilities))

    n_show = len(trs)
    associates_help = _info_button(
        "Frequent associates",
        (
            "Parties that appear repeatedly with this owner on CMS records.\n\n"
            "Ownership: co-owners on the same nursing home enrollments in "
            "CMS owner data (shared enrollment PACs).\n\n"
            "Ownership events: buyer or seller counterparties on CMS-reported ownership "
            "change filings involving this party.\n\n"
            "Sources: CMS owner data; CMS ownership-change (CHOW) filings."
        ),
        label="?",
        cls="owner-info-btn owner-info-btn--section owner-associates-info",
    )
    desktop = (
        '<div class="owner-associates-table-wrap">'
        '<table class="owner-associate-table"><thead><tr>'
        '<th class="owner-associate-col-name">Name</th>'
        '<th class="num owner-associate-col-shared" title="Shared nursing homes with this owner">Shared</th>'
        '<th class="owner-associate-col-link">Link</th>'
        "</tr></thead><tbody>"
        + "".join(trs)
        + "</tbody></table></div>"
    )
    dual = _owner_table_dual(
        desktop_html=desktop,
        mobile_html=_owner_mobile_card_list(mobile_cards, "owner-mobile-card-list--associates"),
    )
    return (
        '<div class="owner-associates-block">'
        f'<div class="owner-associates-head">'
        f'<span class="owner-associates-head-label">Frequent associates · {n_show}</span>'
        f"{associates_help}"
        f"</div>"
        '<details class="owner-collapsible owner-associates-collapsible">'
        f'<summary class="owner-associates-summary">'
        f'<span class="owner-associates-summary-label">Show associates</span>'
        f"</summary>"
        f"{dual}"
        "</details>"
        "</div>"
    )


def _chow_transaction_side_label(role_raw: str) -> str:
    """Buyer/seller on CHOW filings; hide meaningless raw codes."""
    r = str(role_raw or "").strip().lower()
    if r == "buyer":
        return "Buyer"
    if r == "seller":
        return "Seller"
    if r in ("party", "1", ""):
        return ""
    if r.isdigit():
        return ""
    return format_org_display(str(role_raw))


def _snapshot_metric_card(
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
    value_attrs = (
        f' title="{value_tip}" aria-label="{value_tip}"' if value_tip else ""
    )
    return (
        f'<div class="owner-snapshot-card{tone_cls}">'
        f'<div class="owner-snapshot-label">{html.escape(label)}</div>'
        f'<div class="owner-snapshot-value-row">'
        f'<div class="owner-snapshot-value"{value_attrs}>{value}</div>'
        f"{_info_button(help_title, help_body)}"
        "</div></div>"
    )


def _portfolio_distribution_list(
    counts: dict[int, int],
    *,
    row_labels: list[str] | None = None,
) -> str:
    """Bar list only (no card wrapper) for 1–5 star buckets."""
    total = sum(int(counts.get(i, 0) or 0) for i in range(1, 6))
    if total < 1:
        return ""
    peak = max(int(counts.get(i, 0) or 0) for i in range(1, 6)) or 1
    rows: list[str] = []
    for star in range(5, 0, -1):
        cnt = int(counts.get(star, 0) or 0)
        pct = int(round(100.0 * cnt / total)) if total else 0
        width = max(4, int(round(100.0 * cnt / peak))) if cnt else 0
        label = (row_labels[star - 1] if row_labels and len(row_labels) >= star else f"{star}\u2605")
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


def _portfolio_distribution_bars(
    counts: dict[int, int],
    *,
    title: str,
    row_labels: list[str] | None = None,
) -> str:
    """Single distribution card (no tabs)."""
    list_html = _portfolio_distribution_list(counts, row_labels=row_labels)
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


def _portfolio_state_distribution(by_state: list[tuple[str, int]], n_total: int) -> str:
    if not by_state or n_total < 1:
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


def _portfolio_distribution_tabs(
    overall_list: str,
    staffing_list: str,
    *,
    overall_title: str,
    staffing_title: str,
) -> str:
    """Overall / staffing in one card; tabs sit in the card header beside the title."""
    o_title = html.escape(overall_title)
    s_title = html.escape(staffing_title)
    return (
        '<section class="owner-dist-card owner-dist-card--tabbed" data-owner-dist-tabs '
        'aria-label="CMS rating distributions">'
        '<div class="owner-dist-card-head">'
        f'<h3 class="owner-dist-title" data-owner-dist-title>{o_title}</h3>'
        '<div class="owner-dist-tablist" role="tablist" aria-label="Rating type">'
        f'<button type="button" class="owner-dist-tab is-active" role="tab" id="ownerDistTabOverall" '
        f'data-dist-title="{o_title}" aria-selected="true" aria-controls="ownerDistPanelOverall" '
        'tabindex="0">Overall</button>'
        f'<button type="button" class="owner-dist-tab" role="tab" id="ownerDistTabStaffing" '
        f'data-dist-title="{s_title}" aria-selected="false" aria-controls="ownerDistPanelStaffing" '
        'tabindex="-1">Staffing</button>'
        "</div></div>"
        f'<div class="owner-dist-tabpanel is-active" role="tabpanel" id="ownerDistPanelOverall" '
        f'aria-labelledby="ownerDistTabOverall">{overall_list}</div>'
        f'<div class="owner-dist-tabpanel" role="tabpanel" id="ownerDistPanelStaffing" '
        f'aria-labelledby="ownerDistTabStaffing" hidden>{staffing_list}</div>'
        "</section>"
    )


def _portfolio_distribution_html(ps: dict[str, Any]) -> str:
    from ownership.owner_portfolio_metrics import PORTFOLIO_STAR_DIST_MIN

    overall_title = "Overall CMS star rating"
    staffing_title = "Staffing CMS star rating"
    overall_list = ""
    staffing_list = ""
    n_ovr = int(ps.get("n_with_overall_for_dist") or 0)
    if n_ovr >= PORTFOLIO_STAR_DIST_MIN:
        overall_list = _portfolio_distribution_list(ps.get("overall_star_counts") or {})
    n_stf = int(ps.get("n_with_staffing_for_dist") or 0)
    if n_stf >= PORTFOLIO_STAR_DIST_MIN:
        staffing_list = _portfolio_distribution_list(ps.get("staffing_star_counts") or {})
    if overall_list and staffing_list:
        return _portfolio_distribution_tabs(
            overall_list,
            staffing_list,
            overall_title=overall_title,
            staffing_title=staffing_title,
        )
    if overall_list:
        return _portfolio_distribution_bars(
            ps.get("overall_star_counts") or {},
            title=overall_title,
        )
    if staffing_list:
        return _portfolio_distribution_bars(
            ps.get("staffing_star_counts") or {},
            title=staffing_title,
        )
    return _portfolio_state_distribution(
        list(ps.get("by_state") or []),
        int(ps.get("n_facilities") or 0),
    )


def _portfolio_facilities_cta_html(profile: dict[str, Any]) -> str:
    return ""


def _owner_info_modal_html() -> str:
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

def _portfolio_snapshot_html(profile: dict[str, Any]) -> str:
    ps = profile.get("portfolio_summary") or {}
    if not ps or not ps.get("n_facilities"):
        return ""

    n = int(ps.get("n_facilities") or 0)
    n_matched = int(ps.get("n_pbj_matched") or 0)
    n_suggested = int(ps.get("n_pbj_suggested") or 0)
    wmean = ps.get("wmean_hprd")
    umean = ps.get("umean_hprd")
    mean_ovr = ps.get("umean_overall_rating")
    if mean_ovr is None:
        mean_ovr = ps.get("mean_overall_rating")
    mean_stf = ps.get("umean_staffing_rating")
    if mean_stf is None:
        mean_stf = ps.get("mean_staffing_rating")

    from ownership.owner_portfolio_metrics import (
        PORTFOLIO_HPRD_MAX,
        PORTFOLIO_HPRD_MIN,
        PORTFOLIO_OVERALL_RATING_MAX,
        PORTFOLIO_OVERALL_RATING_MIN,
    )

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

    cards: list[str] = [
        _snapshot_metric_card(
            "Facilities",
            str(n),
            "Facilities",
            fac_help,
            tone="accent",
            value_title="Distinct CMS-linked facilities nationwide",
        ),
    ]
    if mean_ovr is not None:
        cards.append(
            _snapshot_metric_card(
                "Avg overall rating",
                html.escape(f"{mean_ovr:.1f}"),
                "Avg overall rating",
                ovr_help,
                tone="warn",
            )
        )
    if wmean is not None:
        cards.append(
            _snapshot_metric_card(
                "Weighted total nurse HPRD",
                html.escape(f"{wmean:.2f}"),
                "Weighted total nurse HPRD",
                hprd_help,
            )
        )
    elif umean is not None:
        cards.append(
            _snapshot_metric_card(
                "Avg total nurse HPRD",
                html.escape(f"{umean:.2f}"),
                "Avg total nurse HPRD",
                hprd_help.replace("resident-weighted", "unweighted mean"),
            )
        )
    if mean_stf is not None:
        cards.append(
            _snapshot_metric_card(
                "Avg staffing rating",
                html.escape(f"{mean_stf:.1f}"),
                "Avg staffing rating",
                stf_help,
            )
        )

    grid_cols = "owner-portfolio-grid--4" if len(cards) >= 4 else "owner-portfolio-grid--3"
    if len(cards) == 2:
        grid_cols = "owner-portfolio-grid--2"

    dist_html = _portfolio_distribution_html(ps)
    cta_html = _portfolio_facilities_cta_html(profile)

    return f"""
      <section class="owner-snapshot-section" aria-label="Portfolio metrics">
        <div class="owner-portfolio-grid {grid_cols}" aria-label="Portfolio summary metrics">
          {"".join(cards)}
        </div>
        {dist_html}
        {cta_html}
      </section>"""


def _facilities_match_note(profile: dict[str, Any]) -> str:
    ps = profile.get("portfolio_summary") or {}
    n = ps.get("n_facilities") or 0
    verified = ps.get("n_pbj_matched") or 0
    suggested = ps.get("n_pbj_suggested") or 0
    if not n or (verified >= n and not suggested):
        return ""
    if suggested:
        row_word = "rows" if suggested != 1 else "row"
        return (
            f'<p class="owner-table-note owner-table-note--compact">'
            f"{suggested} {row_word} linked by facility name only; "
            "PBJ staffing and ratings show when the legal-name match is verified.</p>"
        )
    return (
        f'<p class="owner-table-note">{n - verified} of {n} facilities have no verified PBJ link; '
        "CMS ownership rows are still valid.</p>"
    )


def _state_county_cells(f: dict[str, Any]) -> tuple[str, str]:
    st = html.escape(str(f.get("state") or "").strip().upper() or "—")
    co = html.escape(str(f.get("county") or "").strip() or "—")
    return st, co


def _ccn_match_badge(method: str) -> str:
    if method == "name_exact":
        return (
            '<button type="button" class="owner-match-badge owner-match-badge--tip" '
            'title="Matched via facility DBA or search name, not verified legal business name" '
            'aria-label="DBA name match">DBA</button>'
        )
    if method == "fuzzy":
        return (
            '<button type="button" class="owner-match-badge owner-match-badge--warn owner-match-badge--tip" '
            'title="Approximate name match—verify legal name on Care Compare" '
            'aria-label="Approximate name match">~</button>'
        )
    return ""


def _rating_stars_html(val: str) -> str:
    return cms_rating_stars_html(val)


def _cms_stars_cell(f: dict[str, Any], *, verified: bool) -> tuple[str, str]:
    """CMS star ratings (overall, staffing, QM) with icon rows."""
    if not verified:
        return "—", ""
    ovr = _fmt_rating(f.get("overall_rating"))
    staff = _fmt_rating(f.get("staffing_rating"))
    qm = _fmt_rating(f.get("qm_rating"))
    if ovr == "—" and staff == "—" and qm == "—":
        return "—", ""
    sort_key = f"{ovr}.{staff}.{qm}".replace("—", "")
    hi = f.get("health_inspection_rating") or f.get("health_inspection")
    return cms_ratings_stack_html(
        f.get("overall_rating"),
        f.get("staffing_rating"),
        f.get("qm_rating"),
        health_inspection=hi,
    ), sort_key


def _flag_explainer_button(kind: str, label: str, css_class: str) -> str:
    title, body = _FLAG_EXPLAINERS[kind]
    return (
        f'<button type="button" class="owner-flag {css_class}" data-owner-info '
        f'data-info-format="flag" '
        f'data-info-title="{html.escape(title, quote=True)}" '
        f'data-info-body="{html.escape(body, quote=True)}">{html.escape(label)}</button>'
    )


def _facilities_portfolio_title(profile: dict[str, Any]) -> str:
    raw = str(profile.get("display_name") or "").strip()
    name = html.escape(format_org_display(raw) if raw else "Portfolio")
    return f"{name} Portfolio"


def _facility_flags_cell(
    f: dict[str, Any], *, verified: bool, skip_star_flags: bool = False
) -> str:
    """Regulatory screening badges (SFF, abuse icon, etc.)."""
    if not verified:
        return "—"
    badges: list[str] = []
    sff = str(f.get("sff_status") or f.get("sff") or "").strip()
    sff_up = sff.upper()
    if sff_up == "SFF":
        badges.append(_flag_explainer_button("sff", "SFF", "owner-flag--sff"))
    elif "CANDIDATE" in sff_up:
        badges.append(_flag_explainer_button("sffc", "SFF-C", "owner-flag--sffc"))
    if f.get("has_abuse"):
        badges.append(_flag_explainer_button("abuse", "Abuse", "owner-flag--abuse"))
    if not skip_star_flags:
        if format_cms_star_rating(f.get("overall_rating")) == "1":
            badges.append(_flag_explainer_button("star_overall", "1★", "owner-flag--star"))
        if format_cms_star_rating(f.get("staffing_rating")) == "1":
            badges.append(_flag_explainer_button("star_staff", "1★S", "owner-flag--staff"))
    if not badges:
        return ""
    return '<span class="owner-flags">' + "".join(badges) + "</span>"


def _facility_names_cell(f: dict[str, Any]) -> tuple[str, str]:
    """Provider/DBA on top (linked); CMS legal name below when different."""
    legal_raw = format_org_display(str(f.get("facility_name") or "—"))
    provider_raw = format_org_display(str(f.get("provider_name") or "").strip())
    ccn = str(f.get("ccn") or "").strip().zfill(6)[-6:]
    method = str(f.get("ccn_match_method") or "")
    badge = _ccn_match_badge(method) if method in ("name_exact", "fuzzy") else ""
    legal_esc = html.escape(legal_raw)
    provider_esc = html.escape(provider_raw) if provider_raw else ""
    same = bool(provider_esc) and provider_esc.upper() == legal_esc.upper()
    href = (
        f"/provider/{html.escape(ccn)}"
        if ccn.isdigit() and method in ("legal_exact", "name_exact", "fuzzy")
        else ""
    )

    link_label = provider_esc or legal_esc
    title_attr = (
        f' title="View staffing data for {html.escape(link_label, quote=True)}"'
        if href and link_label
        else ""
    )
    verified = method == "legal_exact"
    location_line = _facility_location_residents_line(f, verified=verified)
    if provider_esc and not same:
        if href:
            primary_html = (
                f'<a href="{href}" class="owner-facility-primary"{title_attr}>'
                f"{provider_esc}</a>"
            )
        else:
            primary_html = (
                f'<span class="owner-facility-primary">{provider_esc}</span>'
            )
        sub_parts = [legal_esc]
        if badge:
            sub_parts.append(badge)
        sub_html = f'<div class="owner-facility-sub">{"".join(sub_parts)}</div>' if sub_parts else ""
    else:
        if href:
            primary_html = (
                f'<a href="{href}" class="owner-facility-primary"{title_attr}>'
                f"{legal_esc}</a>"
            )
        else:
            primary_html = (
                f'<span class="owner-facility-primary">{legal_esc}</span>'
            )
        sub_html = ""

    inner = f"{primary_html}{sub_html}{location_line}"
    sort_key = _sort_attr(f.get("facility_name"))
    return f'<div class="owner-facility-names">{inner}</div>', sort_key


def _role_kind_hint(role_text: str) -> str:
    """Short direct/indirect line for ownership modal."""
    if not role_text:
        return ""
    low = role_text.lower()
    bits: list[str] = []
    if "direct" in low:
        bits.append("Direct")
    if "indirect" in low:
        bits.append("Indirect")
    if not bits and "operational" in low and "control" in low:
        bits.append("Operational control")
    if not bits and "managing employee" in low:
        bits.append("Managing employee")
    return " · ".join(bits)


def _pct_fallback_label(role_raw: str) -> str:
    """CMS often leaves PERCENTAGE OWNERSHIP blank for control roles; show a short label."""
    r = str(role_raw or "").upper()
    if "OPERATIONAL" in r and ("MANAGERIAL" in r or "MANAGER" in r):
        return "Op. ctrl"
    if "ADP OF THE SNF" in r or r.strip() == "ADP":
        return "ADP"
    if "MANAGING EMPLOYEE" in r:
        return "Mgr."
    if "5% OR GREATER" in r or "DIRECT OWNERSHIP" in r:
        return "≥5%"
    return ""


def _role_ownership_cell(f: dict[str, Any]) -> tuple[str, str]:
    """Ownership %; tap opens CMS role + association date."""
    role_raw = str(f.get("role") or "")
    role_text = format_role_text(role_raw) if role_raw else ""
    adate = _fmt_date_mdyy(f.get("association_date"))
    pct_raw = str(f.get("pct") or "").strip()
    pct = ""
    if pct_raw and pct_raw.lower() not in ("nan", "none", "—", "-", ""):
        pct = pct_raw if "%" in pct_raw else f"{pct_raw}%"

    if pct:
        pct_display = html.escape(_format_own_pct_label(pct))
    else:
        pct_display = html.escape(_pct_fallback_label(role_raw) or "—")
    has_detail = bool(role_text) or (adate and adate != "—")
    kind_hint = _role_kind_hint(role_text)
    since_html = _role_since_html(f.get("association_date"))

    if has_detail:
        modal_title = html.escape(pct or "Ownership", quote=True)
        pct_part = (
            f'<button type="button" class="owner-role-pct-btn" data-owner-info '
            f'data-info-format="ownership" '
            f'data-info-title="{modal_title}" '
            f'data-role-kind="{html.escape(kind_hint, quote=True)}" '
            f'data-role-text="{html.escape(role_text, quote=True)}" '
            f'data-role-since="{html.escape(adate if adate != "—" else "", quote=True)}" '
            f'aria-label="Ownership details: {pct_display}">'
            f"{pct_display}</button>"
        )
    else:
        pct_part = f'<span class="owner-role-pct-plain">{pct_display}</span>'

    inner = f'<div class="owner-role-pct-stack">{pct_part}{since_html}</div>'

    return f'<div class="owner-role-cell-inner">{inner}</div>', _sort_attr(pct_raw or role_raw)


def _facilities_enrollment_rows(fac_list: list[dict[str, Any]]) -> list[str]:
    rows = []
    for f in fac_list:
        loc_html, loc_sort = _facility_location_cell(f)
        city = html.escape(str(f.get("city") or "").strip() or "")
        city_cell = city or "—"
        names_html, _ = _facility_names_cell(f)
        rows.append(
            f"<tr><td>{names_html}</td>"
            f"<td>{html.escape(f.get('enrollment_id') or '—')}</td>"
            f'<td class="owner-col-location" data-label="Location" data-sort="{loc_sort}">{loc_html}</td>'
            f"<td>{city_cell}</td></tr>"
        )
    return rows


def _facilities_owner_rows(fac_list: list[dict[str, Any]]) -> list[str]:
    rows = []
    for f in fac_list:
        loc_html, loc_sort = _facility_location_cell(f)
        method = str(f.get("ccn_match_method") or "")
        verified = method == "legal_exact"
        hprd = html.escape(_fmt_hprd(f.get("hprd") if verified else None))
        stars_html, stars_sort = _cms_stars_cell(f, verified=verified)
        census = html.escape(_fmt_census(f.get("census") if verified else None))
        flags = _facility_flags_cell(f, verified=verified)
        names_html, names_sort = _facility_names_cell(f)
        role_html, role_sort = _role_ownership_cell(f)
        search = " ".join(
            [
                str(f.get("facility_name") or ""),
                str(f.get("provider_name") or ""),
                str(f.get("state") or ""),
                str(f.get("county") or ""),
                str(f.get("role") or ""),
            ]
        ).lower()
        rows.append(
            f'<tr data-search="{html.escape(search)}">'
            f'<td class="owner-col-facility" data-label="Facility" data-sort="{names_sort}">{names_html}</td>'
            f'<td class="owner-col-location" data-label="Location" data-sort="{loc_sort}">{loc_html}</td>'
            f'<td class="owner-role-cell owner-col-role" data-label="% Own." data-sort="{role_sort}">{role_html}</td>'
            f'<td class="num owner-col-hprd" data-label="HPRD" data-sort="{_sort_attr(hprd if verified else "")}">{hprd}</td>'
            f'<td class="num owner-col-ratings" data-label="Ratings" data-sort="{html.escape(stars_sort)}">{stars_html}</td>'
            f'<td class="num owner-col-census" data-label="Census" data-sort="{_sort_attr(census if verified else "")}">{census}</td>'
            f'<td class="owner-col-flags" data-label="Flags" data-sort="">{flags}</td></tr>'
        )
    return rows


def _owner_facilities_table_html(
    fac_list: list[dict[str, Any]], profile: dict[str, Any], *, pac: str = ""
) -> str:
    n = len(fac_list)
    if n == 0:
        title = _facilities_portfolio_title(profile)
        return (
            f'<h2 class="section-header">{title}</h2>'
            '<p class="pbj-meta-line">No rows.</p>'
        )
    thead = (
        '<th data-sort="legal" class="sortable owner-col-facility">Facility <span class="sort-icon"></span></th>'
        '<th data-sort="county" class="sortable owner-col-location">Location <span class="sort-icon"></span></th>'
        '<th data-sort="role" class="sortable num owner-col-role" title="Percent ownership">'
        '% Own. <span class="sort-icon"></span></th>'
        '<th data-sort="hprd" class="sortable num owner-col-hprd" title="Facility-reported PBJ total nurse HPRD">HPRD <span class="sort-icon"></span></th>'
        '<th data-sort="stars" class="sortable num owner-col-ratings">'
        'Ratings <span class="sort-icon"></span></th>'
        '<th data-sort="census" class="sortable num owner-col-census">Census <span class="sort-icon"></span></th>'
        '<th class="owner-col-flags">Flags</th>'
    )
    filter_html = ""
    mobile_toolbar = ""
    if n >= FACILITIES_FILTER_MIN:
        filter_html = (
            '<div class="owner-facilities-header-actions">'
            '<button type="button" class="owner-table-view-toggle" id="ownerFacilitiesTableViewBtn" '
            'aria-pressed="false" aria-label="Switch to table view">Table view</button>'
            f'<input type="search" id="ownerFacilitiesFilter" class="owner-table-filter-input owner-table-filter-input--desktop" '
            f'placeholder="Filter…" autocomplete="off" '
            f'aria-label="Filter {n} facilities">'
            '<span class="owner-table-filter-count" id="ownerFacilitiesFilterCount" hidden></span>'
            "</div>"
        )
    if n >= FACILITIES_MOBILE_FILTER_MIN:
        mobile_toolbar = (
            '<div class="owner-facilities-mobile-toolbar owner-table-only-mobile">'
            f'<input type="search" id="ownerFacilitiesFilterMobile" class="owner-table-filter-input" '
            f'placeholder="Filter {n} facilities…" autocomplete="off" '
            f'aria-label="Filter facilities">'
            '<span class="owner-table-filter-count" id="ownerFacilitiesFilterCountMobile" hidden></span>'
            "</div>"
        )
    show_more_btn = ""
    list_extra_class = ""
    if n > FACILITIES_MOBILE_PREVIEW:
        list_extra_class = " owner-mobile-card-list--collapsed"
        show_more_btn = (
            f'<button type="button" class="owner-facilities-show-more owner-table-only-mobile" '
            f'id="ownerFacilitiesShowMore" data-total="{n}" data-preview="{FACILITIES_MOBILE_PREVIEW}">'
            f"Show all {n} facilities</button>"
        )
    title = _facilities_portfolio_title(profile)
    heading = (
        f'<div class="owner-facilities-header">'
        f'<h2 class="section-header owner-facilities-heading">{title}</h2>'
        f"{filter_html}</div>"
    )
    owner_rows = _facilities_owner_rows(fac_list)
    mobile_cards = [_facility_mobile_card(f) for f in fac_list]
    mobile_list = (
        f'<ul class="owner-mobile-card-list owner-mobile-card-list--facilities{list_extra_class}" '
        f'role="list" id="ownerFacilitiesMobileList" data-preview="{FACILITIES_MOBILE_PREVIEW}">'
        + "".join(mobile_cards)
        + "</ul>"
        + show_more_btn
    )
    desktop = (
        '<div class="chow-table-scroll chow-table-scroll--touch owner-facilities-scroll">'
        '<table class="chow-table owner-facilities-table chow-table--compact-sm" id="ownerFacilitiesTable">'
        f"<thead><tr>{thead}</tr></thead><tbody>"
        + "".join(owner_rows)
        + "</tbody></table></div>"
    )
    dual = _owner_table_dual(
        desktop_html=desktop,
        mobile_html=mobile_toolbar + mobile_list,
    )
    return (
        '<section class="owner-facilities-section" id="ownerFacilitiesPortfolio" '
        'aria-label="Facilities in this portfolio">'
        + heading
        + dual
        + _facilities_match_note(profile)
        + "</section>"
    )


def _table_with_preview(
    title: str,
    thead: str,
    all_rows: list[str],
    preview: int,
    entity_label: str,
    *,
    mobile_cards: list[str] | None = None,
    mobile_list_class: str = "",
) -> str:
    n = len(all_rows)
    if n == 0:
        return f'<h2 class="section-header">{title}</h2><p class="pbj-meta-line">No rows.</p>'

    preview_rows = all_rows[:preview]
    rest_rows = all_rows[preview:]
    cards = mobile_cards if mobile_cards is not None else []
    preview_cards = cards[:preview]
    rest_cards = cards[preview:] if cards else []

    def _dual_block(row_html: list[str], card_html: list[str]) -> str:
        desk = (
            '<div class="chow-table-scroll chow-table-scroll--touch owner-preview-table-scroll" '
            'style="max-height:480px;">'
            f'<table class="chow-table chow-tx-table--mobile"><thead><tr>{thead}</tr></thead><tbody>'
            + "".join(row_html)
            + "</tbody></table></div>"
        )
        mob = _owner_mobile_card_list(card_html, mobile_list_class) if card_html else ""
        return _owner_table_dual(desktop_html=desk, mobile_html=mob)

    table = _dual_block(preview_rows, preview_cards)
    if not rest_rows:
        return f'<h2 class="section-header">{title}</h2>{table}'

    footer = (
        f'<p class="owner-table-footer">{n} {html.escape(entity_label)} · '
        f"Showing {preview} of {n}</p>"
    )
    extra = (
        f'<details class="owner-collapsible"><summary>Show all {n} {html.escape(entity_label)} '
        f"({len(rest_rows)} more)</summary>"
        + _dual_block(all_rows, cards)
        + "</details>"
    )
    return f'<h2 class="section-header">{title}</h2>{table}{footer}{extra}'


def _owners_primary_section_html(profile: dict[str, Any], kind: str, ow_label: str) -> str:
    """Prominent owners block for enrollment profiles (before facilities and CHOW)."""
    if kind not in ("enrollment", "both"):
        return ""
    cps = profile.get("control_parties") or []
    if not cps:
        return ""
    inner = _control_parties_html(cps, ow_label, title="Owners & control parties")
    return f'<section class="owner-primary-owners" aria-label="Owners and control parties">{inner}</section>'


def _control_parties_html(
    control_parties: list[dict[str, Any]],
    ow_label: str,
    *,
    title: str = "Owner & control parties",
) -> str:
    if not control_parties:
        return ""

    n = len(control_parties)
    orgs = sum(1 for p in control_parties if (p.get("party_type") or "").lower().startswith("org"))
    inds = n - orgs

    cp_rows = []
    cp_mobile: list[str] = []
    for p in control_parties:
        owner_pac = html.escape(p.get("owner_associate_id") or "—")
        raw_name = p.get("name") or "—"
        pname = html.escape(
            format_org_display(str(raw_name)) if raw_name != "—" else "—"
        )
        ptype = html.escape(_format_party_type(p.get("party_type") or ""))
        roles = "; ".join(
            html.escape(format_role_text(r)) for r in (p.get("roles") or [])[:3]
        )
        pcts = ", ".join(html.escape(x) for x in (p.get("pcts") or [])[:3] if x)
        profile_url = p.get("profile_url") or ""
        if profile_url and p.get("is_owner_control_pac"):
            name_cell = f'<a href="{html.escape(profile_url)}">{pname}</a>'
            pac_cell = f'<a href="{html.escape(profile_url)}">{owner_pac}</a>'
        else:
            name_cell = pname
            pac_cell = owner_pac
        cp_rows.append(
            f"<tr><td>{name_cell}</td><td>{pac_cell}</td><td>{ptype}</td>"
            f"<td>{roles or '—'}</td><td>{pcts or '—'}</td></tr>"
        )
        cp_mobile.append(_control_party_mobile_card(p))

    thead = (
        "<th>Name</th><th>Owner/control PAC</th><th>Type</th>"
        "<th>Role(s)</th><th>%</th>"
    )
    intro = (
        f'<p class="owner-control-summary owner-control-summary--compact">'
        f"<strong>{n}</strong> parties: "
        f"{orgs} organizations · {inds} individuals</p>"
    )
    table_block = _table_with_preview(
        title,
        thead,
        cp_rows,
        PREVIEW_CONTROL_PARTIES,
        "parties",
        mobile_cards=cp_mobile,
        mobile_list_class="owner-mobile-card-list--parties",
    )
    return intro + table_block


def _facilities_sections_html(
    profile: dict[str, Any],
    kind: str,
    facilities: list[dict[str, Any]],
    ow_label: str,
    *,
    skip_control_parties: bool = False,
) -> str:
    if kind == "owner_control":
        html_out = _owner_facilities_table_html(
            facilities, profile, pac=str(profile.get("associate_id") or "")
        )
        tx = _ownership_transactions_html(
            profile, str(profile.get("associate_id") or ""), bool(profile.get("is_chow_only"))
        )
        return html_out + (tx or "")

    if kind in ("enrollment", "both", "chow_only"):
        has_ccn = any(str(f.get("ccn") or "").strip() for f in facilities)
        if kind == "enrollment" and has_ccn:
            html_out = _owner_facilities_table_html(
                facilities,
                profile,
                pac=str(profile.get("associate_id") or ""),
            )
        else:
            thead_en = (
                "<th>Facility</th><th>Enrollment ID</th><th>Location</th><th>City</th>"
            )
            html_out = _table_with_preview(
                "Linked facilities",
                thead_en,
                _facilities_enrollment_rows(facilities),
                PREVIEW_FACILITIES,
                "enrollments",
                mobile_cards=[_enrollment_facility_mobile_card(f) for f in facilities],
                mobile_list_class="owner-mobile-card-list--facilities",
            )
        if not skip_control_parties:
            cps = profile.get("control_parties") or []
            if cps:
                html_out += _control_parties_html(cps, ow_label)
        tx = _ownership_transactions_html(
            profile, str(profile.get("associate_id") or ""), kind == "chow_only"
        )
        if tx:
            html_out += tx
        return html_out

    return ""


def _owner_dual_section_html(profile: dict[str, Any], kind: str) -> str:
    if kind != "both" or not profile.get("owner_control_section"):
        return ""
    ow = profile["owner_control_section"]
    fac_list = ow.get("facilities") or []
    ps = ow.get("portfolio_summary") or {}
    extra = ""
    if ps.get("n_facilities"):
        extra = (
            f'<p class="pbj-meta-line">As owner/control party on '
            f'<strong>{ps["n_facilities"]}</strong> other enrollment(s).</p>'
        )
    thead = (
        "<th>Facility</th><th>Location</th><th>%</th>"
        "<th>HPRD</th><th>Ratings</th><th>Census</th><th>Flags</th>"
    )
    block = _table_with_preview(
        "Also reported as owner / control elsewhere",
        thead,
        _facilities_owner_rows(fac_list),
        PREVIEW_FACILITIES,
        "facilities",
        mobile_cards=[_facility_mobile_card(f) for f in fac_list],
        mobile_list_class="owner-mobile-card-list--facilities",
    )
    return extra + block


def _ownership_transactions_html(profile: dict[str, Any], pac: str, is_chow_only: bool) -> str:
    from ownership.chow_lookup import format_chow_date

    chow_rows = _dedupe_chow_transactions(profile.get("chow_transactions") or [])
    if not chow_rows:
        return ""

    tx_rows = []
    tx_mobile: list[str] = []
    for rec in chow_rows[:25]:
        eff = html.escape(format_chow_date(str(rec.get("effective_date") or "")) or "—")
        ccn = str(rec.get("ccn") or "").strip().zfill(6)[-6:]
        fac_raw = format_org_display(
            str(rec.get("facility_display_name") or rec.get("buyer_dba_name") or "—")
        )
        fac_esc = html.escape(fac_raw)
        if ccn:
            fac_cell = (
                f'<a class="owner-tx-facility" href="/provider/{html.escape(ccn)}" '
                f'title="View staffing data for {fac_esc}">{fac_esc}</a>'
            )
        else:
            fac_cell = f'<span class="owner-tx-facility">{fac_esc}</span>'
        buyer = html.escape(format_org_display(str(rec.get("buyer_org_name") or "—")))
        seller = html.escape(format_org_display(str(rec.get("seller_org_name") or "—")))
        side = _chow_transaction_side_label(str(rec.get("chow_role") or ""))
        side_cell = html.escape(side) if side else "—"
        tx_rows.append(
            f"<tr><td>{eff}</td><td>{fac_cell}</td><td>{buyer}</td>"
            f"<td>{seller}</td><td>{side_cell}</td></tr>"
        )
        tx_mobile.append(_ownership_timeline_item_html(rec))

    desktop = (
        '<div class="chow-table-scroll chow-table-scroll--touch owner-tx-scroll" '
        'style="max-height:360px;">'
        '<table class="chow-table chow-tx-table owner-tx-table">'
        "<thead><tr>"
        "<th>Effective</th><th>Facility</th><th>Buyer</th><th>Seller</th><th>Side</th>"
        "</tr></thead><tbody>"
        + "".join(tx_rows)
        + "</tbody></table></div>"
    )
    mobile_list = (
        '<ol class="owner-timeline-list owner-mobile-card-list--tx">'
        + "".join(tx_mobile)
        + "</ol>"
    )
    inner = _owner_table_dual(
        desktop_html=desktop,
        mobile_html=mobile_list,
    )
    n = len(chow_rows)
    count_line = (
        f'<p class="owner-tx-count">{n} CMS ownership change record{"s" if n != 1 else ""} '
        f"(showing {min(n, 25)})</p>"
    )
    return (
        '<section class="owner-tx-section" aria-label="Ownership history">'
        '<h2 class="section-header">Ownership history</h2>'
        f"{count_line}"
        f"{inner}"
        "</section>"
    )


def _cli_main() -> None:
    """Preview rendered body for a PAC (dev helper). Run from repo root."""
    import argparse
    import sys

    from ownership.owner_profile import load_owner_profile

    parser = argparse.ArgumentParser(description="Preview owner profile HTML body")
    parser.add_argument("pac", nargs="?", default="7618113481", help="10-digit CMS associate ID")
    parser.add_argument(
        "--related-only",
        action="store_true",
        help="Print only the Frequent associates section HTML",
    )
    args = parser.parse_args()
    profile = load_owner_profile(str(args.pac).strip())
    if not profile:
        print(f"No profile for PAC {args.pac!r}", file=sys.stderr)
        raise SystemExit(1)
    if args.related_only:
        print(_related_associates_html(profile) or "(empty — no related associates)")
        return
    body, *_rest = render_owner_profile_body(profile)
    print(body)


if __name__ == "__main__":
    _cli_main()
