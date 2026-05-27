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
    """FEC contributions panel + methodology (only CT/NY public ownership profiles)."""
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
        <div class="owner-fec-heading-row">
          <h2 class="section-header owner-fec-heading" id="ownerFecHeading">
            FEC political contributions
          </h2>
          <span class="owner-fec-beta" title="Beta tool — verify each filing on FEC.gov">Beta</span>
        </div>
        <p class="owner-fec-lead">
          Federal Election Commission records matched to <strong>{title_name}</strong> by name.
          Similar names may appear; open each <span class="owner-fec-lead-k">FEC filing</span> link to confirm on FEC.gov.
        </p>
        <button type="button" class="owner-fec-load-btn" id="ownerFecLoadBtn"
          aria-controls="ownerFecPanel" aria-expanded="false">
          View {title_name} FEC contributions
        </button>
        <div id="ownerFecPanel" class="owner-fec-panel" hidden role="region"
          aria-label="FEC political contributions for {title_name}"></div>
        <details class="owner-fec-methodology">
          <summary>Sources, methodology &amp; disclaimers</summary>
          <div class="owner-fec-methodology-body">
            <p class="owner-fec-disclaimer-block">
              <strong>Disclaimer:</strong> This view displays public FEC and CMS data.
              Committee groupings are based on committee names and filings.
              No ideological classification is assigned.
            </p>
            <p>
              Contributions are queried live from the
              <a href="https://api.open.fec.gov/" target="_blank" rel="noopener">FEC API</a>
              using the owner name on this profile. The FEC uses fuzzy name matching;
              always confirm each filing via the linked FEC.gov record.
            </p>
            <h3>Matching methodology</h3>
            <ol>
              <li>Owner name from CMS SNF All Owners (this profile).</li>
              <li>FEC Schedule A search with name variants (nicknames, order).</li>
              <li>Individual vs organization filters per CMS party type when available.</li>
            </ol>
            <h3>Data sources</h3>
            <ul>
              <li><a href="https://data.cms.gov/provider-characteristics/hospitals-and-other-facilities/skilled-nursing-facility-all-owners/data" target="_blank" rel="noopener">CMS SNF All Owners</a></li>
              <li><a href="https://www.fec.gov/data/receipts/" target="_blank" rel="noopener">FEC individual contributions</a></li>
            </ul>
            <div class="owner-fec-disclaimer-warn">
              <p><strong>Beta:</strong> Matching errors and incomplete data are possible.</p>
              <p><strong>Name matching:</strong> Similar names may appear in results.</p>
              <p><strong>Completeness:</strong> No FEC rows does not prove zero contributions.</p>
            </div>
            <p class="owner-fec-contact">
              Questions:
              <a href="mailto:eric@320insight.com">eric@320insight.com</a>
              · Full search:
              <a href="/owner">Political contributions tool</a>
            </p>
          </div>
        </details>
      </section>
    """
