"""SFF / SFF Candidate explainers and entity-page metric cards (CMS + PBJ320 /sff)."""
from __future__ import annotations

import html
from typing import Any

PBJ_SFF_URL = "https://www.pbj320.com/sff"
PBJ_SFF_LINK_LABEL = "PBJ320 Special Focus Facility List"

# Verified from: CMS SFF program materials; PBJ320 /sff page copy.
SFF_EXPLAINERS: dict[str, dict[str, Any]] = {
    "sff": {
        "title": "Special Focus Facilities (SFF)",
        "paragraphs": [
            "CMS designates nursing homes with a history of serious quality problems as "
            "Special Focus Facilities. They receive enhanced surveys and oversight until "
            "they graduate or exit the program.",
        ],
        "pbj_link_label": PBJ_SFF_LINK_LABEL,
    },
    "sffc": {
        "title": "SFF Candidates",
        "paragraphs": [
            "Nursing homes CMS monitors for potential Special Focus Facility designation, "
            "typically based on sustained poor survey performance.",
        ],
        "pbj_link_label": PBJ_SFF_LINK_LABEL,
    },
}


def sff_explainer_body(kind: str) -> str:
    """Plain-text body for legacy data-info-body (paragraphs joined)."""
    spec = SFF_EXPLAINERS.get(kind) or {}
    return "\n\n".join(str(p) for p in (spec.get("paragraphs") or []) if p)


def sff_flag_explainer_tuple(kind: str) -> tuple[str, str]:
    """Short title + body for owner portfolio flag badges."""
    spec = SFF_EXPLAINERS.get(kind) or {}
    title = str(spec.get("title") or "SFF")
    body = sff_explainer_body(kind)
    return title, body or title


def sff_info_button_html(kind: str, *, label: str = "?") -> str:
    """Info button opening the shared owner info modal (data-info-format=sff)."""
    spec = SFF_EXPLAINERS.get(kind)
    if not spec:
        return ""
    title = str(spec.get("title") or "SFF")
    body = sff_explainer_body(kind)
    pbj_label = str(spec.get("pbj_link_label") or PBJ_SFF_LINK_LABEL)
    return (
        f'<button type="button" class="owner-info-btn" data-owner-info '
        f'data-info-format="sff" '
        f'data-info-title="{html.escape(title, quote=True)}" '
        f'data-info-body="{html.escape(body, quote=True)}" '
        f'data-info-link-url="{html.escape(PBJ_SFF_URL, quote=True)}" '
        f'data-info-link-label="{html.escape(pbj_label, quote=True)}" '
        f'aria-label="What is {html.escape(title, quote=True)}?">'
        f"{html.escape(label)}</button>"
    )


def entity_risk_metric_card_html(
    label: str,
    value: str,
    explainer_kind: str,
    *,
    tone: str = "",
) -> str:
    """Metric card for entity high-risk grid with SFF-style info modal."""
    tone_cls = f" entity-risk-metric-card--{tone}" if tone else ""
    info = sff_info_button_html(explainer_kind) if explainer_kind in SFF_EXPLAINERS else ""
    return (
        f'<div class="entity-risk-metric-card{tone_cls}">'
        f'<div class="entity-risk-metric-label">{html.escape(label)}</div>'
        f'<div class="entity-risk-metric-value-row">'
        f'<div class="entity-risk-metric-value">{html.escape(value)}</div>'
        f"{info}"
        "</div></div>"
    )


def entity_high_risk_metrics_section_html(
    entity_name: str,
    *,
    sff_count: int | float | None,
    sff_cand_count: int | float | None,
    one_star_count: int | None,
    abuse_count: int | float | None,
    high_risk_tooltip: str,
) -> str:
    """High-risk facility summary grid with SFF / candidate info modals."""
    sff_val = str(int(sff_count)) if sff_count is not None else "—"
    cand_val = str(int(sff_cand_count)) if sff_cand_count is not None else "—"
    one_star_val = str(int(one_star_count)) if one_star_count is not None else "—"
    abuse_val = str(int(abuse_count)) if abuse_count is not None else "—"

    cards = [
        entity_risk_metric_card_html(
            "Special Focus Facilities (SFFs)",
            sff_val,
            "sff",
            tone="warn" if sff_count and float(sff_count) > 0 else "",
        ),
        entity_risk_metric_card_html(
            "SFF Candidates",
            cand_val,
            "sffc",
            tone="warn" if sff_cand_count and float(sff_cand_count) > 0 else "",
        ),
        (
            '<div class="entity-risk-metric-card">'
            '<div class="entity-risk-metric-label">1-Star Overall</div>'
            f'<div class="entity-risk-metric-value-row">'
            f'<div class="entity-risk-metric-value">{html.escape(one_star_val)}</div>'
            "</div></div>"
        ),
        (
            '<div class="entity-risk-metric-card">'
            '<div class="entity-risk-metric-label">Cited for Abuse</div>'
            f'<div class="entity-risk-metric-value-row">'
            f'<div class="entity-risk-metric-value">{html.escape(abuse_val)}</div>'
            "</div></div>"
        ),
    ]
    return (
        f'<section class="entity-high-risk-metrics" aria-labelledby="entityHighRiskHeading">'
        f'<div class="section-header" id="entityHighRiskHeading">'
        f'<span class="pbj-high-risk-help-wrap entity-section-tooltip-wrap">'
        f'<span class="pbj-high-risk-help">High-Risk Facilities</span>'
        f'<span class="pbj-high-risk-tooltip entity-section-tooltip" role="tooltip">'
        f"{html.escape(high_risk_tooltip)}</span></span>"
        f'<span class="pbj-section-header-entity-name"> – {html.escape(entity_name)}</span>'
        "</div>"
        f'<div class="entity-high-risk-metrics-grid" role="list">'
        f"{''.join(cards)}"
        "</div></section>"
    )
