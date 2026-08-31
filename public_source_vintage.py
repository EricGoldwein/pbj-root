"""Production source-vintage metadata contract for public PBJ320 pages."""

from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parent


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _month_year_from_release_id(release_id: str) -> str:
    parts = (release_id or "").strip().split("-", 1)
    if len(parts) != 2 or len(parts[0]) != 4 or len(parts[1]) != 2:
        return "UNKNOWN"
    try:
        return datetime(int(parts[0]), int(parts[1]), 1).strftime("%B %Y")
    except ValueError:
        return "UNKNOWN"


def _newest_chain_label(ownership_dir: Path) -> str:
    """Return newest CMS Chain Performance vintage by filename date, not filesystem mtime."""
    candidates = list(ownership_dir.glob("Nursing_Home_Chain_Performance_Measures_*.csv"))
    if not candidates:
        return "UNKNOWN"

    month_lookup = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }

    dated: list[tuple[int, int, Path]] = []
    for path in candidates:
        m = re.search(r"([A-Za-z]{3,9})[_\s-]?(\d{4})$", path.stem)
        if not m:
            continue
        mo = month_lookup.get(m.group(1).lower()[:3])
        if mo:
            dated.append((int(m.group(2)), mo, path))

    if not dated:
        return "UNKNOWN"

    year, mo, _ = max(dated, key=lambda row: (row[0], row[1]))
    return datetime(year, mo, 1).strftime("%B %Y")


def _provider_info_vintage(app_root: Path | None = None) -> dict[str, Any]:
    root = app_root or APP_ROOT
    norm_dir = root / "provider_info"
    norms = sorted(norm_dir.glob("ProviderInfoNorm_*.csv"))
    if not norms:
        return {
            "source_id": "cms.provider_info",
            "display_name": "Provider Information",
            "release_id": "UNKNOWN",
            "source_vintage": "UNKNOWN",
            "official_publication_date": "—",
            "processing_modified_date": "—",
            "cadence": "monthly",
            "publication_class": "governed_release",
            "used_in": ["provider pages", "search index", "state aggregates", "ownership crosswalk"],
            "status": "UNKNOWN",
        }
    newest = max(norms, key=lambda p: p.name)
    m = re.search(r"ProviderInfoNorm_(\d{4})_(\d{2})", newest.name)
    release_id = f"{m.group(1)}-{m.group(2)}" if m else "UNKNOWN"
    vintage = _month_year_from_release_id(release_id)
    return {
        "source_id": "cms.provider_info",
        "display_name": "Provider Information",
        "release_id": release_id,
        "source_vintage": vintage,
        "official_publication_date": "—",
        "processing_modified_date": vintage if vintage != "UNKNOWN" else "—",
        "cadence": "monthly",
        "source_url": "https://data.cms.gov/provider-data/dataset/4pq5-n9py",
        "publication_class": "governed_release",
        "used_in": ["provider pages", "search index", "state aggregates", "ownership crosswalk"],
        "status": "CURRENT",
    }


def vintage_rows_by_source_id(app_root: Path | None = None) -> dict[str, dict[str, Any]]:
    return {str(row.get("source_id") or ""): row for row in build_public_source_vintages(app_root)}


def source_vintage_label(source_id: str, app_root: Path | None = None) -> str:
    row = vintage_rows_by_source_id(app_root).get(source_id) or {}
    label = str(row.get("source_vintage") or "").strip()
    return label if label and label != "UNKNOWN" else "—"


