"""
Top nursing home owner contributors page — /owners/top.
NOT public: returns 404 unless ENABLE_TOP_PAGE=1 is set. Needs donor/FEC data/top_nursing_home_contributors_2026.csv
(generate with: python -m donor.top_nursing_home_contributors_2026 --top 500).
"""

import os
from pathlib import Path

from flask import abort, render_template, send_file


def _fec_name_display(raw: str) -> str:
    """'LANDA, BENJAMIN' -> 'Benjamin Landa'; else title-case."""
    if not raw or not isinstance(raw, str):
        return raw or ""
    s = raw.strip()
    if "," in s:
        parts = [p.strip() for p in s.split(",", 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            return f"{parts[1].title()} {parts[0].title()}"
    return s.title()


def _title_case_facility(name: str) -> str:
    """First word cap; the/and/at/of lowercase; Post-Acute style cap."""
    if not name or not isinstance(name, str):
        return name or ""
    small = {"the", "and", "at", "of", "a", "an", "in", "on", "for", "to", "with"}
    words = name.split()
    out = []
    for i, w in enumerate(words):
        w = w.strip()
        if not w:
            continue
        if "-" in w:
            out.append("-".join(p.capitalize() for p in w.split("-")))
        elif i == 0 or w.lower() not in small:
            out.append(w.capitalize())
        else:
            out.append(w.lower())
    return " ".join(out)


_OWNER_ACRONYMS = frozenset({"nhs", "pac", "dnc", "rnc", "nrsc", "dscc"})


def _owner_display(raw: str, owner_type: str = "") -> str:
    """Title-case owner name. Acronyms (NHS, PAC, etc.) stay caps. For orgs: lowercase the/and/at/of/a in middle."""
    if not raw or not isinstance(raw, str):
        return raw or ""
    s = raw.strip()
    lower = s.lower()
    if lower in _OWNER_ACRONYMS and len(s) <= 6:
        return s.upper()
    is_org = (owner_type or "").upper() == "ORGANIZATION"
    if is_org:
        return _title_case_facility(s)
    return s.title()


from display_utils import format_top_recipients
from common_names import is_common_name as _is_common_name, is_likely_conflated as _is_likely_conflated


def register_top_routes(app):
    """Register /top route. Called from owner_donor_dashboard if this module exists."""

    @app.route('/top.csv')
    def top_csv():
        """Serve full top contributors CSV for download. 404 unless ENABLE_TOP_PAGE=1."""
        if os.environ.get("ENABLE_TOP_PAGE") != "1":
            abort(404)
        base = Path(__file__).resolve().parent
        csv_path = base / "FEC data" / "top_nursing_home_contributors_2026.csv"
        if not csv_path.exists():
            abort(404)
        return send_file(
            csv_path,
            as_attachment=True,
            download_name="top_nursing_home_contributors.csv",
            mimetype="text/csv",
        )

    @app.route('/top')
    def top_contributors():
        """Top contributors page. 404 unless ENABLE_TOP_PAGE=1 (not public)."""
        if os.environ.get("ENABLE_TOP_PAGE") != "1":
            abort(404)
        base = Path(__file__).resolve().parent
        csv_path = base / "FEC data" / "top_nursing_home_contributors_2026.csv"
        rows = []
        csv_exists = csv_path.exists()
        if csv_exists:
            import csv
            try:
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        facilities_raw = (r.get("facilities", "") or "").replace("\n", " ").replace("\r", "")
                        fac_list = [x.strip() for x in facilities_raw.split(",") if x.strip()]
                        facilities_tooltip = "; ".join(_title_case_facility(f) for f in fac_list[:15])
                        if len(fac_list) > 15:
                            facilities_tooltip += f" … and {len(fac_list) - 15} more"
                        fec_name = r.get("fec_name", "")
                        owner_type = r.get("owner_type", "")
                        num_contrib = int(r.get("num_contributions", 0))
                        is_common = _is_common_name(fec_name, owner_type)
                        likely_conflated = _is_likely_conflated(fec_name, owner_type, num_contrib)
                        rows.append({
                            "owner_cms": r.get("owner_cms", ""),
                            "owner_cms_display": _owner_display(r.get("owner_cms", ""), owner_type),
                            "fec_name": fec_name,
                            "fec_name_display": _fec_name_display(fec_name),
                            "total_amount": float(r.get("total_amount", 0)),
                            "num_contributions": num_contrib,
                            "facilities": facilities_raw,
                            "facilities_tooltip": facilities_tooltip,
                            "owner_type": owner_type,
                            "num_facilities": int(r.get("num_facilities", 0)),
                            "top_recipients": r.get("top_recipients", ""),
                            "top_recipients_display": format_top_recipients(r.get("top_recipients", "")),
                            "years_included": r.get("years_included", ""),
                            "is_common_name": is_common,
                            "likely_conflated": likely_conflated,
                        })
            except Exception as e:
                rows = []
                csv_exists = False
        # Sort: non-conflated first by amount desc, then conflated (so common+high-contrib at end)
        rows.sort(key=lambda r: (r.get("likely_conflated", False), -r.get("total_amount", 0)))
        raw_years = (rows[0].get("years_included", "") if rows else "") or "2023,2024,2025,2026"
        years_list = [y.strip() for y in raw_years.split(",") if y.strip()]
        if len(years_list) >= 2:
            years_display = f"{years_list[0]}–{years_list[-1][2:]}"  # e.g. 2019–26
        else:
            years_display = raw_years.replace(",", ", ") if raw_years else "2022–26"
        return render_template(
            "owner_donor_dashboard_top.html",
            rows=rows,
            csv_exists=csv_exists,
            csv_path=str(csv_path),
            years_included=years_display,
        )
