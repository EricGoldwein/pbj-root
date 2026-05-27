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
from utils.seo_utils import owner_page_seo_from_profile
from ownership.display_format import (
    cms_rating_stars_html,
    cms_ratings_stack_html,
    format_cms_star_rating,
    format_org_display,
    format_role_text,
)

PREVIEW_CONTROL_PARTIES = 25
PREVIEW_FACILITIES = 50
FACILITIES_FILTER_MIN = 12

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
        "Flagged for abuse on CMS provider data.",
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


def render_owner_profile_body(profile: dict[str, Any]) -> tuple[str, str, str, str]:
    """Return (body_html, page_title, meta_desc, canonical_path_suffix)."""
    kind = profile.get("profile_kind") or "owner_control"
    name = html.escape(format_org_display(profile.get("display_name") or "Organization"))
    pac = html.escape(profile.get("associate_id") or "")
    owner_type = html.escape(profile.get("owner_type") or "")
    states = profile.get("states") or []
    facilities = profile.get("facilities") or []
    en_label = html.escape(profile.get("enrollment_pac_label") or "Enrollment PAC")
    ow_label = html.escape(profile.get("owner_pac_label") or "Owner PAC")
    page_title, meta_desc, owner_intro_html = owner_page_seo_from_profile(profile)
    states_meta = _states_meta_html(profile)
    states_modal = _states_breakdown_modal_html(profile)

    is_chow_only = bool(profile.get("is_chow_only"))

    pac_meta = _pac_meta_html(profile, kind, pac, en_label, ow_label)

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
        pac_meta=pac_meta,
        kind=kind,
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
      <h2 class="section-header">Related on PBJ320</h2>
      <ul class="chow-future-list">
        <li><a href="/owner">Political contributions search</a> (FEC)</li>
      </ul>
      <p class="pbj-meta-line" style="margin-top:1rem;font-size:0.85rem;color:#94a3b8;">
        <strong>PACs:</strong> {en_label} = facility enrollment (typical buyer/seller in ownership changes).
        {ow_label} = reported owner or control party.
      </p>
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
          <div class="chow-table-scroll owner-states-modal-body">
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
) -> str:
    enrollment_ids = profile.get("enrollment_ids") or []
    parts: list[str] = []
    if kind == "both":
        parts.append(f'<span class="owner-meta-item"><span class="owner-meta-k">PAC</span> {pac}</span>')
    elif kind == "owner_control":
        parts.append(
            f'<span class="owner-meta-item"><span class="owner-meta-k">{ow_label}</span> {pac}</span>'
        )
    else:
        parts.append(
            f'<span class="owner-meta-item"><span class="owner-meta-k">{en_label}</span> {pac}</span>'
        )
    if enrollment_ids:
        ids = ", ".join(html.escape(e) for e in enrollment_ids[:4])
        if len(enrollment_ids) > 4:
            ids += f" (+{len(enrollment_ids) - 4})"
        parts.append(
            f'<span class="owner-meta-item"><span class="owner-meta-k">Enrollment ID</span> {ids}</span>'
        )
    return f'<span class="owner-profile-pac-meta">{" · ".join(parts)}</span>'


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
            "may not appear in the current SNF All Owners enrollment or owner PAC file."
        )
    elif kind == "owner_control":
        return ""
    else:
        return ""
    return f'<div class="owner-scope-note" role="status">{text}</div>'



def _snf_owners_source_line(profile: dict[str, Any]) -> str:
    from ownership.owner_profile import snf_owners_source_citation

    return str(profile.get("ownership_source") or snf_owners_source_citation())


def _owner_page_help_body(profile: dict[str, Any], kind: str) -> str:
    """Page-level methodology for the ownership profile ? control."""
    n = len(profile.get("facilities") or [])
    snf_src = _snf_owners_source_line(profile)
    kind_line = {
        "owner_control": (
            f"Owner/control party with {n} linked nursing homes in {snf_src}."
        ),
        "enrollment": (
            f"CMS enrollment entity with {n} linked facility record(s), owners, and control parties."
        ),
        "both": (
            f"Enrollment and owner/control PAC with {n} linked facilities in CMS data."
        ),
        "chow_only": (
            f"Party in CMS ownership-change records with {n} linked facility reference(s); "
            f"may be absent from {snf_src}."
        ),
    }.get(kind, f"CMS ownership profile with {n} linked record(s).")
    from ownership.owner_portfolio_metrics import PORTFOLIO_METHODOLOGY_SUMMARY

    return (
        f"{kind_line}\n\n"
        "Facility table: reported ownership % and CMS role, PBJ staffing (HPRD), "
        "CMS star ratings, and regulatory flags where data are linked.\n\n"
        f"Portfolio summary metrics: {PORTFOLIO_METHODOLOGY_SUMMARY}\n\n"
        f"Sources: {snf_src}; CMS Payroll-Based Journal (PBJ); "
        "CMS provider data; PBJ320 CHOW index (ownership changes and frequent associates)."
    )