def build_public_source_vintages(app_root: Path | None = None) -> list[dict[str, Any]]:
    """Build production metadata rows from on-disk pbj-root artifacts."""
    root = app_root or APP_ROOT
    rows: list[dict[str, Any]] = []

    quarter = _read_json(root / "latest_quarter_data.json")
    q_display = str(quarter.get("quarter_display") or "UNKNOWN")
    rows.append(
        {
            "source_id": "cms.pbj_nurse_staffing",
            "display_name": "PBJ nurse staffing",
            "release_id": str(quarter.get("quarter") or "UNKNOWN"),
            "source_vintage": q_display,
            "official_publication_date": "—",
            "processing_modified_date": q_display,
            "cadence": "quarterly",
            "source_url": "https://data.cms.gov/quality-of-care/nursing-home-payroll-based-journal-daily-nurse-staffing",
            "publication_class": "quarterly_metrics",
            "used_in": ["facility HPRD", "state pages", "compliance evidence", "provider indexes"],
            "status": "CURRENT" if q_display != "UNKNOWN" else "UNKNOWN",
        }
    )

    rows.append(_provider_info_vintage(root))

    ownership_policy = _read_json(root / "ownership" / "ownership_release_policy.json")
    active_date = str(ownership_policy.get("active_release_date") or "UNKNOWN")
    active_release = (ownership_policy.get("releases") or {}).get(active_date) or {}
    pbj_period = str(active_release.get("pbj_period") or "UNKNOWN")
    rows.append(
        {
            "source_id": "cms.snf_ownership_pair",
            "display_name": "SNF ownership",
            "release_id": active_date,
            "source_vintage": active_date,
            "official_publication_date": active_date if active_date != "UNKNOWN" else "—",
            "processing_modified_date": active_date if active_date != "UNKNOWN" else "—",
            "cadence": "monthly_pair",
            "source_url": "https://data.cms.gov/provider-characteristics/hospitals-and-other-facilities/skilled-nursing-facility-all-owners",
            "source_urls": [
                {"label": "Owners", "url": "https://data.cms.gov/provider-characteristics/hospitals-and-other-facilities/skilled-nursing-facility-all-owners"},
                {"label": "Enrollments", "url": "https://data.cms.gov/provider-characteristics/hospitals-and-other-facilities/skilled-nursing-facility-enrollments"},
            ],
            "publication_class": "paired_release",
            "used_in": ["owner profiles", "CCN bridge", "entity pages"],
            "status": "CURRENT" if active_date != "UNKNOWN" else "UNKNOWN",
            "notes": f"PBJ quarter context: {pbj_period}",
        }
    )

    sff_release = _read_json(root / "data_sources" / "cms" / "sff" / "current_release.json")
    sff_id = str(sff_release.get("source_release") or "UNKNOWN")
    rows.append(
        {
            "source_id": "cms.sff_pdf_list",
            "display_name": "SFF / Candidate list",
            "release_id": sff_id,
            "source_vintage": _month_year_from_release_id(sff_id),
            "official_publication_date": "—",
            "processing_modified_date": _month_year_from_release_id(sff_id),
            "cadence": "posting_cycle",
            "source_url": str(sff_release.get("source_url") or "").strip()
            or "https://www.cms.gov/medicare/health-safety-standards/certification-compliance/special-focus-facility-initiative/sff-posting-candidate-list",
            "publication_class": "reference_posting",
            "used_in": ["SFF pages", "search index", "entity chain counts"],
            "status": "CURRENT" if sff_id != "UNKNOWN" else "UNKNOWN",
            "notes": "Authoritative SFF source; Provider Information Special Focus Status may lag.",
        }
    )

    chain_label = _newest_chain_label(root / "ownership")
    rows.append(
        {
            "source_id": "cms.chain_performance",
            "display_name": "Chain Performance",
            "release_id": chain_label,
            "source_vintage": chain_label,
            "official_publication_date": "—",
            "processing_modified_date": chain_label,
            "cadence": "monthly",
            "source_url": "https://data.cms.gov/quality-of-care/nursing-home-chain-performance-measures/",
            "publication_class": "reference_csv",
            "used_in": ["entity pages", "search index"],
            "status": "CURRENT" if chain_label != "UNKNOWN" else "UNKNOWN",
        }
    )

    rows.append(
        {
            "source_id": "cms.macpac_state_staffing",
            "display_name": "State staffing policies",
            "release_id": "2022-03",
            "source_vintage": "March 2022 compendium",
            "official_publication_date": "March 2022",
            "processing_modified_date": "March 2022",
            "cadence": "reference",
            "source_url": "https://www.macpac.gov/publication/state-policies-related-to-nursing-facility-staffing/",
            "publication_class": "static_reference",
            "used_in": ["state policy context", "NY/CT threshold references"],
            "status": "CURRENT",
            "notes": "Static reference; not stale merely because vintage is old.",
        }
    )

    rows.append(
        {
            "source_id": "fec.contributions",
            "display_name": "Political contributions",
            "release_id": "rolling",
            "source_vintage": "Rolling / current",
            "official_publication_date": "—",
            "processing_modified_date": "—",
            "cadence": "rolling",
            "source_url": "https://www.fec.gov/",
            "publication_class": "rolling_external",
            "used_in": ["owner profile political contributions"],
            "status": "CURRENT",
        }
    )

    return rows


