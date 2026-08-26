"""HTML rendering for /owners/<pac> — portfolio-first CMS owner profiles."""
from __future__ import annotations

# Allow `python ownership/owner_profile_html.py` from repo root (package imports).
if __name__ == "__main__" and not __package__:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import html
import json
from urllib.parse import urlencode
from typing import Any

import re

from canonical_urls import provider_url
from ownership.beta_gate import profile_has_public_state, ownership_public_enabled_for_state
from ownership.state_owner_index import PUBLIC_OWNER_INDEX_SLUGS, STATE_INDEX_META
from ownership.owner_fec_section import render_owner_fec_contributions_section
from ownership.owner_profile import owner_profile_canonical_path
from utils.seo_utils import owner_page_seo_from_profile
from ownership.display_format import (
    cms_rating_stars_html,
    cms_ratings_compact_html,
    cms_ratings_stack_html,
    format_cms_star_rating,
    format_org_display,
    format_role_text,
)
from ownership.portfolio_display import (
    info_button_html as _info_button,
    owner_portfolio_snapshot_html,
    portfolio_distribution_html as _portfolio_distribution_html,
    portfolio_info_modal_html as _owner_info_modal_html,
    portfolio_state_distribution_html as _portfolio_state_distribution,
)
from ownership.sff_display import sff_flag_explainer_tuple

PREVIEW_CONTROL_PARTIES = 25
PREVIEW_FACILITIES = 15
FACILITIES_FILTER_MIN = 12
FACILITIES_MOBILE_PREVIEW = 12
FACILITIES_MOBILE_FILTER_MIN = 8
FACILITIES_DESKTOP_PREVIEW = 15
FACILITIES_SHOW_MORE_BATCH = 50