def _owner_profile_header_html(
    profile: dict[str, Any],
    *,
    name: str,
    owner_type: str,
    states_meta: str,
    pac_meta: str,
    kind: str,
) -> str:
    page_help = _info_button(
        "PBJ320 Ownership",
        _owner_page_help_body(profile, kind),
        label="?",
        cls="owner-info-btn owner-info-btn--section owner-page-help",
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
    if pac_meta or page_help:
        header_actions = (
            f'<div class="owner-profile-header-actions">{pac_meta}{page_help}</div>'
        )
    return f"""
      <header class="owner-profile-header owner-profile-header--branded">
        <div class="owner-profile-brand-row">
          <a class="owner-profile-brand" href="/state/connecticut" aria-label="Connecticut PBJ320">
            <img class="owner-profile-brand-icon" src="/pbj_favicon.png" alt="" width="28" height="28" decoding="async">
            <span class="owner-profile-brand-lockup">
              <span class="owner-profile-brand-mark"><span class="owner-profile-brand-pbj">PBJ</span><span class="owner-profile-brand-320">320</span></span>
              <span class="owner-profile-brand-suffix">Ownership</span>
            </span>
          </a>
          {header_actions}
        </div>
        <h1 class="owner-profile-name">{name}</h1>
        {meta_row}
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

    n_show = len(trs)
    associates_help = _info_button(
        "Frequent associates",
        (
            "Parties that appear repeatedly with this owner on CMS records.\n\n"
            "Ownership: co-owners on the same nursing home enrollments in "
            "CMS SNF All Owners (shared enrollment PACs).\n\n"
            "Ownership events: buyer or seller counterparties on CMS-reported ownership "
            "change filings involving this party.\n\n"
            "Sources: CMS SNF All Owners; PBJ320 CHOW index (CMS ownership change filings)."
        ),
        label="?",
        cls="owner-info-btn owner-info-btn--section owner-associates-info",
    )
    table = (
        '<div class="owner-associates-table-wrap">'
        '<table class="owner-associate-table"><thead><tr>'
        '<th class="owner-associate-col-name">Name</th>'
        '<th class="num owner-associate-col-shared" title="Shared nursing homes with this owner">Shared</th>'
        '<th class="owner-associate-col-link">Link</th>'
        "</tr></thead><tbody>"
        + "".join(trs)
        + "</tbody></table></div>"
    )
    return (
        '<details class="owner-collapsible owner-associates-collapsible">'
        f'<summary class="owner-associates-summary">'
        f'<span class="owner-associates-summary-label">Frequent associates · {n_show}</span>'
        f"{associates_help}"
        f"</summary>"
        f"{table}"
        "</details>"
    )


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

    n = ps.get("n_facilities") or 0
    n_matched = ps.get("n_pbj_matched") or 0
    wmean = ps.get("wmean_hprd")
    umean = ps.get("umean_hprd")
    mean_ovr = ps.get("mean_overall_rating")
    n_suggested = ps.get("n_pbj_suggested") or 0

    hprd_val = "—"
    if wmean is not None:
        hprd_val = f"{wmean:.2f}"
    elif umean is not None:
        hprd_val = f"{umean:.2f}"

    ovr_val = "—"
    if mean_ovr is not None:
        ovr_val = f"{mean_ovr:.1f}"

    fac_help = (
        f"{n} facilities in CMS SNF All Owners for this party. "
        f"{n_matched} have a verified PBJ link (enrollment legal name = provider-info legal name)."
    )
    if n_suggested:
        fac_help += f" {n_suggested} use a tentative name match."

    from ownership.owner_portfolio_metrics import (
        PORTFOLIO_HPRD_MAX,
        PORTFOLIO_HPRD_MIN,
        PORTFOLIO_OVERALL_RATING_MAX,
        PORTFOLIO_OVERALL_RATING_MIN,
    )

    ovr_help = (
        f"Mean CMS overall star rating ({PORTFOLIO_OVERALL_RATING_MIN:g}–"
        f"{PORTFOLIO_OVERALL_RATING_MAX:g}), resident-weighted by census (or beds). "
        "Only PBJ-verified facilities; missing or out-of-range values excluded."
    )
    hprd_help = (
        f"Mean total nurse HPRD from PBJ, resident-weighted. Only PBJ-verified facilities. "
        f"Values below {PORTFOLIO_HPRD_MIN:g} or above {PORTFOLIO_HPRD_MAX:g} HPRD are excluded "
        "(CMS PBJ quarterly plausible range)."
    )
    qc_bits: list[str] = []
    if ps.get("n_hprd_outlier_excluded"):
        qc_bits.append(f"{ps['n_hprd_outlier_excluded']} HPRD outlier(s) excluded")
    if ps.get("n_missing_overall_rating"):
        qc_bits.append(f"{ps['n_missing_overall_rating']} missing overall rating")
    if ps.get("n_rating_outlier_excluded"):
        qc_bits.append(f"{ps['n_rating_outlier_excluded']} rating outlier(s) excluded")
    if qc_bits:
        hprd_help += " " + "; ".join(qc_bits) + "."

    return f"""
      <section class="owner-snapshot-section" aria-label="Portfolio summary">
        <div class="owner-portfolio-grid owner-portfolio-grid--3" aria-label="Portfolio summary metrics">
          <div class="owner-snapshot-card owner-snapshot-card--accent">
            <div class="owner-snapshot-label">Facilities {_info_button("Facilities", fac_help)}</div>
            <div class="owner-snapshot-value">{n}</div>
          </div>
          <div class="owner-snapshot-card owner-snapshot-card--warn">
            <div class="owner-snapshot-label">Overall rating {_info_button("Overall rating", ovr_help)}</div>
            <div class="owner-snapshot-value">{html.escape(str(ovr_val))}</div>
          </div>
          <div class="owner-snapshot-card">
            <div class="owner-snapshot-label">Staffing (HPRD) {_info_button("Staffing (HPRD)", hprd_help)}</div>
            <div class="owner-snapshot-value">{html.escape(str(hprd_val))}</div>
          </div>
        </div>
      </section>"""


def _facilities_match_note(profile: dict[str, Any]) -> str:
    ps = profile.get("portfolio_summary") or {}
    n = ps.get("n_facilities") or 0
    verified = ps.get("n_pbj_matched") or 0
    suggested = ps.get("n_pbj_suggested") or 0
    if not n or (verified >= n and not suggested):
        return ""
    if suggested:
        dba_abbr = (
            f'<abbr title="{html.escape(_DBA_ABBR_TITLE, quote=True)}">DBA</abbr>'
        )
        return (
            f'<p class="owner-table-note">{suggested} row(s) use a tentative {dba_abbr} '
            f"or name match ({_ccn_match_badge('name_exact')} / {_ccn_match_badge('fuzzy')}) "
            "— PBJ columns show only for verified legal-name links.</p>"
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
            'title="Approximate name match only—verify on CMS before relying on link" '
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
    return cms_ratings_stack_html(
        f.get("overall_rating"),
        f.get("staffing_rating"),
        f.get("qm_rating"),
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
    return f"{name} — Nursing Home Portfolio"


def _facility_flags_cell(f: dict[str, Any], *, verified: bool) -> str:
    """Regulatory screening badges (SFF, abuse icon, etc.)."""
    if not verified:
        return "—"
    badges: list[str] = []
    sff = str(f.get("sff_status") or f.get("sff") or "").strip()
    sff_up = sff.upper()
    if sff_up == "SFF":
        badges.append(_flag_explainer_button("sff", "SFF", "owner-flag--sff"))
    elif "CANDIDATE" in sff_up:
        badges.append(_flag_explainer_button("sffc", "SFFC", "owner-flag--sffc"))
    if f.get("has_abuse"):
        badges.append(_flag_explainer_button("abuse", "Abuse", "owner-flag--abuse"))
    if not badges:
        return "—"
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
    if provider_esc and not same:
        if href:
            primary_html = (
                f'<a href="{href}" class="owner-facility-primary"{title_attr}>{provider_esc}</a>'
            )
        else:
            primary_html = f'<span class="owner-facility-primary">{provider_esc}</span>'
        sub_parts = [legal_esc]
        if badge:
            sub_parts.append(badge)
        sub_html = f'<div class="owner-facility-sub">{"".join(sub_parts)}</div>'
    else:
        if href:
            primary_html = (
                f'<a href="{href}" class="owner-facility-primary"{title_attr}>{legal_esc}</a>'
            )
        else:
            primary_html = f'<span class="owner-facility-primary">{legal_esc}</span>'
        sub_html = ""

    inner = f"{primary_html}{sub_html}"
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

    pct_display = html.escape(pct) if pct else html.escape(_pct_fallback_label(role_raw) or "—")
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
        st, co = _state_county_cells(f)
        city = html.escape(str(f.get("city") or "").strip() or "")
        city_cell = city or "—"
        names_html, _ = _facility_names_cell(f)
        rows.append(
            f"<tr><td>{names_html}</td>"
            f"<td>{html.escape(f.get('enrollment_id') or '—')}</td>"
            f"<td>{st}</td><td>{co}</td><td>{city_cell}</td></tr>"
        )
    return rows


def _facilities_owner_rows(fac_list: list[dict[str, Any]]) -> list[str]:
    rows = []
    for f in fac_list:
        st, co = _state_county_cells(f)
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
            f'<td class="owner-col-facility" data-sort="{names_sort}">{names_html}</td>'
            f'<td data-sort="{_sort_attr(f.get("state"))}">{st}</td>'
            f'<td class="owner-col-county" data-sort="{_sort_attr(f.get("county"))}">{co}</td>'
            f'<td class="owner-role-cell" data-sort="{role_sort}">{role_html}</td>'
            f'<td class="num" data-sort="{_sort_attr(hprd if verified else "")}">{hprd}</td>'
            f'<td class="num owner-col-ratings" data-sort="{html.escape(stars_sort)}">{stars_html}</td>'
            f'<td class="num owner-col-census" data-sort="{_sort_attr(census if verified else "")}">{census}</td>'
            f'<td class="owner-col-flags" data-sort="">{flags}</td></tr>'
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
        '<th data-sort="state" class="sortable owner-col-state">State <span class="sort-icon"></span></th>'
        '<th data-sort="county" class="sortable owner-col-county">County <span class="sort-icon"></span></th>'
        '<th data-sort="role" class="sortable owner-col-role" title="Percent ownership">'
        '% Own. <span class="sort-icon"></span></th>'
        '<th data-sort="hprd" class="sortable num owner-col-hprd">HPRD <span class="sort-icon"></span></th>'
        '<th data-sort="stars" class="sortable num owner-col-ratings">'
        'Ratings <span class="sort-icon"></span></th>'
        '<th data-sort="census" class="sortable num owner-col-census">Census <span class="sort-icon"></span></th>'
        '<th class="owner-col-flags">Flags</th>'
    )
    filter_html = ""
    if n >= FACILITIES_FILTER_MIN:
        filter_html = (
            '<div class="owner-facilities-header-actions">'
            f'<input type="search" id="ownerFacilitiesFilter" class="owner-table-filter-input" '
            f'placeholder="Filter…" autocomplete="off" '
            f'aria-label="Filter {n} facilities">'
            '<span class="owner-table-filter-count" id="ownerFacilitiesFilterCount" hidden></span>'
            "</div>"
        )
    title = _facilities_portfolio_title(profile)
    heading = (
        f'<div class="owner-facilities-header">'
        f'<h2 class="section-header owner-facilities-heading">{title}</h2>'
        f"{filter_html}</div>"
    )
    table = (
        '<div class="chow-table-scroll owner-facilities-scroll" style="max-height:min(70vh,560px);">'
        '<table class="chow-table owner-facilities-table" id="ownerFacilitiesTable">'
        f"<thead><tr>{thead}</tr></thead><tbody>"
        + "".join(_facilities_owner_rows(fac_list))
        + "</tbody></table></div>"
    )
    tx_html = _ownership_transactions_html(profile, pac, bool(profile.get("is_chow_only")))
    return (
        '<section class="owner-facilities-section">'
        + heading
        + table
        + _facilities_match_note(profile)
        + tx_html
        + "</section>"
    )


def _table_with_preview(
    title: str,
    thead: str,
    all_rows: list[str],
    preview: int,
    entity_label: str,
) -> str:
    n = len(all_rows)
    if n == 0:
        return f'<h2 class="section-header">{title}</h2><p class="pbj-meta-line">No rows.</p>'

    preview_rows = all_rows[:preview]
    rest_rows = all_rows[preview:]
    table = (
        '<div class="chow-table-scroll" style="max-height:480px;">'
        f'<table class="chow-table"><thead><tr>{thead}</tr></thead><tbody>'
        + "".join(preview_rows)
        + "</tbody></table></div>"
    )
    if not rest_rows:
        return f'<h2 class="section-header">{title}</h2>{table}'

    footer = (
        f'<p class="owner-table-footer">{n} {html.escape(entity_label)} · '
        f"Showing {preview} of {n}</p>"
    )
    extra = (
        f'<details class="owner-collapsible"><summary>Show all {n} {html.escape(entity_label)} '
        f"({len(rest_rows)} more)</summary>"
        '<div class="chow-table-scroll">'
        f'<table class="chow-table"><thead><tr>{thead}</tr></thead><tbody>'
        + "".join(all_rows)
        + "</tbody></table></div></details>"
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
    for p in control_parties:
        owner_pac = html.escape(p.get("owner_associate_id") or "—")
        raw_name = p.get("name") or "—"
        pname = html.escape(
            format_org_display(str(raw_name)) if raw_name != "—" else "—"
        )
        ptype = html.escape(p.get("party_type") or "—")
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

    thead = (
        "<th>Name</th><th>Owner/control PAC</th><th>Type</th>"
        "<th>Role(s)</th><th>%</th>"
    )
    intro = (
        f'<p class="owner-control-summary">'
        f"<strong>{n}</strong> reported parties "
        f"({orgs} organizations · {inds} individuals). "
        f"Sorted by ownership % and role. Names link to owner profiles.</p>"
    )
    table_block = _table_with_preview(
        title,
        thead,
        cp_rows,
        PREVIEW_CONTROL_PARTIES,
        "parties",
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
        return _owner_facilities_table_html(
            facilities, profile, pac=str(profile.get("associate_id") or "")
        )

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
                "<th>Facility</th><th>Enrollment ID</th><th>State</th>"
                "<th>County</th><th>City</th>"
            )
            html_out = _table_with_preview(
                "Linked facilities",
                thead_en,
                _facilities_enrollment_rows(facilities),
                PREVIEW_FACILITIES,
                "enrollments",
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
        "<th>Facility</th><th>State</th><th>County</th><th>%</th>"
        "<th>HPRD</th><th>Ratings</th><th>Census</th><th>Flags</th>"
    )
    block = _table_with_preview(
        "Also reported as owner / control elsewhere",
        thead,
        _facilities_owner_rows(fac_list),
        PREVIEW_FACILITIES,
        "facilities",
    )
    return extra + block


def _ownership_transactions_html(profile: dict[str, Any], pac: str, is_chow_only: bool) -> str:
    chow_rows = profile.get("chow_transactions") or []
    if not chow_rows:
        return ""

    tx_rows = []
    for rec in chow_rows[:25]:
        eff = html.escape(str(rec.get("effective_date") or "—"))
        ccn = str(rec.get("ccn") or "").strip().zfill(6)[-6:]
        fac = html.escape(rec.get("facility_display_name") or rec.get("buyer_dba_name") or "—")
        if ccn:
            fac_cell = (
                f'<a href="/provider/{html.escape(ccn)}" '
                f'title="View staffing data for {html.escape(fac, quote=True)}">{fac}</a>'
            )
        else:
            fac_cell = fac
        buyer = html.escape(rec.get("buyer_org_name") or "—")
        seller = html.escape(rec.get("seller_org_name") or "—")
        role = html.escape(rec.get("chow_role") or "—")
        tx_rows.append(
            f"<tr><td>{eff}</td><td>{fac_cell}</td><td>{buyer}</td>"
            f"<td>{seller}</td><td>{role}</td></tr>"
        )

    inner = (
        '<div class="chow-table-scroll" style="max-height:360px;">'
        '<table class="chow-table"><thead><tr>'
        "<th>Effective</th><th>Facility</th><th>Buyer</th><th>Seller</th><th>Role</th>"
        "</tr></thead><tbody>"
        + "".join(tx_rows)
        + "</tbody></table></div>"
    )
    if is_chow_only:
        return (
            '<h2 class="section-header">Ownership transactions</h2>'
            + inner
        )

    return (
        f'<details class="owner-collapsible owner-collapsible--txns">'
        f'<summary>Ownership transactions · {len(chow_rows)} in CMS data'
        f"{'s' if len(chow_rows) != 1 else ''}</summary>"
        + inner
        + "</details>"
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