def render_data_sources_vintage_table_html(rows: list[dict[str, Any]]) -> str:
    """Render the current production source contract for /data-sources."""
    table_rows = []
    mobile_cards = []

    for row in rows:
        dataset = html.escape(str(row.get("display_name") or "?"))
        vintage = html.escape(str(row.get("source_vintage") or "?"))

        source_rows = row.get("source_urls") or []
        source_links = []

        if source_rows:
            for source in source_rows:
                label = html.escape(str(source.get("label") or "Source"))
                url = html.escape(str(source.get("url") or ""), quote=True)
                if url:
                    source_links.append(
                        f'<a href="{url}" target="_blank" rel="noopener">{label}</a>'
                    )
        else:
            url = html.escape(str(row.get("source_url") or ""), quote=True)
            if url:
                label = {
                    "cms.pbj_nurse_staffing": "CMS",
                    "cms.provider_info": "CMS",
                    "cms.sff_pdf_list": "CMS",
                    "cms.chain_performance": "CMS",
                    "cms.macpac_state_staffing": "MACPAC",
                    "fec.contributions": "FEC",
                }.get(str(row.get("source_id") or ""), "Source")

                source_links.append(
                    f'<a href="{url}" target="_blank" rel="noopener">{label}</a>'
                )

        source_html = " &middot; ".join(source_links) or "?"

        table_rows.append(
            "<tr>"
            f"<td>{dataset}</td>"
            f"<td>{vintage}</td>"
            f"<td>{source_html}</td>"
            "</tr>"
        )
        mobile_cards.append(
            '<article class="source-vintage-card">'
            f'<h3 class="source-vintage-card-title">{dataset}</h3>'
            '<div class="source-vintage-card-meta">'
            f'<span class="source-vintage-card-date">{vintage}</span>'
            '<span class="source-vintage-card-sep" aria-hidden="true">&middot;</span>'
            f'<span class="source-vintage-card-source">{source_html}</span>'
            "</div>"
            "</article>"
        )

    out = [
        '<div class="source-vintage-table-wrap">',
        '<table class="meta-table source-vintage-table">',
        "<thead><tr>"
        "<th>Source</th>"
        "<th>Current data</th>"
        "<th>Official source</th>"
        "</tr></thead>",
        "<tbody>",
        *table_rows,
        "</tbody></table>",
        "</div>",
        '<div class="source-vintage-mobile-list" aria-label="Current data sources">',
        *mobile_cards,
        "</div>",
    ]
    return "\n".join(out)


def _page_last_updated_label(rows: list[dict[str, Any]]) -> str:
    """Newest dated governed/public source represented on the page."""
    dated: list[tuple[int, int]] = []

    for row in rows:
        release_id = str(row.get("release_id") or "").strip()

        match = re.match(r"^(\d{4})-(\d{2})(?:-\d{2})?$", release_id)
        if match:
            dated.append((int(match.group(1)), int(match.group(2))))
            continue

        match = re.match(r"^CY(\d{4})Q([1-4])$", release_id, re.IGNORECASE)
        if match:
            year = int(match.group(1))
            quarter = int(match.group(2))
            dated.append((year, quarter * 3))

    if not dated:
        return "?"

    year, month = max(dated)
    return datetime(year, month, 1).strftime("%B %Y")

def inject_data_sources_vintage_html(html_content: str, app_root: Path | None = None) -> str:
    rows = build_public_source_vintages(app_root)
    table = render_data_sources_vintage_table_html(rows)
    html_content = html_content.replace("__PUBLIC_SOURCE_VINTAGE_TABLE__", table)
    html_content = html_content.replace(
        "__PAGE_LAST_UPDATED__",
        _page_last_updated_label(rows),
    )
    return html_content
