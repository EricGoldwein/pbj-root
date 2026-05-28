"""Inline FEC political contributions block for /owners/<pac> (CT/NY public profiles)."""
from __future__ import annotations

import html
from typing import Any

from ownership.beta_gate import profile_has_public_state
from ownership.display_format import format_org_display


def _fec_owner_type(profile: dict[str, Any]) -> str:
    ot = str(profile.get("owner_type") or "").lower()
    if "individual" in ot or ot == "i":
        return "INDIVIDUAL"
    return "ORGANIZATION"


def _fec_search_name(profile: dict[str, Any]) -> str:
    return format_org_display(str(profile.get("display_name") or "").strip()) or "Organization"


def render_owner_fec_contributions_section(profile: dict[str, Any]) -> str:
    """FEC contributions panel + short methodology (only CT/NY public ownership profiles)."""
    if not profile_has_public_state(profile):
        return ""

    fec_name = _fec_search_name(profile)
    if not fec_name or fec_name == "Organization":
        return ""

    fec_type = _fec_owner_type(profile)
    title_name = html.escape(fec_name)
    name_attr = html.escape(fec_name, quote=True)
    type_attr = html.escape(fec_type, quote=True)

    return f"""
      <section class="owner-fec-section" id="ownerFecContributions"
        data-owner-name="{name_attr}" data-owner-type="{type_attr}"
        aria-labelledby="ownerFecHeading">
        <h2 class="section-header owner-fec-heading" id="ownerFecHeading">
          FEC political contributions
          <span class="owner-fec-beta" title="Beta — verify each filing on FEC.gov">Beta</span>
        </h2>
        <p class="owner-fec-lead">
          FEC records matched to <strong>{title_name}</strong> by name.
          Similar names may appear—confirm each filing on
          <a href="https://www.fec.gov/data/receipts/" target="_blank" rel="noopener">FEC.gov</a>.
        </p>
        <button type="button" class="owner-fec-load-btn" id="ownerFecLoadBtn"
          aria-controls="ownerFecPanel" aria-expanded="false">
          View {title_name} FEC contributions
        </button>
        <div id="ownerFecPanel" class="owner-fec-panel" hidden role="region"
          aria-label="FEC political contributions for {title_name}"></div>
        <details class="owner-fec-methodology">
          <summary class="owner-fec-methodology-summary">
            <span class="owner-fec-methodology-summary-text">How this search works</span>
            <span class="owner-fec-methodology-caret" aria-hidden="true">▾</span>
          </summary>
          <div class="owner-fec-methodology-body">
            <p>Live query against the
              <a href="https://api.open.fec.gov/" target="_blank" rel="noopener">FEC API</a>
              using the owner name on this profile. CMS type (individual vs organization) filters
              results when known. Similar names can appear—verify each filing on FEC.gov. No rows
              here does not prove zero lifetime contributions.</p>
            <p class="owner-fec-methodology-links">
              <a href="https://data.cms.gov/provider-characteristics/hospitals-and-other-facilities/skilled-nursing-facility-all-owners/data" target="_blank" rel="noopener">CMS SNF All Owners</a>
              ·
              <a href="https://www.fec.gov/data/receipts/" target="_blank" rel="noopener">FEC receipts</a>
              ·
              <a href="/owner">Full political contributions search</a>
            </p>
          </div>
        </details>
      </section>
    """
