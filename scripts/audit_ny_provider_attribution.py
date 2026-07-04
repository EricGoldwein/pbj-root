#!/usr/bin/env python3
"""QA gate: quarter-aligned ProviderInfoNorm attribution for NY 2025 verification package.

Verified from: public/downloads/.../daily_facility_data.csv (below_350_direct_care default).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV_DIR = ROOT / "public" / "downloads" / "PBJ320_NY_2025_daily_staffing_verification_csvs"
HTML = ROOT / "insights-ny-minimum-staffing.html"

EXCLUDED_CCNS = ("335683", "335675")
BELOW_COL = "below_350_direct_care"
ANCHOR_STATEWIDE_FD = 216_134
ANCHOR_STATEWIDE_BELOW = 123_428

CCN_EXPECTED = {
    "335683": {
        "ownership_contains": "for-profit",
        "county": "chautauqua",
        "nyc_flag": False,
    },
    "335675": {
        "ownership_contains": "non-profit",
        "county": "broome",
        "nyc_flag": False,
    },
}

OWNERSHIP_SLICES = (
    ("For-profit", "For-profit"),
    ("Non-profit", "Non-profit"),
    ("Government", "Government"),
)


def _blank_series(series: pd.Series) -> pd.Series:
    s = series.fillna("").astype(str).str.strip()
    return s.eq("") | s.str.lower().isin(("nan", "none", "<na>"))


def _truthy(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.lower().isin(("true", "1", "yes"))


def extract_json_after(marker: str, text: str) -> object:
    start = text.index(marker) + len(marker)
    depth = 0
    for j in range(start, len(text)):
        c = text[j]
        if c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : j + 1])
    raise ValueError(f"unterminated JSON after {marker!r}")


def _daily_totals(daily: pd.DataFrame, mask: pd.Series | None = None) -> tuple[int, int]:
    sub = daily if mask is None else daily.loc[mask]
    fd = len(sub)
    bl = int(_truthy(sub[BELOW_COL]).sum()) if fd else 0
    return fd, bl


def audit() -> list[str]:
    errors: list[str] = []

    daily_path = CSV_DIR / "daily_facility_data.csv"
    own_path = CSV_DIR / "ownership_summary.csv"
    fac_path = CSV_DIR / "facility_summary.csv"
    for p in (daily_path, own_path, fac_path):
        if not p.is_file():
            errors.append(f"missing {p}")
            return errors

    daily = pd.read_csv(daily_path, dtype=str)
    daily["ccn"] = daily["ccn"].str.zfill(6)
    own = pd.read_csv(own_path)
    fac = pd.read_csv(fac_path, dtype=str)
    fac["ccn"] = fac["ccn"].str.zfill(6)

    if BELOW_COL not in daily.columns:
        errors.append(f"daily missing NY-mapped default column {BELOW_COL!r}")
        return errors
    if "total_hprd" not in daily.columns:
        errors.append("daily missing comparison-only column total_hprd")

    if _blank_series(daily["provider_name"]).any():
        errors.append(f"blank provider_name rows: {int(_blank_series(daily['provider_name']).sum())}")
    if _blank_series(daily["county"]).any():
        errors.append(f"blank county rows: {int(_blank_series(daily['county']).sum())}")

    other = own[own["slice"].astype(str).str.contains("Other", case=False, na=False)]
    other_fd = int(other["facility_days"].sum()) if not other.empty else 0
    if other_fd:
        errors.append(f"Other/unknown facility-days remain: {other_fd}")

    statewide_fd, statewide_bl = _daily_totals(daily)
    if statewide_fd != ANCHOR_STATEWIDE_FD:
        errors.append(f"statewide facility-days {statewide_fd} != {ANCHOR_STATEWIDE_FD}")
    if statewide_bl != ANCHOR_STATEWIDE_BELOW:
        errors.append(f"statewide below-standard days {statewide_bl} != {ANCHOR_STATEWIDE_BELOW}")

    all_ny = own[own["slice"].astype(str).str.lower() == "all ny"]
    if all_ny.empty:
        errors.append("ownership_summary missing All NY slice")
    else:
        r = all_ny.iloc[0]
        if int(r["facility_days"]) != statewide_fd or int(r["days_below_350_direct"]) != statewide_bl:
            errors.append(
                f"All NY ownership totals {r['facility_days']}/{r['days_below_350_direct']} "
                f"!= daily NY-mapped {statewide_fd}/{statewide_bl}"
            )

    for slice_label, ownership_type in OWNERSHIP_SLICES:
        mask = daily["ownership_type"].astype(str).str.lower() == ownership_type.lower()
        exp_fd, exp_bl = _daily_totals(daily, mask)
        row = own[own["slice"].astype(str).str.lower() == slice_label.lower()]
        if row.empty:
            errors.append(f"ownership_summary missing slice {slice_label!r}")
            continue
        r = row.iloc[0]
        if int(r["facility_days"]) != exp_fd or int(r["days_below_350_direct"]) != exp_bl:
            errors.append(
                f"{slice_label} totals {r['facility_days']}/{r['days_below_350_direct']} "
                f"!= daily NY-mapped {exp_fd}/{exp_bl}"
            )

    for ccn, expected in CCN_EXPECTED.items():
        sub = daily[daily["ccn"] == ccn]
        if sub.empty:
            errors.append(f"missing daily rows for CCN {ccn}")
            continue
        if _blank_series(sub["provider_name"]).any() or _blank_series(sub["county"]).any():
            errors.append(f"{ccn} has blank provider_name or county")
        if _truthy(sub["nyc_flag"]).any() != expected["nyc_flag"]:
            errors.append(f"{ccn} incorrectly flagged nyc_flag={expected['nyc_flag']}")

        exp_fd, exp_bl = _daily_totals(sub)
        row = fac[fac["ccn"] == ccn]
        if row.empty:
            errors.append(f"missing facility_summary for {ccn}")
            continue
        r = row.iloc[0]
        own_type = str(r["ownership_type"]).lower()
        if expected["ownership_contains"] not in own_type:
            errors.append(f"{ccn} ownership not {expected['ownership_contains']}: {r['ownership_type']!r}")
        if str(r["county"]).lower() != expected["county"]:
            errors.append(f"{ccn} county not {expected['county'].title()}: {r['county']!r}")
        if int(r["facility_days"]) != exp_fd or int(r["days_below_350_direct"]) != exp_bl:
            errors.append(
                f"{ccn} facility_summary fd/below {r['facility_days']}/{r['days_below_350_direct']} "
                f"!= daily NY-mapped {exp_fd}/{exp_bl}"
            )

    nyc_other = own[own["slice"].astype(str).str.contains("NYC other", case=False, na=False)]
    if not nyc_other.empty and int(nyc_other.iloc[0]["facility_days"]) > 0:
        errors.append("NYC other/unknown slice still has facility-days")

    if HTML.is_file():
        html = HTML.read_text(encoding="utf-8")
        if '"provider_name": "nan"' in html or '"provider_name":"nan"' in html:
            errors.append('embedded JSON contains provider_name "nan"')
        if "Ownership coverage:" in html and "442" in html:
            errors.append("stale ownership coverage footnote still present")
        facilities = extract_json_after("window.PBJ_REPORT_FACILITIES = ", html)
        for ccn in EXCLUDED_CCNS:
            hit = next((f for f in facilities["facilities"] if f["ccn"] == ccn), None)
            if not hit:
                errors.append(f"embedded facilities missing {ccn}")
                continue
            if hit.get("is_nyc"):
                errors.append(f"embedded {ccn} is_nyc=true")
            if not hit.get("provider_name"):
                errors.append(f"embedded {ccn} blank provider_name")

        interactive = extract_json_after("window.PBJ_REPORT_INTERACTIVE = ", html)
        default_mode = interactive.get("default_mode", "ny_mapped_non_admin_hprd")
        mode = interactive["modes"][default_mode]
        fp_pt = next(
            p for p in mode["curves"]["ny_for_profit"] if abs(float(p["threshold"]) - 3.5) < 0.01
        )
        np_pt = next(
            p for p in mode["curves"]["ny_non_profit"] if abs(float(p["threshold"]) - 3.5) < 0.01
        )
        fp_row = own[own["slice"].astype(str).str.lower() == "for-profit"]
        np_row = own[own["slice"].astype(str).str.lower() == "non-profit"]
        if not fp_row.empty and int(fp_row.iloc[0]["days_below_350_direct"]) != int(fp_pt["below"]):
            errors.append(
                f"embed for-profit below {fp_pt['below']} != ownership summary "
                f"{fp_row.iloc[0]['days_below_350_direct']}"
            )
        if not np_row.empty and int(np_row.iloc[0]["days_below_350_direct"]) != int(np_pt["below"]):
            errors.append(
                f"embed non-profit below {np_pt['below']} != ownership summary "
                f"{np_row.iloc[0]['days_below_350_direct']}"
            )

    return errors


def main() -> int:
    errors = audit()
    if errors:
        print("FAIL audit_ny_provider_attribution.py")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("PASS audit_ny_provider_attribution.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
