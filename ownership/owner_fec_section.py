"""Inline FEC political contributions block for /owners/<pac> (CT/NY public profiles)."""
from __future__ import annotations

import html
from typing import Any

from ownership.beta_gate import profile_has_public_state
from ownership.display_format import format_org_display

_FEC_HELP_TITLE = "How FEC matching works"
_FEC_HELP_BODY = (
    "This panel queries the FEC API using the owner name on this CMS profile. "
    "When CMS lists individual vs organization, that type filters results.\n\n"
    "Similar names can appear in FEC data—open each filing on FEC.gov before treating "
    "a row as this person or entity.\n\n"
    "No rows here does not prove zero lifetime contributions. "
    "Use the full political contributions search at /owner for broader name experiments."
)


def _fec_owner_type(profile: dict[str, Any]) -> str:
    ot = str(profile.get("owner_type") or "").lower()
    if "individual" in ot or ot == "i":
        return "INDIVIDUAL"
    return "ORGANIZATION"


def _fec_search_name(profile: dict[str, Any]) -> str:
    return format_org_display(str(profile.get("display_name") or "").strip()) or "Organization"


def render_owner_fec_contributions_section(profile: dict[str, Any]) -> str:
    """FEC contributions panel (only CT/NY public ownership profiles)."""
    if not profile_has_public_state(profile):
        return ""

    fec_name = _fec_search_name(profile)
    if not fec_name or fec_name == "Organization":
        return ""

    fec_type = _fec_owner_type(profile)
    title_name = html.escape(fec_name)
    name_attr = html.escape(fec_name, quote=True)
    type_attr = html.escape(fec_type, quote=True)
    help_title = html.escape(_FEC_HELP_TITLE, quote=True)
    help_body = html.escape(_FEC_HELP_BODY, quote=True)

    return f"""
      <section class="owner-fec-section" id="ownerFecContributions"
        data-owner-name="{name_attr}" data-owner-type="{type_attr}"
        aria-labelledby="ownerFecHeading">
        <div class="owner-fec-hub">
          <div class="owner-fec-hub-top">
            <h2 class="section-header owner-fec-heading" id="ownerFecHeading">
              <span class="owner-fec-heading-text owner-fec-heading-text--long">FEC political contributions</span>
              <span class="owner-fec-heading-text owner-fec-heading-text--short">FEC contributions</span>
              <span class="owner-fec-heading-actions">
                <span class="owner-fec-beta">Beta</span>
                <button type="button" class="owner-fec-help-btn" data-owner-info
                  data-info-title="{help_title}" data-info-body="{help_body}">
                  How it works
                </button>
              </span>
            </h2>
          </div>
          <p class="owner-fec-hub-note">
            Name match to <strong>{title_name}</strong> in FEC filings.
            <span class="owner-fec-hub-warn">Similar names may appear—confirm on
            <a href="https://www.fec.gov/data/receipts/" target="_blank" rel="noopener">FEC.gov</a>.</span>
          </p>
          <button type="button" class="owner-fec-load-btn" id="ownerFecLoadBtn"
            aria-controls="ownerFecPanel" aria-expanded="false">
            View {title_name} FEC contributions
          </button>
          <div id="ownerFecPanel" class="owner-fec-panel" hidden role="region"
            aria-label="FEC political contributions for {title_name}"></div>
        </div>
      </section>
    """