_FLAG_EXPLAINERS: dict[str, tuple[str, str]] = {
    "sff": sff_flag_explainer_tuple("sff"),
    "sffc": sff_flag_explainer_tuple("sffc"),
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
    """e.g. Associated in CMS since Feb. 2020"""
    parts = _parse_ymd(val)
    if not parts:
        return ""
    y, mo, _d = parts
    return f"Associated in CMS since {_MONTH_ABBR[mo - 1]} {y}"


def _fmt_since_short(val: Any) -> str:
    """e.g. CMS assoc. 2/20 (month/year for narrow columns)"""
    parts = _parse_ymd(val)
    if not parts:
        return ""
    y, mo, _d = parts
    return f"CMS assoc. {mo}/{y % 100:02d}"


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
        aside_bits.append(
            f'<span class="owner-m-card__metric">{html.escape(pcts)}</span>'
        )
    primary = str(p.get("primary_role_label") or "").strip()
    if primary and not roles:
        aside_bits.append(f'<span class="owner-m-card__muted">{html.escape(primary)}</span>')
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


def _format_place_label(value: str) -> str:
    """Title-case city/county labels (CMS often ships ALL CAPS)."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    return format_org_display(raw)


def _facility_location_short(f: dict[str, Any]) -> str:
    """Compact place label for table/mobile (prefer city over county)."""
    city = _format_place_label(str(f.get("city") or ""))
    st = str(f.get("state") or "").strip().upper()[:2]
    if city and len(st) == 2:
        return f"{city}, {st}"
    county = _format_place_label(str(f.get("county") or ""))
    co = county
    if co.lower().endswith(" county"):
        co = co[: -len(" county")].strip()
    if co and len(st) == 2:
        return f"{co}, {st}"
    if len(st) == 2:
        return st
    return co or "—"


def _facility_postal_address_parts(f: dict[str, Any]) -> dict[str, str]:
    """Structured mailing address from provider_info when CCN matched."""
    street = _format_place_label(str(f.get("provider_address") or ""))
    city = _format_place_label(str(f.get("city") or ""))
    county = _format_place_label(str(f.get("county") or ""))
    st = str(f.get("state") or "").strip().upper()[:2]
    zip_raw = str(f.get("zip_code") or "").strip()
    if zip_raw and "." in zip_raw:
        zip_raw = zip_raw.split(".")[0]
    zip_code = zip_raw[:10] if zip_raw else ""

    city_line_parts: list[str] = []
    if city:
        city_line_parts.append(city)
    elif county:
        co = county if "county" in county.lower() else f"{county} County"
        city_line_parts.append(co)
    if len(st) == 2:
        city_line_parts.append(st)
    city_line = ", ".join(city_line_parts)
    if zip_code:
        city_line = f"{city_line} {zip_code}".strip() if city_line else zip_code

    full_lines: list[str] = []
    if street:
        full_lines.append(street)
    if city_line:
        full_lines.append(city_line)
    if not full_lines:
        fallback = _facility_location_short(f)
        if fallback and fallback != "—":
            full_lines.append(fallback)

    return {
        "street": street,
        "city_line": city_line,
        "full_text": "\n".join(full_lines),
        "has_postal": bool(street),
    }


def _facility_location_cell(f: dict[str, Any]) -> tuple[str, str]:
    label = _facility_location_short(f)
    esc = html.escape(label)
    addr = _facility_postal_address_parts(f)
    sort_key = f"{f.get('city') or ''} {f.get('county') or ''} {f.get('state') or ''}"
    if addr.get("has_postal"):
        fac_name = format_org_display(
            str(f.get("provider_name") or f.get("facility_name") or "Facility")
        )
        return (
            f'<button type="button" class="owner-facility-location-btn" data-owner-info '
            f'data-info-format="address" '
            f'data-info-title="{html.escape(fac_name, quote=True)}" '
            f'data-address-street="{html.escape(addr["street"], quote=True)}" '
            f'data-address-cityline="{html.escape(addr["city_line"], quote=True)}" '
            f'data-address-full="{html.escape(addr["full_text"], quote=True)}" '
            f'aria-label="Full address for {html.escape(label, quote=True)}">{esc}</button>',
            _sort_attr(sort_key),
        )
    return f'<span class="owner-facility-location">{esc}</span>', _sort_attr(sort_key)


def _facility_location_chip(f: dict[str, Any]) -> str:
    """Tappable location chip for mobile facility cards."""
    label = _facility_location_short(f)
    if not label or label == "—":
        return ""
    addr = _facility_postal_address_parts(f)
    esc = html.escape(label)
    if not addr.get("has_postal"):
        return f'<span class="owner-m-card-chip owner-m-card-chip--place">{esc}</span>'
    fac_name = format_org_display(
        str(f.get("provider_name") or f.get("facility_name") or "Facility")
    )
    return (
        f'<button type="button" class="owner-m-card-chip owner-m-card-chip--place owner-facility-location-btn" '
        f'data-owner-info data-info-format="address" '
        f'data-info-title="{html.escape(fac_name, quote=True)}" '
        f'data-address-street="{html.escape(addr["street"], quote=True)}" '
        f'data-address-cityline="{html.escape(addr["city_line"], quote=True)}" '
        f'data-address-full="{html.escape(addr["full_text"], quote=True)}" '
        f'aria-label="Full address: {html.escape(label, quote=True)}">{esc}</button>'
    )


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


def _format_ownership_pct_value(raw: str) -> str:
    """CMS ownership % for display (one decimal when fractional)."""
    s = str(raw or "").strip()
    if not s or s.lower() in ("nan", "none", "—", "-", "n/a"):
        return ""
    core = s.replace("%", "").replace(",", "").strip()
    if not core:
        return ""
    try:
        v = float(core)
        if abs(v - round(v)) < 1e-9:
            return f"{int(round(v))}%"
        return f"{v:.1f}%"
    except ValueError:
        return s if "%" in s else f"{s}%"


def _format_own_pct_label(value: str) -> str:
    """Compact CMS ownership stake for mobile cards."""
    s = str(value or "").strip()
    if not s or s == "—":
        return s
    low = s.lower()
    if "ownership interest" in low or " ownership" in low:
        m = re.search(r"([\d.,]+)\s*%", s)
        if m:
            pct = _format_ownership_pct_value(m.group(1))
            return f"{pct} ownership" if pct else s
        return s
    if "%" in s or any(ch.isdigit() for ch in s):
        pct = _format_ownership_pct_value(s)
        return f"{pct} ownership" if pct else s
    return s


def _facility_ownership_modal_attr_str(f: dict[str, Any], *, pct_label: str = "") -> str:
    """data-* attributes for ownership / role info modal."""
    from ownership.role_classification import (
        ASSOC_DATE_COL,
        PCT_COL,
        ROLE_CODE_COL,
        ROLE_TEXT_COL,
        classify_owner_record,
    )

    role_raw = str(f.get("role") or "")
    role_text = format_role_text(role_raw) if role_raw else ""
    adate = _fmt_date_mdyy(f.get("association_date"))
    info = classify_owner_record(
        {
            ROLE_CODE_COL: f.get("role_code") or "",
            ROLE_TEXT_COL: role_raw,
            PCT_COL: f.get("pct") or "",
            ASSOC_DATE_COL: f.get("association_date") or "",
        }
    )
    category = str(
        info.get("primary_role_label") or info.get("role_category_label") or ""
    ).strip()
    pct_reported = _format_ownership_pct_value(str(f.get("pct") or ""))
    kind_hint = _role_kind_hint(role_text)
    fac = format_org_display(str(f.get("facility_name") or ""))
    title = fac or category or "Ownership"
    bits = ["data-owner-info", 'data-info-format="ownership"']
    bits.append(f'data-info-title="{html.escape(title, quote=True)}"')
    for key, val in (
        ("data-role-category", category),
        ("data-role-code", str(info.get("role_code") or "")),
        ("data-role-text", role_text),
        ("data-role-since", adate if adate != "—" else ""),
        ("data-pct-reported", pct_reported),
        ("data-role-kind", kind_hint),
        ("data-facility-name", fac),
    ):
        if val:
            bits.append(f'{key}="{html.escape(str(val), quote=True)}"')
    return " ".join(bits)


def _facility_mobile_own_chip(f: dict[str, Any]) -> str:
    """Inline ownership % for compact mobile cards (tap for CMS role when available)."""
    role_raw = str(f.get("role") or "")
    pct_raw = str(f.get("pct") or "").strip()
    pct = _format_ownership_pct_value(pct_raw) if pct_raw else ""
    pct_label = _format_own_pct_label(pct) if pct else _pct_fallback_label(role_raw) or ""
    pct_display = html.escape(pct_label)
    if not pct_display:
        return ""
    label = pct_display
    adate = _fmt_date_mdyy(f.get("association_date"))
    role_text = format_role_text(role_raw) if role_raw else ""
    if role_text or (adate and adate != "—") or pct:
        attrs = _facility_ownership_modal_attr_str(f, pct_label=pct_label)
        return (
            f'<button type="button" class="owner-m-card-chip owner-m-card-chip--own owner-role-pct-btn" '
            f"{attrs} "
            f'aria-label="Ownership {label} (tap for details)">{label}</button>'
        )
    return f'<span class="owner-m-card-chip owner-m-card-chip--own">{label}</span>'


def _facility_mobile_primary_block(f: dict[str, Any]) -> str:
    """Row 1: provider/DBA (linked); row 2: CMS legal name + tappable city chip when different."""
    legal_raw = format_org_display(str(f.get("facility_name") or "—"))
    provider_raw = format_org_display(str(f.get("provider_name") or "").strip())
    ccn = str(f.get("ccn") or "").strip().zfill(6)[-6:]
    method = str(f.get("ccn_match_method") or "")
    legal_esc = html.escape(legal_raw)
    provider_esc = html.escape(provider_raw) if provider_raw else ""
    same = bool(provider_esc) and provider_esc.upper() == legal_esc.upper()
    link_label = provider_raw or legal_raw
    href = (
        html.escape(provider_url(ccn, link_label))
        if ccn.isdigit() and method in ("legal_exact", "name_exact", "fuzzy")
        else ""
    )
    primary_esc = provider_esc if provider_esc else legal_esc
    link_label = provider_raw or legal_raw
    title_attr = ""
    if href and link_label:
        title_attr = (
            f' title="{html.escape(f"View staffing data for {link_label}", quote=True)}"'
        )
    if href:
        row1 = f'<a href="{href}" class="owner-m-card__title"{title_attr}>{primary_esc}</a>'
    else:
        row1 = f'<span class="owner-m-card__title">{primary_esc}</span>'
    html_out = f'<div class="owner-m-card__title-line">{row1}</div>'
    place = _facility_location_chip(f)
    if provider_esc and not same:
        sub_left = f'<span class="owner-m-card__sub">{legal_esc}</span>'
        aside = (
            f'<span class="owner-m-card__sub-aside">{place}</span>' if place else ""
        )
        html_out += f'<div class="owner-m-card__subrow">{sub_left}{aside}</div>'
    elif place:
        html_out += (
            f'<div class="owner-m-card__subrow owner-m-card__subrow--place-only">'
            f'<span class="owner-m-card__sub-aside">{place}</span></div>'
        )
    return html_out


def _facility_mobile_metrics_block(f: dict[str, Any], *, verified: bool) -> str:
    """Mobile facility card metrics: ownership · census/HPRD; then stars + flags."""
    sep = '<span class="owner-m-card__sep" aria-hidden="true"> · </span>'
    row1: list[str] = []
    own = _facility_mobile_own_chip(f)
    if own:
        row1.append(own)
    census = _fmt_census(f.get("census") if verified else None)
    if census and census != "—":
        row1.append(f'<span class="owner-m-card-chip">{html.escape(census)} res</span>')
    hprd = _fmt_hprd(f.get("hprd") if verified else None)
    if hprd and hprd != "—":
        row1.append(f'<span class="owner-m-card-chip">{html.escape(hprd)} HPRD</span>')

    row2: list[str] = []
    ratings = cms_ratings_compact_html(
        f.get("overall_rating"),
        f.get("staffing_rating"),
        verified=verified,
    )
    if ratings:
        row2.append(ratings)
    flags = _facility_flags_cell(f, verified=verified, skip_star_flags=True)
    if flags:
        row2.append(flags)

    if not row1 and not row2:
        return ""
    rows: list[str] = []
    if row1:
        rows.append(
            '<div class="owner-m-card__stats-row">' + sep.join(row1) + "</div>"
        )
    if row2:
        rows.append(
            '<div class="owner-m-card__stats-row owner-m-card__stats-row--secondary">'
            + sep.join(row2)
            + "</div>"
        )
    return '<div class="owner-m-card__metrics">' + "".join(rows) + "</div>"


def _facility_mobile_card(f: dict[str, Any]) -> str:
    method = str(f.get("ccn_match_method") or "")
    verified = method == "legal_exact"
    title_block = _facility_mobile_primary_block(f)
    metrics = _facility_mobile_metrics_block(f, verified=verified)
    search = " ".join(
        [
            str(f.get("facility_name") or ""),
            str(f.get("provider_name") or ""),
            str(f.get("state") or ""),
            str(f.get("county") or ""),
            str(f.get("role") or ""),
        ]
    ).lower()
    st_code = _facility_state_code(f)
    return (
        f'<li class="owner-m-card owner-m-card--facility owner-m-card--facility-compact" '
        f'data-search="{html.escape(search)}" data-state="{html.escape(st_code)}">'
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
            f'<a class="owner-timeline-facility" href="{html.escape(provider_url(ccn, fac_raw))}">{fac_esc}</a>'
        )
    else:
        fac_html = f'<span class="owner-timeline-facility">{fac_esc}</span>'
    seller = html.escape(format_org_display(str(rec.get("seller_org_name") or "—")))
    buyer = html.escape(format_org_display(str(rec.get("buyer_org_name") or "—")))
    side = _chow_transaction_side_label(str(rec.get("chow_role") or ""))
    parties = f'<span class="owner-timeline-seller">{seller}</span> \u2192 <span class="owner-timeline-buyer">{buyer}</span>'
    side_html = (
        f' <span class="owner-timeline-side">({html.escape(side)})</span>'
        if side
        else ""
    )
    return (
        f'<li class="owner-timeline-item">'
        f'<div class="owner-timeline-date">{eff}</div>'
        f'<div class="owner-timeline-body">'
        f'<div class="owner-timeline-facility-row">{fac_html}{side_html}</div>'
        f'<div class="owner-timeline-parties" aria-label="Seller to buyer">{parties}</div>'
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
    link_type = html.escape(_associate_source_label_short(r) or "—")
    meta = f'<span class="owner-m-card__meta">{shared} shared · {link_type}</span>'
    return (
        '<li class="owner-m-card owner-m-card--associate">'
        f"{name_html}{meta}"
        "</li>"
    )


def render_owner_profile_body(
    profile: dict[str, Any], *, include_heavy: bool = False
) -> tuple[str, str, str, str]:
    """Return (body_html, page_title, meta_desc, canonical_path_suffix).

    Default page: fast summary + initial facilities batch + inline deferred sections.
    ``include_heavy`` (?full=1) remains for backwards compatibility: preloads associates
    and expands the facilities table. Users never need ?full=1 for a complete profile.
    """
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
        profile,
        kind,
        facilities,
        ow_label,
        skip_control_parties=bool(owners_primary_html),
        force_full_table=include_heavy,
    )

    # Dual-PAC detail + FEC shell always on-page; associates collapsed (prefetch only for ?full=1).
    if include_heavy and not profile.get("related_associates"):
        from ownership.owner_profile import build_related_associates

        profile["related_associates"] = build_related_associates(profile)
    associates_html = _related_associates_html(
        profile, preload=include_heavy or bool(profile.get("related_associates"))
    )
    owner_section_html = _owner_dual_section_html(profile, kind)
    fec_html = render_owner_fec_contributions_section(profile)
    deferred_html = "".join(
        bit
        for bit in (associates_html, owner_section_html, fec_html)
        if bit and bit.strip()
    )

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
      {deferred_html}
      </div>
    """
    return body, page_title, meta_desc, owner_profile_canonical_path(profile) or f"/owners/{pac}"



def _cms_source_link_html(kind: str, pac: str) -> str:
    """Outbound CMS Ownership dataset filter for this associate PAC."""
    pac = (pac or "").strip()
    if kind not in ("owner_control", "both") or not pac:
        return ""
    href = (
        "https://data.cms.gov/data-api/v1/dataset/"
        "afe44b85-cc6d-40d7-b5df-00ae8910d1d2/data?"
        + urlencode({"filter[ASSOCIATE ID - OWNER]": pac})
    )
    return (
        f'<a class="owner-cms-source" href="{html.escape(href, quote=True)}" '
        'target="_blank" rel="noopener noreferrer">'
        'CMS source <span aria-hidden="true">↗</span></a>'
    )



def _states_meta_html(profile: dict[str, Any]) -> str:
    """Legacy meta-line states control — unused once States is a summary metric."""
    return ""


def _states_breakdown_modal_html(profile: dict[str, Any]) -> str:
    ps = profile.get("portfolio_summary") or {}
    by_state: list[tuple[str, int]] = list(ps.get("by_state") or [])
    if not by_state:
        states = profile.get("states") or []
        if not states:
            return ""
        by_state = [(st, 0) for st in states]
    rows = []
    for st, cnt in by_state:
        rows.append(
            f'<li class="owner-states-row">'
            f'<span class="owner-states-code">{html.escape(st)}</span>'
            f'<span class="owner-states-count">{cnt if cnt else "—"}</span>'
            f"</li>"
        )
    return f"""
      <div class="owner-states-popover" id="ownerStatesPopover" hidden role="dialog"
           aria-labelledby="ownerStatesPopoverTitle">
        <div class="owner-states-popover-card">
          <h2 class="owner-states-popover-title" id="ownerStatesPopoverTitle">Facilities by state</h2>
          <ul class="owner-states-list" role="list">{"".join(rows)}</ul>
        </div>
      </div>"""


def _cms_snf_owners_filtered_url(pac: str) -> str:
    """CMS SNF All Owners API filtered to this owner PAC (ASSOCIATE ID - OWNER)."""
    from urllib.parse import urlencode

    pac_s = str(pac or "").strip()
    if len(pac_s) != 10 or not pac_s.isdigit():
        return ""
    base = (
        "https://data.cms.gov/data-api/v1/dataset/"
        "afe44b85-cc6d-40d7-b5df-00ae8910d1d2/data"
    )
    return f"{base}?{urlencode({'filter[ASSOCIATE ID - OWNER]': pac_s})}"


def _cms_source_badge_html(pac: str) -> str:
    href = _cms_snf_owners_filtered_url(pac)
    if not href:
        return ""
    return (
        f'<a class="owner-cms-source" href="{html.escape(href, quote=True)}" '
        'target="_blank" rel="noopener noreferrer" '
        'title="CMS SNF All Owners records for this owner PAC">'
        "CMS source <span aria-hidden=\"true\">↗</span></a>"
    )


def _max_ownership_pct_display(profile: dict[str, Any]) -> str:
    """Highest reported ownership % across facility rows (e.g. '100%')."""
    best: float | None = None
    best_raw = ""
    for fac in profile.get("facilities") or []:
        raw = str(fac.get("pct") or "").strip()
        if not raw or raw in ("—", "-", "n/a", "N/A", "nan"):
            continue
        num_s = raw.replace("%", "").replace(",", "").strip()
        try:
            val = float(num_s)
        except ValueError:
            continue
        if best is None or val > best:
            best = val
            best_raw = f"{int(val)}%" if val == int(val) else f"{val:g}%"
    if best is None:
        return ""
    return best_raw


def _header_role_line_html(profile: dict[str, Any], *, page_help: str) -> str:
    """Compact role / ownership interest line under type · PAC."""
    seg = str(profile.get("publication_segment") or "").strip()
    role_labels = {
        "ownership_interest_only": "CMS ownership interest",
        "mixed_ownership_plus_other": "Mixed CMS roles",
        "control_managerial_no_ownership": "Managing/control",
        "governance_only": "Officer/director",
        "administrative_enrollment_style": "Enrollment associate",
        "financial_only": "Financial interest",
        "chow_enrollment_party": "CHOW party",
        "other_or_unclassified": "CMS associate",
        "unknown_placeholder": "CMS associate",
    }
    role = role_labels.get(seg) or str(profile.get("publication_descriptor") or "").strip()
    if not role:
        return ""
    pct = _max_ownership_pct_display(profile)
    bits = [html.escape(role)]
    if pct:
        bits.append(f"up to {html.escape(pct)}")
    text = " · ".join(bits)
    return (
        f'<div class="owner-profile-role-line">'
        f'<span class="owner-profile-role-text">{text}</span>{page_help}'
        f"</div>"
    )


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
            f'<span class="owner-meta-item owner-meta-row owner-meta-row--enrollment">'
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
    # Compact descriptors live in the header; keep long CMS copy behind ⓘ help only.
    del kind, is_chow_only
    return ""


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
            "Enrollment entity: CMS facility enrollment PAC with linked owners, facilities, "
            f"and any ownership transactions in CMS data ({n} linked facilities in {snf_src})."
        ),
        "both": (
            "Enrollment and owner PAC: this number appears as both the facility enrollment "
            f"and an owner/control party in CMS data ({n} linked facilities in {snf_src})."
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


def _primary_owner_state_code(profile: dict[str, Any]) -> str:
    """State code for back link to /owners/{slug} (largest portfolio slice)."""
    by_state: list[tuple[str, int]] = list(
        (profile.get("portfolio_summary") or {}).get("by_state") or []
    )
    if by_state:
        return str(max(by_state, key=lambda row: int(row[1] or 0))[0] or "").strip().upper()[:2]
    for st in profile.get("states") or []:
        code = str(st or "").strip().upper()[:2]
        if code:
            return code
    return ""


def _owner_public_state_codes(profile: dict[str, Any]) -> list[str]:
    """Distinct published state slices represented by an owner profile."""
    codes: list[str] = []
    by_state = (profile.get("portfolio_summary") or {}).get("by_state") or []
    candidates = [row[0] for row in by_state if row] + list(profile.get("states") or [])
    for raw in candidates:
        code = str(raw or "").strip().upper()[:2]
        if code and code not in codes and ownership_public_enabled_for_state(code):
            codes.append(code)
    return codes


def _owner_index_back_link_html(profile: dict[str, Any]) -> str:
    """Back to one state index only when the profile is genuinely single-state."""
    public_states = _owner_public_state_codes(profile)
    if len(public_states) > 1:
        return (
            '<a class="owner-profile-back" href="/owners" '
            'title="Back to nursing home ownership search">← Owners</a>'
        )
    st = _primary_owner_state_code(profile)
    if not st or not ownership_public_enabled_for_state(st):
        return ""
    slug = next(
        (s for s, code in PUBLIC_OWNER_INDEX_SLUGS.items() if code == st),
        "",
    )
    meta = STATE_INDEX_META.get(st) or {}
    if not slug:
        return ""
    short = st
    label = str(meta.get("name") or short).strip()
    text = f"← {short} owners" if label else f"← {short} ownership"
    title = f"Back to {label} ownership search" if label else "Back to state ownership search"
    return (
        f'<a class="owner-profile-back" href="/owners/{html.escape(slug)}" '
        f'title="{html.escape(title, quote=True)}">{html.escape(text)}</a>'
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
    from ownership.publication_taxonomy import (
        ownership_pct_headline,
        publication_role_label,
        segment_for_profile,
    )

    _ = segment_for_profile(profile)
    role = publication_role_label(profile)
    pct_chip, pct_help = ownership_pct_headline(profile)
    # One descriptor line: role (+ optional OI %) with a single ⓘ.
    desc_text = role
    if pct_chip:
        desc_text = f"{role} · {pct_chip}" if role else pct_chip
    help_body = _owner_page_help_body(profile, kind, en_label=en_label, ow_label=ow_label)
    if pct_help:
        help_body = f"{pct_help}\n\n{help_body}"
    help_title = "Ownership percentage" if pct_chip else "PBJ320 Ownership"
    role_help = (
        _info_button(help_title, help_body, label="?", cls="owner-info-btn owner-info-btn--role")
        if desc_text
        else ""
    )
    descriptor_row = ""
    if desc_text:
        descriptor_row = (
            f'<div class="owner-profile-descriptor-row">'
            f'<span class="owner-profile-descriptor">{html.escape(desc_text)}</span>'
            f"{role_help}</div>"
        )

    pac_label = "PAC"
    if kind == "owner_control":
        pac_label = ow_label or "Owner PAC"
    elif kind == "enrollment":
        pac_label = en_label or "Enrollment PAC"
    elif kind == "both":
        pac_label = "PAC"

    meta_bits: list[str] = []
    if owner_type:
        meta_bits.append(html.escape(owner_type))
    if pac:
        meta_bits.append(f"{html.escape(pac_label)} {pac}")
    enrollment_ids = profile.get("enrollment_ids") or []
    if enrollment_ids and kind in ("enrollment", "both"):
        ids = ", ".join(html.escape(e) for e in enrollment_ids[:2])
        if len(enrollment_ids) > 2:
            ids += f" (+{len(enrollment_ids) - 2})"
        meta_bits.append(f"Enrollment ID {ids}")
    # States live in the summary metric strip (interactive card), not the meta line.
    _ = states_meta

    meta_inner = ' <span class="owner-meta-sep" aria-hidden="true">·</span> '.join(meta_bits)
    meta_row = (
        f'<div class="owner-profile-meta-line">{meta_inner}</div>' if meta_inner else ""
    )

    back_link = _owner_index_back_link_html(profile)
    back_html = f'<div class="owner-profile-back-wrap">{back_link}</div>' if back_link else ""
    cms_source = _cms_source_link_html(kind, pac)
    cms_html = f'<div class="owner-profile-header-actions">{cms_source}</div>' if cms_source else ""
    return f"""
      <header class="owner-profile-header owner-profile-header--compact">
        <div class="owner-profile-header-top">
          {back_html}
          {cms_html}
        </div>
        <div class="owner-profile-header-identity">
          <h1 class="owner-profile-name">{name}</h1>
          {descriptor_row}
          {meta_row}
        </div>
      </header>"""


def _associate_shared_facilities_cell(r: dict[str, Any], *, n_facilities: int) -> str:
    snf = int(r.get("snf_shared") or 0)
    chow = int(r.get("chow_count") or 0)
    if snf:
        if n_facilities and snf <= n_facilities:
            return f"{snf} / {n_facilities}"
        return str(snf)
    if chow:
        return f"{chow} CHOW"
    return "—"


def _associate_source_label(r: dict[str, Any]) -> str:
    """Desktop relationship column — concise, single-line when possible."""
    bits: list[str] = []
    if int(r.get("snf_shared") or 0):
        if r.get("shared_ownership_interest") or r.get("is_ownership_interest"):
            bits.append("Shared ownership interest")
        else:
            bits.append("Co-enrollee")
    if int(r.get("chow_count") or 0):
        bits.append("CHOW party")
    return " · ".join(bits) if bits else "Related"


def _associate_source_label_short(r: dict[str, Any]) -> str:
    """Mobile meta line — shorter relationship wording."""
    bits: list[str] = []
    if int(r.get("snf_shared") or 0):
        if r.get("shared_ownership_interest") or r.get("is_ownership_interest"):
            bits.append("Ownership interest")
        else:
            bits.append("Co-enrollee")
    if int(r.get("chow_count") or 0):
        bits.append("CHOW party")
    return " · ".join(bits) if bits else "Related"


def _associates_summary_html(*, count_html: str) -> str:
    """One far-right disclosure chevron; hide native/details ::before via CSS."""
    return (
        '<summary class="owner-associates-summary">'
        '<span class="owner-associates-summary-label">Related CMS associates'
        f"{count_html}</span>"
        '<span class="owner-associates-caret" aria-hidden="true"></span>'
        "</summary>"
    )


def _related_associates_html(profile: dict[str, Any], *, preload: bool = False) -> str:
    """Collapsed Related CMS associates — fetch once on open unless preloaded."""
    pac = str(profile.get("associate_id") or "").strip()
    rows = profile.get("related_associates") or []
    n_fac = int((profile.get("portfolio_summary") or {}).get("n_facilities") or 0)
    has_chow = bool(profile.get("chow_transactions"))
    if not preload:
        if not pac or (n_fac < 1 and not has_chow):
            return ""
        if not rows:
            # Deferred shell — content filled by JS on first open.
            associates_help = _info_button(
                "Related CMS associates",
                (
                    "Parties that appear with this PAC on CMS records.\n\n"
                    "Shared ownership: co-disclosed ownership-interest parties on "
                    "the same nursing home enrollments.\n\n"
                    "Co-enrollee: appear together on CMS enrollment or owner rows "
                    "without implying affiliate, partner, parent, or subsidiary status.\n\n"
                    "CHOW party: buyer or seller counterparties on CMS-reported "
                    "ownership-change filings.\n\n"
                    "Sources: CMS SNF All Owners; CMS CHOW filings."
                ),
                label="?",
                cls="owner-info-btn owner-info-btn--section owner-associates-info",
            )
            return (
                f'<div class="owner-associates-block"'
                f' data-associates-pac="{html.escape(pac, quote=True)}"'
                f' data-associates-url="/owners/api/related-associates/{html.escape(pac, quote=True)}">'
                + associates_help
                + '<details class="owner-collapsible owner-associates-collapsible">'
                + _associates_summary_html(
                    count_html='<span class="owner-associates-count"></span>',
                )
                + '<div class="owner-associates-panel" data-associates-panel aria-live="polite">'
                '<div class="owner-associates-loading" role="status" hidden>'
                '<span class="owner-associates-loading-label">Loading related CMS associates…</span>'
                '<span class="owner-associates-loading-bars" aria-hidden="true">'
                '<span></span><span></span><span></span></span></div>'
                "</div>"
                "</details>"
                "</div>"
            )
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
            f'<tr><td class="owner-associate-col-name">{name_html}</td>'
            f'<td class="num owner-associate-col-shared">{shared}</td>'
            f'<td class="owner-associate-col-link">{link_type}</td></tr>'
        )
        mobile_cards.append(_associate_mobile_card(r, n_facilities=n_facilities))

    n_show = len(trs)
    associates_help = _info_button(
        "Related CMS associates",
        (
            "Parties that appear with this PAC on CMS records.\n\n"
            "Shared ownership: co-disclosed ownership-interest parties on "
            "the same nursing home enrollments.\n\n"
            "Co-enrollee: appear together on CMS enrollment or owner rows "
            "without implying affiliate, partner, parent, or subsidiary status.\n\n"
            "CHOW party: buyer or seller counterparties on CMS-reported "
            "ownership-change filings.\n\n"
            "Sources: CMS SNF All Owners; CMS CHOW filings."
        ),
        label="?",
        cls="owner-info-btn owner-info-btn--section owner-associates-info",
    )
    desktop = (
        '<div class="owner-associates-table-wrap">'
        '<table class="owner-associate-table"><thead><tr>'
        '<th class="owner-associate-col-name">Name</th>'
        '<th class="num owner-associate-col-shared" title="Shared nursing homes with this owner">'
        "Shared facilities</th>"
        '<th class="owner-associate-col-link">Relationship</th>'
        "</tr></thead><tbody>"
        + "".join(trs)
        + "</tbody></table></div>"
    )
    dual = _owner_table_dual(
        desktop_html=desktop,
        mobile_html=_owner_mobile_card_list(mobile_cards, "owner-mobile-card-list--associates"),
    )
    return (
        '<div class="owner-associates-block" data-associates-loaded="1">'
        + associates_help
        + '<details class="owner-collapsible owner-associates-collapsible">'
        + _associates_summary_html(
            count_html=f'<span class="owner-associates-count"> · {n_show}</span>',
        )
        + f'<div class="owner-associates-panel" data-associates-panel>{dual}</div>'
        "</details>"
        "</div>"
    )


def render_related_associates_fragment(profile: dict[str, Any]) -> str:
    """API helper: associates table/cards only (no details chrome)."""
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
            f'<tr><td class="owner-associate-col-name">{name_html}</td>'
            f'<td class="num owner-associate-col-shared">{shared}</td>'
            f'<td class="owner-associate-col-link">{link_type}</td></tr>'
        )
        mobile_cards.append(_associate_mobile_card(r, n_facilities=n_facilities))
    desktop = (
        '<div class="owner-associates-table-wrap">'
        '<table class="owner-associate-table"><thead><tr>'
        '<th class="owner-associate-col-name">Name</th>'
        '<th class="num owner-associate-col-shared" title="Shared nursing homes with this owner">'
        "Shared facilities</th>"
        '<th class="owner-associate-col-link">Relationship</th>'
        "</tr></thead><tbody>"
        + "".join(trs)
        + "</tbody></table></div>"
    )
    return _owner_table_dual(
        desktop_html=desktop,
        mobile_html=_owner_mobile_card_list(mobile_cards, "owner-mobile-card-list--associates"),
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


def _portfolio_facilities_cta_html(profile: dict[str, Any]) -> str:
    return ""


def _portfolio_snapshot_html(profile: dict[str, Any]) -> str:
    return owner_portfolio_snapshot_html(profile)


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
    label = str(profile.get("facility_section_label") or "").strip()
    if label:
        return html.escape(label)
    raw = str(profile.get("display_name") or "").strip()
    name = html.escape(format_org_display(raw) if raw else "Linked facilities")
    if profile.get("uses_ownership_portfolio_language"):
        return f"{name} — facilities with reported ownership interest"
    return f"{name} — linked facilities"


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
    link_label_raw = provider_raw or legal_raw
    href = (
        html.escape(provider_url(ccn, link_label_raw))
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
    if not bits and "operational" in low and ("managerial" in low or "control" in low):
        bits.append("Operational/managerial control")
    if not bits and "managing employee" in low:
        bits.append("Managing employee")
    return " · ".join(bits)


def _pct_fallback_label(role_raw: str) -> str:
    """CMS often leaves PERCENTAGE OWNERSHIP blank for control roles; show a short label."""
    from ownership.role_classification import (
        ROLE_TEXT_COL,
        classify_owner_record,
        format_role_short_for_classification,
    )

    info = classify_owner_record({ROLE_TEXT_COL: role_raw})
    return format_role_short_for_classification(info) if info.get("primary_role_label") else ""


def _role_ownership_cell(f: dict[str, Any]) -> tuple[str, str]:
    """Role / stake cell; tap opens CMS role + association date."""
    role_raw = str(f.get("role") or "")
    role_text = format_role_text(role_raw) if role_raw else ""
    adate = _fmt_date_mdyy(f.get("association_date"))
    pct_raw = str(f.get("pct") or "").strip()

    from ownership.role_classification import facility_stake_column_label

    short_lbl, long_lbl = facility_stake_column_label(
        role_raw=role_raw,
        role_code=str(f.get("role_code") or ""),
        pct_raw=pct_raw,
    )

    is_role_label = not short_lbl.endswith("%")
    if is_role_label:
        pct_label_raw = long_lbl if long_lbl != "—" else ""
        pct_display = html.escape(short_lbl)
        pct_title = html.escape(long_lbl) if long_lbl != "—" else pct_display
        pct = ""
    else:
        pct = _format_ownership_pct_value(pct_raw) if pct_raw else ""
        pct_label_raw = _format_own_pct_label(pct) if pct else long_lbl
        pct_display = html.escape(short_lbl)
        pct_title = html.escape(pct_label_raw) if pct_label_raw else pct_display

    has_detail = bool(role_text) or (adate and adate != "—") or pct
    since_html = _role_since_html(f.get("association_date"))

    if has_detail:
        attrs = _facility_ownership_modal_attr_str(
            f, pct_label=pct_label_raw if pct else long_lbl
        )
        title_attr = (
            f' title="{pct_title}"' if pct_title and pct_title != pct_display else ""
        )
        pct_part = (
            f'<button type="button" class="owner-role-pct-btn" {attrs}{title_attr} '
            f'aria-label="Ownership details: {pct_title}">'
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


def _facility_state_code(f: dict[str, Any]) -> str:
    return str(f.get("state") or "").strip().upper()[:2]


def _portfolio_state_codes(fac_list: list[dict[str, Any]]) -> list[str]:
    return sorted({_facility_state_code(f) for f in fac_list if _facility_state_code(f)})


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
        st_code = _facility_state_code(f)
        rows.append(
            f'<tr data-search="{html.escape(search)}" data-state="{html.escape(st_code)}">'
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
    fac_list: list[dict[str, Any]],
    profile: dict[str, Any],
    *,
    pac: str = "",
    force_full_table: bool = False,
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
        '<th data-sort="role" class="sortable num owner-col-role" title="Role or ownership percentage">'
        'Role / stake <span class="sort-icon"></span></th>'
        '<th data-sort="hprd" class="sortable num owner-col-hprd" title="Facility-reported PBJ total nurse HPRD">HPRD <span class="sort-icon"></span></th>'
        '<th data-sort="stars" class="sortable num owner-col-ratings">'
        'Ratings <span class="sort-icon"></span></th>'
        '<th data-sort="census" class="sortable num owner-col-census">Census <span class="sort-icon"></span></th>'
        '<th class="owner-col-flags">Flags</th>'
    )
    filter_html = ""
    mobile_toolbar = ""
    state_codes = _portfolio_state_codes(fac_list)
    state_filter_html = ""
    if len(state_codes) > 1:
        opts = ['<option value="">All states</option>']
        for code in state_codes:
            label = code
            try:
                from app import STATE_CODE_TO_NAME

                label = STATE_CODE_TO_NAME.get(code, code)
            except Exception:
                pass
            opts.append(
                f'<option value="{html.escape(code)}">{html.escape(label)}</option>'
            )
        state_filter_html = (
            f'<select id="ownerFacilitiesStateFilter" class="owner-table-state-filter" '
            f'aria-label="Filter by state">{"".join(opts)}</select>'
        )
    if n >= FACILITIES_FILTER_MIN:
        filter_html = (
            '<div class="owner-facilities-header-actions">'
            f'{state_filter_html}'
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
    title = _facilities_portfolio_title(profile)
    heading = (
        f'<div class="owner-facilities-header">'
        f'<h2 class="section-header owner-facilities-heading">{title}</h2>'
        f"{filter_html}</div>"
    )
    preview_n = len(fac_list) if force_full_table else min(FACILITIES_DESKTOP_PREVIEW, n)
    fac_slice = fac_list if force_full_table else fac_list[:preview_n]
    rest_count = 0 if force_full_table else max(0, n - preview_n)
    owner_rows = _facilities_owner_rows(fac_slice)
    mobile_cards = [_facility_mobile_card(f) for f in fac_slice]
    pac_raw = str(profile.get("associate_id") or pac or "").strip()

    show_more_btn = ""
    if rest_count and pac_raw:
        show_more_btn = (
            f'<button type="button" class="owner-facilities-show-more" '
            f'id="ownerFacilitiesShowMore" data-total="{n}" data-shown="{preview_n}" '
            f'data-batch="{FACILITIES_SHOW_MORE_BATCH}" '
            f'data-facilities-url="/owners/api/owner-facilities/{html.escape(pac_raw, quote=True)}">'
            f"Show more</button>"
        )

    mobile_list = (
        '<ul class="owner-mobile-card-list owner-mobile-card-list--facilities" '
        f'role="list" id="ownerFacilitiesMobileList" data-preview="{preview_n}">'
        + "".join(mobile_cards)
        + "</ul>"
    )

    def _desk(rows: list[str]) -> str:
        return (
            '<div class="chow-table-scroll chow-table-scroll--touch owner-facilities-scroll">'
            '<table class="chow-table owner-facilities-table chow-table--compact-sm" id="ownerFacilitiesTable">'
            f"<thead><tr>{thead}</tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table></div>"
        )

    footer = ""
    if rest_count:
        footer = (
            f'<p class="owner-table-footer" id="ownerFacilitiesFooter">'
            f'<span id="ownerFacilitiesShownLabel">Showing {preview_n} of {n}</span>'
            f"{show_more_btn}</p>"
        )
    desktop = _desk(owner_rows)
    dual = _owner_table_dual(
        desktop_html=desktop,
        mobile_html=mobile_toolbar + mobile_list,
    )
    return (
        '<section class="owner-facilities-section" id="ownerFacilitiesPortfolio" '
        'aria-label="Facilities in this portfolio">'
        + heading
        + dual
        + footer
        + _facilities_match_note(profile)
        + "</section>"
    )


def render_owner_facilities_batch_html(
    profile: dict[str, Any], *, offset: int = 0, limit: int = 50
) -> dict[str, Any]:
    """HTML row/card batch for inline Show more (sqlite-backed profile facilities)."""
    fac_list = list(profile.get("facilities") or [])
    n = len(fac_list)
    start = max(0, int(offset))
    take = max(1, min(200, int(limit)))
    batch = fac_list[start : start + take]
    next_offset = start + len(batch)
    return {
        "total": n,
        "offset": start,
        "next_offset": next_offset,
        "done": next_offset >= n,
        "rows_html": "".join(_facilities_owner_rows(batch)),
        "cards_html": "".join(_facility_mobile_card(f) for f in batch),
        "count": len(batch),
    }


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
    force_full_table: bool = False,
) -> str:
    owner_primary_both = kind == "both" and profile.get("both_primary") == "owner_control"
    if kind == "owner_control" or owner_primary_both:
        html_out = _owner_facilities_table_html(
            facilities,
            profile,
            pac=str(profile.get("associate_id") or ""),
            force_full_table=force_full_table,
        )
        if owner_primary_both and not skip_control_parties:
            cps = profile.get("control_parties") or []
            if cps:
                html_out += _control_parties_html(cps, ow_label)
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
                force_full_table=force_full_table,
            )
        else:
            thead_en = (
                "<th>Facility</th><th>Enrollment ID</th><th>Location</th><th>City</th>"
            )
            html_out = _table_with_preview(
                "Linked facilities",
                thead_en,
                _facilities_enrollment_rows(facilities),
                PREVIEW_FACILITIES if not force_full_table else max(len(facilities), 1),
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
    if kind != "both":
        return ""

    # Owner-primary both: enrollment side is secondary (not the main facility table).
    if profile.get("both_primary") == "owner_control":
        en = profile.get("enrollment_section") or {}
        fac_list = en.get("facilities") or []
        if not fac_list:
            return ""
        ps = en.get("portfolio_summary") or {}
        extra = ""
        n_en = int(ps.get("n_facilities") or len(fac_list) or 0)
        if n_en:
            extra = (
                f'<p class="pbj-meta-line">Also appears as enrollment entity on '
                f"<strong>{n_en}</strong> facilit{'y' if n_en == 1 else 'ies'}.</p>"
            )
        thead_en = (
            "<th>Facility</th><th>Enrollment ID</th><th>Location</th><th>City</th>"
        )
        block = _table_with_preview(
            "Also linked as enrollment entity",
            thead_en,
            _facilities_enrollment_rows(fac_list),
            PREVIEW_FACILITIES,
            "enrollments",
            mobile_cards=[_enrollment_facility_mobile_card(f) for f in fac_list],
            mobile_list_class="owner-mobile-card-list--facilities",
        )
        return extra + block

    if not profile.get("owner_control_section"):
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
                f'<a class="owner-tx-facility" href="{html.escape(provider_url(ccn, fac_raw))}" '
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
        help="Print only the Associated Owners section HTML",
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
