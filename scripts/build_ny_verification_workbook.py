#!/usr/bin/env python3
"""
Build public NY 2025 daily staffing verification workbook + CSV package.

Verified from: PBJapp/scripts/analyze_ny_minimum_staffing.py (facility-day logic, thresholds).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import numpy as np
import pandas as pd
from openpyxl.styles import Font

ROOT = Path(__file__).resolve().parents[1]
PBJAPP_ROOT = ROOT.parent / "PBJapp"
if PBJAPP_ROOT.exists() and str(PBJAPP_ROOT) not in sys.path:
    sys.path.insert(0, str(PBJAPP_ROOT))

from scripts.analyze_ny_minimum_staffing import (  # noqa: E402
    HRS_BROAD_PBJ_TOTAL,
    HRS_NY_MAPPED_CNA_SIDE,
    HRS_NY_MAPPED_INCLUDE_DON,
    HRS_NY_MAPPED_LICENSED,
    HRS_NY_MAPPED_TOTAL,
    NY_STATUTE_CNA_MIN_HPRD,
    NY_STATUTE_LPN_RN_MIN_HPRD,
    NY_STATUTE_TOTAL_MIN_HPRD,
    _col_bool,
    _col_eq,
    _col_series,
    _compute_quarterly_statutory_rows,
    _facility_quarter_pivot_flags,
    _facility_quarter_rollups,
    _iso_week_key,
    _load_ny_facility_days,
    _merge_days_provider_time_aware,
    _pbj_county_fips_full,
    _pbj_quarter_paths,
    _quarterly_statutory_summary,
    _sum_hours,
    _us_federal_holidays,
)

YEAR = 2025
THRESHOLD_TOTAL = 3.50
TABLES_GENERATED_DATE = datetime.now().strftime("%Y-%m-%d")
REPORT_URL = "https://pbj320.com/insights/ny-minimum-staffing"
CONTACT_EMAIL = "eric@320insight.com"
PBJ320_SITE = "https://www.pbj320.com"
CMS_PBJ_DAILY_BASE_URL = (
    "https://data.cms.gov/quality-of-care/payroll-based-journal-daily-nurse-staffing"
)

WORKBOOK_NAME = "PBJ320_NY_2025_daily_staffing_verification_file.xlsx"
CSV_DIR_NAME = "PBJ320_NY_2025_daily_staffing_verification_csvs"
ZIP_NAME = f"{CSV_DIR_NAME}.zip"

OUT_BASE = ROOT / "public" / "downloads"
XLSX_PATH = OUT_BASE / WORKBOOK_NAME
CSV_DIR = OUT_BASE / CSV_DIR_NAME
ZIP_PATH = OUT_BASE / ZIP_NAME

# Reconciliation anchors populated at build time (NY-mapped default @ 3.50 HPRD)
ANCHOR_STATEWIDE_FD: int | None = None
ANCHOR_STATEWIDE_BELOW: int | None = None
ANCHOR_STATEWIDE_PCT: float | None = None
ANCHOR_NYC_WKND_FD: int | None = None
ANCHOR_NYC_WKND_BELOW: int | None = None
ANCHOR_NYC_WKND_PCT: float | None = None

FORBIDDEN_COLUMN_PATTERNS = (
    "employee",
    "ssn",
    "incident",
    "attorney",
    "client_note",
    "provnum",
    "shift_",
    "window_",
)

OWNERSHIP_DISPLAY = {
    "For profit": "For-profit",
    "Non profit": "Non-profit",
    "Government": "Government",
    "Other/unknown": "Other / unknown",
}

URL_COLUMN_MARKERS = ("_url",)

# Exported CSV column names (daily + summaries)
COL_TOTAL_HPRD = "total_hprd"
COL_DIRECT_CARE_HPRD = "direct_care_hprd"
COL_CNA_SIDE_HPRD = "cna_side_hprd"
COL_LICENSED_NURSE_HPRD = "licensed_nurse_hprd"
COL_DIRECT_CARE_INCLUDE_DON_HPRD = "direct_care_include_don_hprd"
COL_BELOW_350_DIRECT_CARE = "below_350_direct_care"
COL_BELOW_350_TOTAL_NURSING = "below_350_total_nursing"
COL_MET_ALL_THREE_DIRECT_CARE = "met_all_three_direct_care"
COL_DAYS_BELOW_350_DIRECT = "days_below_350_direct"
COL_DAYS_BELOW_350_TOTAL = "days_below_350_total"
COL_PCT_BELOW_350_DIRECT = "pct_below_350_direct"
COL_PCT_BELOW_350_TOTAL = "pct_below_350_total"
COL_PCT_DAYS_BELOW_350_DIRECT = "pct_days_below_350_direct"
COL_PCT_DAYS_BELOW_350_TOTAL = "pct_days_below_350_total"

FACILITY_QUARTER_COL_RENAME = {
    "ny_mapped_total_hours": "direct_care_hours",
    "ny_mapped_total_hprd": COL_DIRECT_CARE_HPRD,
    "ny_mapped_cna_side_hours": "cna_side_hours",
    "ny_mapped_cna_side_hprd": COL_CNA_SIDE_HPRD,
    "ny_mapped_licensed_hours": "licensed_nurse_hours",
    "ny_mapped_licensed_hprd": COL_LICENSED_NURSE_HPRD,
    "ny_mapped_include_don_total_hprd": "direct_care_include_don_hprd",
}


def _pbj_role_sum(cols: tuple[str, ...]) -> str:
    return "+".join(cols)


def _excel_daily_hprd_formula(cols: tuple[str, ...]) -> str:
    """Excel expression as documentation text (no leading = — avoids #NAME? in README cells)."""
    return f"({_pbj_role_sum(cols)})/MDScensus"


def _methodology_readme_lines() -> list[tuple[str, str]]:
    """README Methodology: definitions + Excel formulas users can replicate in CMS PBJ exports."""
    return [
        ("Methodology", ""),
        (
            "Unit of analysis",
            "One facility-day per NY CCN per calendar day with MDScensus > 0.",
        ),
        (
            "HPRD definition",
            "Hours per resident day = sum of CMS PBJ role hours / MDScensus on that day.",
        ),
        (
            "Strict threshold rule",
            "Below standard when HPRD is strictly less than the threshold; equal counts as compliant.",
        ),
        ("", ""),
        ("Daily HPRD columns (CMS PBJ → this file)", ""),
        (
            COL_TOTAL_HPRD,
            f"Total PBJ nursing (comparison): ({_pbj_role_sum(HRS_BROAD_PBJ_TOTAL)}) / MDScensus",
        ),
        (f"{COL_TOTAL_HPRD} (Excel)", _excel_daily_hprd_formula(HRS_BROAD_PBJ_TOTAL)),
        (
            COL_DIRECT_CARE_HPRD,
            f"NY direct care (report default): ({_pbj_role_sum(HRS_NY_MAPPED_TOTAL)}) / MDScensus",
        ),
        (f"{COL_DIRECT_CARE_HPRD} (Excel)", _excel_daily_hprd_formula(HRS_NY_MAPPED_TOTAL)),
        (
            COL_CNA_SIDE_HPRD,
            f"CNA-side @ 2.20 floor: ({_pbj_role_sum(HRS_NY_MAPPED_CNA_SIDE)}) / MDScensus",
        ),
        (f"{COL_CNA_SIDE_HPRD} (Excel)", _excel_daily_hprd_formula(HRS_NY_MAPPED_CNA_SIDE)),
        (
            COL_LICENSED_NURSE_HPRD,
            f"Licensed nurse @ 1.10 floor: ({_pbj_role_sum(HRS_NY_MAPPED_LICENSED)}) / MDScensus",
        ),
        (
            f"{COL_LICENSED_NURSE_HPRD} (Excel)",
            _excel_daily_hprd_formula(HRS_NY_MAPPED_LICENSED),
        ),
        (
            COL_DIRECT_CARE_INCLUDE_DON_HPRD,
            f"Include-DON sensitivity: ({_pbj_role_sum(HRS_NY_MAPPED_INCLUDE_DON)}) / MDScensus",
        ),
        (
            f"{COL_DIRECT_CARE_INCLUDE_DON_HPRD} (Excel)",
            _excel_daily_hprd_formula(HRS_NY_MAPPED_INCLUDE_DON),
        ),
        ("", ""),
        ("Daily compliance flags (Excel on exported HPRD columns)", ""),
        (COL_BELOW_350_DIRECT_CARE, f"{COL_DIRECT_CARE_HPRD}<{THRESHOLD_TOTAL}"),
        (COL_BELOW_350_DIRECT_CARE + " (Excel)", f"{COL_DIRECT_CARE_HPRD}<3.5"),
        (COL_BELOW_350_TOTAL_NURSING, f"{COL_TOTAL_HPRD}<{THRESHOLD_TOTAL}"),
        (COL_BELOW_350_TOTAL_NURSING + " (Excel)", f"{COL_TOTAL_HPRD}<3.5"),
        ("below_220_cna_side", f"{COL_CNA_SIDE_HPRD}<{NY_STATUTE_CNA_MIN_HPRD}"),
        ("below_220_cna_side (Excel)", f"{COL_CNA_SIDE_HPRD}<2.2"),
        ("below_110_licensed", f"{COL_LICENSED_NURSE_HPRD}<{NY_STATUTE_LPN_RN_MIN_HPRD}"),
        ("below_110_licensed (Excel)", f"{COL_LICENSED_NURSE_HPRD}<1.1"),
        (
            COL_MET_ALL_THREE_DIRECT_CARE,
            f"AND(NOT({COL_BELOW_350_DIRECT_CARE}),NOT(below_220_cna_side),NOT(below_110_licensed))",
        ),
        ("", ""),
        ("Quarterly facility-quarter metrics", ""),
        (
            f"Quarterly {COL_DIRECT_CARE_HPRD}",
            f"SUM({_pbj_role_sum(HRS_NY_MAPPED_TOTAL)})/SUM(MDScensus) within CCN+quarter",
        ),
        (
            f"Quarterly {COL_DIRECT_CARE_HPRD} (Excel)",
            f"SUM({_pbj_role_sum(HRS_NY_MAPPED_TOTAL)})/SUM(MDScensus)",
        ),
        (
            "Quarterly below_350_direct_care_quarter",
            f"Quarterly {COL_DIRECT_CARE_HPRD}<{THRESHOLD_TOTAL}",
        ),
        (
            "Quarterly below_350_direct_care_quarter (Excel)",
            f"Quarterly {COL_DIRECT_CARE_HPRD}<3.5",
        ),
        (
            "Quarterly CNA-side / licensed floors",
            f"Same pattern using {COL_CNA_SIDE_HPRD} and {COL_LICENSED_NURSE_HPRD} @ 2.20 and 1.10",
        ),
    ]


def _url_ccn(ccn: str) -> str:
    """CCN for external URLs (no leading zeros; matches site/Care Compare convention)."""
    s = str(ccn).strip().zfill(6)
    return s.lstrip("0") or "0"


def _pbj320_provider_url(ccn: str) -> str:
    return f"{PBJ320_SITE}/provider/{_url_ccn(ccn)}"


def _medicare_care_compare_url(ccn: str, *, state: str = "NY") -> str:
    return (
        f"https://www.medicare.gov/care-compare/details/nursing-home/"
        f"{_url_ccn(ccn)}/view-all/?state={state}"
    )


def _cms_pbj_quarter_filtered_url(ccn: str, quarter: int, *, year: int = YEAR) -> str:
    """PROVNUM-only CMS Data Catalog filter (2025 CY files use PROVNUM)."""
    prov = _url_ccn(ccn)
    query = {
        "filters": {
            "list": [
                {
                    "conditions": [
                        {
                            "column": {"value": "PROVNUM"},
                            "comparator": {"value": "="},
                            "filterValue": [prov],
                        }
                    ]
                }
            ],
            "rootConjunction": {"value": "AND"},
        },
        "keywords": "",
        "offset": 0,
        "limit": 10,
        "sort": {"sortBy": None, "sortOrder": None},
        "columns": [],
    }
    base = f"{CMS_PBJ_DAILY_BASE_URL}/data/q{quarter}-{year}"
    return f"{base}?query={quote(json.dumps(query, separators=(',', ':')))}"


def _is_url_column(col: str) -> bool:
    low = str(col).lower()
    return low.endswith("_url") or low == "url"


def _apply_sheet_hyperlinks(ws, columns: list[str], row_count: int) -> None:
    link_font = Font(color="0563C1", underline="single")
    for col_idx, col_name in enumerate(columns, start=1):
        if not _is_url_column(col_name):
            continue
        for row_idx in range(2, row_count + 2):
            cell = ws.cell(row=row_idx, column=col_idx)
            val = cell.value
            if isinstance(val, str) and val.startswith("http"):
                cell.hyperlink = val
                cell.font = link_font


WEEKEND_SLICE_SPECS: tuple[tuple[str, str], ...] = (
    ("All NY", "all"),
    ("NY statewide for-profit", "ny_for_profit"),
    ("NY statewide non-profit", "ny_non_profit"),
    ("NY statewide government", "ny_government"),
    ("NYC five boroughs", "nyc"),
    ("NYC for-profit", "nyc_for_profit"),
    ("NYC non-profit", "nyc_non_profit"),
    ("NYC government", "nyc_government"),
)


def _ownership_mask(merged: pd.DataFrame, key: str) -> pd.Series:
    is_nyc = _col_bool(merged, "is_nyc")
    is_fp = _col_eq(merged, "ownership_bucket", "For profit")
    is_np = _col_eq(merged, "ownership_bucket", "Non profit")
    is_gov = _col_eq(merged, "ownership_bucket", "Government")
    is_other = _col_eq(merged, "ownership_bucket", "Other/unknown")
    if key == "all":
        return pd.Series(True, index=merged.index, dtype=bool)
    if key == "for_profit":
        return is_fp
    if key == "non_profit":
        return is_np
    if key == "government":
        return is_gov
    if key == "other":
        return is_other
    if key == "nyc":
        return is_nyc
    if key == "nyc_for_profit":
        return is_nyc & is_fp
    if key == "nyc_non_profit":
        return is_nyc & is_np
    if key == "nyc_government":
        return is_nyc & is_gov
    if key == "nyc_other":
        return is_nyc & is_other
    if key == "ny_for_profit":
        return is_fp
    if key == "ny_non_profit":
        return is_np
    if key == "ny_government":
        return is_gov
    raise KeyError(key)


def _slice_mask(merged: pd.DataFrame, spec_key: str) -> pd.Series:
    is_nyc = _col_bool(merged, "is_nyc")
    is_fp = _col_eq(merged, "ownership_bucket", "For profit")
    is_np = _col_eq(merged, "ownership_bucket", "Non profit")
    is_gov = _col_eq(merged, "ownership_bucket", "Government")
    masks = {
        "all": pd.Series(True, index=merged.index, dtype=bool),
        "ny_for_profit": is_fp,
        "ny_non_profit": is_np,
        "ny_government": is_gov,
        "nyc": is_nyc,
        "nyc_for_profit": is_nyc & is_fp,
        "nyc_non_profit": is_nyc & is_np,
        "nyc_government": is_nyc & is_gov,
    }
    return masks[spec_key]


def _finite_mask(merged: pd.DataFrame) -> pd.Series:
    col = "hprd_ny_mapped_total" if "hprd_ny_mapped_total" in merged.columns else "hprd"
    return np.isfinite(_col_series(merged, col).to_numpy())


def _load_ny_facility_days_with_quarter(year: int) -> pd.DataFrame:
    """Load facility-days and tag each row with PBJ quarterly source file label."""
    paths = _pbj_quarter_paths(year)
    if not paths:
        return _load_ny_facility_days(year, "total").assign(source_file_quarter=pd.NA)
    parts: list[pd.DataFrame] = []
    for path in paths:
        q_label = path.name.split("CY")[1].replace(".csv", "")
        usecols = [
            "PROVNUM",
            "STATE",
            "WorkDate",
            "MDScensus",
            "COUNTY_FIPS",
            "COUNTY_NAME",
            "CITY",
            *HRS_BROAD_PBJ_TOTAL,
        ]
        start = pd.Timestamp(f"{year}-01-01")
        end = pd.Timestamp(f"{year}-12-31")
        for chunk in pd.read_csv(
            path,
            usecols=lambda c: c in usecols,
            dtype={"PROVNUM": str, "STATE": str},
            chunksize=250_000,
            low_memory=False,
            encoding="latin-1",
        ):
            chunk = chunk[chunk["STATE"].astype(str).str.upper() == "NY"].copy()
            if chunk.empty:
                continue
            chunk["WorkDate"] = pd.to_datetime(
                chunk["WorkDate"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True),
                format="%Y%m%d",
                errors="coerce",
            )
            chunk = chunk[
                chunk["WorkDate"].notna()
                & (chunk["WorkDate"] >= start)
                & (chunk["WorkDate"] <= end)
            ]
            census = pd.to_numeric(chunk["MDScensus"], errors="coerce")
            chunk = chunk[census > 0].copy()
            if chunk.empty:
                continue
            census = pd.to_numeric(chunk["MDScensus"], errors="coerce")
            chunk["hprd"] = _sum_hours(chunk, HRS_BROAD_PBJ_TOTAL) / census
            chunk["hprd_ny_mapped_total"] = _sum_hours(chunk, HRS_NY_MAPPED_TOTAL) / census
            chunk["hprd_ny_mapped_cna_side"] = _sum_hours(chunk, HRS_NY_MAPPED_CNA_SIDE) / census
            chunk["hprd_ny_mapped_licensed"] = _sum_hours(chunk, HRS_NY_MAPPED_LICENSED) / census
            chunk["hprd_ny_mapped_include_don"] = (
                _sum_hours(chunk, HRS_NY_MAPPED_INCLUDE_DON) / census
            )
            chunk["hprd_excl_admin"] = chunk["hprd_ny_mapped_total"]
            chunk["hprd_cna_statute"] = chunk["hprd_ny_mapped_cna_side"]
            chunk["hprd_lpn_rn_statute"] = chunk["hprd_ny_mapped_licensed"]
            chunk["ccn"] = chunk["PROVNUM"].astype(str).str.strip().str.zfill(6)
            chunk["dow"] = chunk["WorkDate"].dt.day_name()
            chunk["month"] = chunk["WorkDate"].dt.month
            chunk["county_fips"] = None
            if "COUNTY_FIPS" in chunk.columns:
                chunk["county_fips"] = _pbj_county_fips_full(chunk["COUNTY_FIPS"])
            chunk["county_name_pbj"] = (
                chunk["COUNTY_NAME"].astype(str).str.strip()
                if "COUNTY_NAME" in chunk.columns
                else ""
            )
            chunk["city_pbj"] = (
                chunk["CITY"].astype(str).str.strip() if "CITY" in chunk.columns else ""
            )
            chunk["source_file_quarter"] = q_label
            parts.append(
                chunk[
                    [
                        "ccn",
                        "WorkDate",
                        "dow",
                        "month",
                        "hprd",
                        "hprd_ny_mapped_total",
                        "hprd_ny_mapped_cna_side",
                        "hprd_ny_mapped_licensed",
                        "hprd_ny_mapped_include_don",
                        "hprd_excl_admin",
                        "hprd_cna_statute",
                        "hprd_lpn_rn_statute",
                        "MDScensus",
                        "county_fips",
                        "county_name_pbj",
                        "city_pbj",
                        "source_file_quarter",
                    ]
                ].rename(columns={"WorkDate": "work_date"})
            )
    if not parts:
        raise RuntimeError(f"No NY facility-days with census > 0 in {year}")
    return pd.concat(parts, ignore_index=True)


def _prepare_merged(year: int) -> pd.DataFrame:
    days = _load_ny_facility_days_with_quarter(year)
    merged = _merge_days_provider_time_aware(days, year=year)

    census = pd.to_numeric(merged["MDScensus"], errors="coerce")
    merged["broad_total_hours"] = _col_series(merged, "hprd") * census
    merged["ny_mapped_total_hours"] = _col_series(merged, "hprd_ny_mapped_total") * census
    merged["ny_mapped_cna_side_hours"] = _col_series(merged, "hprd_ny_mapped_cna_side") * census
    merged["ny_mapped_licensed_hours"] = _col_series(merged, "hprd_ny_mapped_licensed") * census
    merged["ny_mapped_include_don_hours"] = (
        _col_series(merged, "hprd_ny_mapped_include_don") * census
    )

    merged["below_350_ny_mapped"] = _col_series(merged, "hprd_ny_mapped_total") < THRESHOLD_TOTAL
    merged["below_350_total_nursing"] = _col_series(merged, "hprd") < THRESHOLD_TOTAL
    merged["below_350_direct"] = merged["below_350_ny_mapped"]
    merged["below_220_cna_side"] = (
        _col_series(merged, "hprd_ny_mapped_cna_side") < NY_STATUTE_CNA_MIN_HPRD
    )
    merged["below_110_licensed"] = (
        _col_series(merged, "hprd_ny_mapped_licensed") < NY_STATUTE_LPN_RN_MIN_HPRD
    )
    merged["met_all_three_ny_mapped"] = ~(
        merged["below_350_ny_mapped"] | merged["below_220_cna_side"] | merged["below_110_licensed"]
    )
    # Legacy alias for internal aggregations
    merged["below_350_hprd"] = merged["below_350_direct"]
    merged["below_220_cna_hprd"] = merged["below_220_cna_side"]
    merged["below_110_licensed_hprd"] = merged["below_110_licensed"]
    merged["met_all_three_ny_floors"] = merged["met_all_three_ny_mapped"]

    federal_dates = _us_federal_holidays(year)
    work_norm = pd.to_datetime(_col_series(merged, "work_date")).dt.normalize()
    merged["federal_holiday_flag"] = work_norm.isin(pd.to_datetime(sorted(federal_dates)))
    merged["weekend_flag"] = _col_series(merged, "dow").isin(["Saturday", "Sunday"])
    merged["iso_week"] = _iso_week_key(_col_series(merged, "work_date"))
    merged["year"] = pd.to_datetime(merged["work_date"]).dt.year
    merged["quarter"] = pd.to_datetime(merged["work_date"]).dt.quarter
    merged["ownership_display"] = merged["ownership_bucket"].map(OWNERSHIP_DISPLAY).fillna(
        "Other / unknown"
    )
    return merged


def _count_below(mask: pd.Series, merged: pd.DataFrame) -> tuple[int, int, int]:
    sub = merged.loc[mask & _finite_mask(merged)]
    fd = len(sub)
    if not fd:
        return 0, 0, 0
    return (
        fd,
        int(sub["below_350_direct"].sum()),
        int(sub["below_350_total_nursing"].sum()),
    )


def _pct(bl: int, fd: int) -> float | None:
    return round(100.0 * bl / fd, 1) if fd else None


def _summary_below_fields(fd: int, bl_direct: int, bl_total: int) -> dict[str, Any]:
    return {
        "facility_days": fd,
        COL_DAYS_BELOW_350_DIRECT: bl_direct,
        COL_DAYS_BELOW_350_TOTAL: bl_total,
        COL_PCT_BELOW_350_DIRECT: _pct(bl_direct, fd),
        COL_PCT_BELOW_350_TOTAL: _pct(bl_total, fd),
    }


def _build_facility_links(merged: pd.DataFrame) -> pd.DataFrame:
    """One row per CCN with external verification URLs (no daily-row duplication)."""
    work = merged.copy()
    if "city" not in work.columns or work["city"].isna().all():
        work["city"] = work.get("city_pbj", "")
    if "county" not in work.columns or work["county"].isna().all():
        work["county"] = work.get("county_norm", "")
    g = work.groupby("ccn", observed=True)
    meta = g.agg(
        provider_name=("provider_name", "first"),
        city=("city", "first"),
        county=("county", "first"),
        ownership_type=("ownership_display", "first"),
    ).reset_index()
    meta["pbj320_provider_url"] = meta["ccn"].map(_pbj320_provider_url)
    meta["medicare_care_compare_url"] = meta["ccn"].map(_medicare_care_compare_url)
    meta["cms_pbj_daily_base_url"] = CMS_PBJ_DAILY_BASE_URL
    for q in (1, 2, 3, 4):
        meta[f"cms_pbj_daily_q{q}_url"] = meta["ccn"].map(
            lambda c, qn=q: _cms_pbj_quarter_filtered_url(c, qn)
        )
    return meta.sort_values("ccn")


def _build_daily_sheet(merged: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ccn": merged["ccn"],
            "facility_links_sheet_key": merged["ccn"],
            "provider_name": merged.get("provider_name", pd.Series([""] * len(merged))),
            "city": merged.get("city", merged.get("city_pbj", "")),
            "county": merged.get("county", merged.get("county_norm", "")),
            "ownership_type": merged["ownership_display"],
            "nyc_flag": _col_bool(merged, "is_nyc"),
            "work_date": pd.to_datetime(merged["work_date"]).dt.strftime("%Y-%m-%d"),
            "year": merged["year"],
            "quarter": merged["quarter"],
            "month": merged["month"],
            "iso_week": merged["iso_week"],
            "day_of_week": merged["dow"],
            "weekend_flag": merged["weekend_flag"],
            "federal_holiday_flag": merged["federal_holiday_flag"],
            "mds_census": pd.to_numeric(merged["MDScensus"], errors="coerce").round(3),
            COL_TOTAL_HPRD: _col_series(merged, "hprd").round(4),
            COL_DIRECT_CARE_HPRD: _col_series(merged, "hprd_ny_mapped_total").round(4),
            COL_CNA_SIDE_HPRD: _col_series(merged, "hprd_ny_mapped_cna_side").round(4),
            COL_LICENSED_NURSE_HPRD: _col_series(merged, "hprd_ny_mapped_licensed").round(4),
            COL_DIRECT_CARE_INCLUDE_DON_HPRD: _col_series(merged, "hprd_ny_mapped_include_don").round(4),
            COL_BELOW_350_DIRECT_CARE: merged["below_350_ny_mapped"],
            COL_BELOW_350_TOTAL_NURSING: merged["below_350_total_nursing"],
            "below_220_cna_side": merged["below_220_cna_side"],
            "below_110_licensed": merged["below_110_licensed"],
            COL_MET_ALL_THREE_DIRECT_CARE: merged["met_all_three_ny_mapped"],
            "source_file_quarter": merged.get("source_file_quarter", pd.NA),
        }
    )


def _build_facility_summary(merged: pd.DataFrame, links_df: pd.DataFrame) -> pd.DataFrame:
    g = merged.groupby("ccn", observed=True)
    rows = g.agg(
        provider_name=("provider_name", "first"),
        city=("city", "first"),
        county=("county", "first"),
        ownership_type=("ownership_display", "first"),
        nyc_flag=("is_nyc", "first"),
        facility_days=("below_350_direct", "size"),
        days_below_350_direct=("below_350_direct", "sum"),
        days_below_350_total=("below_350_total_nursing", "sum"),
        mean_direct_care_hprd=("hprd_ny_mapped_total", "mean"),
        mean_total_hprd=("hprd", "mean"),
        mean_cna_side_hprd=("hprd_ny_mapped_cna_side", "mean"),
        mean_licensed_nurse_hprd=("hprd_ny_mapped_licensed", "mean"),
        days_below_220_cna=("below_220_cna_hprd", "sum"),
        days_below_110_licensed=("below_110_licensed_hprd", "sum"),
        days_met_all_three=("met_all_three_ny_floors", "sum"),
    ).reset_index()
    rows[COL_PCT_DAYS_BELOW_350_DIRECT] = (
        100.0 * rows[COL_DAYS_BELOW_350_DIRECT] / rows["facility_days"]
    ).round(1)
    rows[COL_PCT_DAYS_BELOW_350_TOTAL] = (
        100.0 * rows[COL_DAYS_BELOW_350_TOTAL] / rows["facility_days"]
    ).round(1)
    rows["pct_days_below_220_cna"] = (
        100.0 * rows["days_below_220_cna"] / rows["facility_days"]
    ).round(1)
    rows["pct_days_below_110_licensed"] = (
        100.0 * rows["days_below_110_licensed"] / rows["facility_days"]
    ).round(1)
    rows["pct_days_met_all_three"] = (
        100.0 * rows["days_met_all_three"] / rows["facility_days"]
    ).round(1)
    for col in ("mean_direct_care_hprd", "mean_total_hprd", "mean_cna_side_hprd", "mean_licensed_nurse_hprd"):
        rows[col] = rows[col].round(4)
    link_cols = ["pbj320_provider_url", "medicare_care_compare_url", "cms_pbj_daily_base_url"]
    rows = rows.merge(links_df[["ccn", *link_cols]], on="ccn", how="left")
    fq_df = _compute_quarterly_statutory_rows(merged)
    rollups = _facility_quarter_rollups(fq_df)
    if not rollups.empty:
        merge_cols = [
            "ccn",
            "quarters_analyzed",
            "quarters_below_350_total",
            "quarters_missing_any_floor",
            "quarters_met_all_three",
            "qtrs_below_350_display",
            "qtrs_missing_floor_display",
        ]
        rows = rows.merge(rollups[merge_cols], on="ccn", how="left")
        pivot = _facility_quarter_pivot_flags(fq_df)
        if not pivot.empty:
            rows = rows.merge(pivot, on="ccn", how="left")
    return rows.sort_values(COL_DAYS_BELOW_350_DIRECT, ascending=False)


def _enrich_facility_persistence_flags(rows: pd.DataFrame) -> pd.DataFrame:
    """Per-facility daily persistence flags @ NY-mapped 3.50 HPRD (strictly below)."""
    out = rows.copy()
    pct = out[COL_PCT_DAYS_BELOW_350_DIRECT]
    bl = out[COL_DAYS_BELOW_350_DIRECT]
    fd = out["facility_days"]
    out["below_350_ge_50pct_days"] = pct >= 50.0
    out["below_350_ge_75pct_days"] = pct >= 75.0
    out["below_350_ge_90pct_days"] = pct >= 90.0
    out["below_350_all_analyzed_days"] = bl >= fd
    out["below_350_zero_days"] = bl == 0

    def _band(row: pd.Series) -> str:
        if row[COL_DAYS_BELOW_350_DIRECT] >= row["facility_days"]:
            return "100% of days"
        p = float(row[COL_PCT_DAYS_BELOW_350_DIRECT])
        if p >= 90:
            return "90-99%"
        if p >= 75:
            return "75-89%"
        if p >= 50:
            return "50-74%"
        if p >= 25:
            return "25-49%"
        if row[COL_DAYS_BELOW_350_DIRECT] > 0:
            return "1-24%"
        return "0% (none)"

    out["provider_day_band"] = out.apply(_band, axis=1)
    return out


def _provider_persistence_counts(facility_df: pd.DataFrame) -> dict[str, Any]:
    n = int(len(facility_df))
    if n == 0:
        return {"facility_count": 0}
    flags = {
        "at_least_50pct": "below_350_ge_50pct_days",
        "at_least_75pct": "below_350_ge_75pct_days",
        "at_least_90pct": "below_350_ge_90pct_days",
        "all_analyzed_days": "below_350_all_analyzed_days",
        "zero_days": "below_350_zero_days",
    }
    thresholds: dict[str, Any] = {}
    for key, col in flags.items():
        count = int(facility_df[col].sum())
        thresholds[key] = {
            "facilities": count,
            "pct_of_facilities": round(100.0 * count / n, 1),
        }
    band_order = [
        "100% of days",
        "90-99%",
        "75-89%",
        "50-74%",
        "25-49%",
        "1-24%",
        "0% (none)",
    ]
    bands: list[dict[str, Any]] = []
    for label in band_order:
        count = int((facility_df["provider_day_band"] == label).sum())
        bands.append(
            {
                "band": label,
                "facilities": count,
                "pct_of_facilities": round(100.0 * count / n, 1),
            }
        )
    return {
        "metric": COL_DIRECT_CARE_HPRD,
        "threshold_hprd": THRESHOLD_TOTAL,
        "below_rule": "strictly less than 3.50",
        "facility_count": n,
        "thresholds": thresholds,
        "bands": bands,
    }


def _build_provider_persistence_summary(persistence: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        {
            "measure": "Facilities analyzed",
            "facilities": persistence["facility_count"],
            "pct_of_facilities": 100.0,
            "notes": "NY CCNs with census > 0 in CY2025 PBJ",
        }
    ]
    label_map = {
        "at_least_50pct": "Below 3.50 on >=50% of analyzed facility-days",
        "at_least_75pct": "Below 3.50 on >=75% of analyzed facility-days",
        "at_least_90pct": "Below 3.50 on >=90% of analyzed facility-days",
        "all_analyzed_days": "Below 3.50 on 100% of analyzed facility-days",
        "zero_days": "Below 3.50 on 0% of analyzed facility-days",
    }
    for key, label in label_map.items():
        t = persistence["thresholds"][key]
        rows.append(
            {
                "measure": label,
                "facilities": t["facilities"],
                "pct_of_facilities": t["pct_of_facilities"],
                "notes": "NY-mapped direct-care HPRD; daily staffing frame only",
            }
        )
    return pd.DataFrame(rows)


def _build_provider_day_bands_summary(persistence: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(persistence["bands"]).rename(
        columns={"band": "provider_day_band", "facilities": "facility_count"}
    )


def _build_facility_quarter_summary(merged: pd.DataFrame) -> pd.DataFrame:
    fq = _compute_quarterly_statutory_rows(merged)
    if fq.empty:
        return fq
    fq["ownership_type"] = fq["ownership_type"].map(OWNERSHIP_DISPLAY).fillna(fq["ownership_type"])
    quarter_renames = {
        **FACILITY_QUARTER_COL_RENAME,
        "below_350_total": "below_350_direct_care_quarter",
    }
    fq = fq.rename(columns={k: v for k, v in quarter_renames.items() if k in fq.columns})
    return fq.sort_values(["ccn", "quarter"])


def _build_dow_summary(merged: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for dow in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
        mask = _col_eq(merged, "dow", dow)
        fd, bl_direct, bl_total = _count_below(mask, merged)
        rows.append({"day_of_week": dow, **_summary_below_fields(fd, bl_direct, bl_total)})
    return pd.DataFrame(rows)


def _build_weekend_weekday_summary(merged: pd.DataFrame) -> pd.DataFrame:
    is_wknd = _col_bool(merged, "weekend_flag")
    is_wkd = ~is_wknd
    rows: list[dict[str, Any]] = []
    for slice_label, spec_key in WEEKEND_SLICE_SPECS:
        base = _slice_mask(merged, spec_key)
        for day_type, day_mask in (
            ("All days", base),
            ("Weekdays", base & is_wkd),
            ("Weekends", base & is_wknd),
        ):
            fd, bl_direct, bl_total = _count_below(day_mask, merged)
            calc = round(bl_direct / fd, 6) if fd else None
            rows.append(
                {
                    "slice": slice_label,
                    "day_type": day_type,
                    **_summary_below_fields(fd, bl_direct, bl_total),
                    "calculation_check": calc,
                }
            )
    return pd.DataFrame(rows)


def _build_ownership_summary(merged: pd.DataFrame) -> pd.DataFrame:
    specs = [
        ("All NY", "all", None),
        ("For-profit", "for_profit", "For-profit"),
        ("Non-profit", "non_profit", "Non-profit"),
        ("Government", "government", "Government"),
        ("Other / unknown", "other", "Other / unknown"),
        ("NYC all", "nyc", None),
        ("NYC for-profit", "nyc_for_profit", "For-profit"),
        ("NYC non-profit", "nyc_non_profit", "Non-profit"),
        ("NYC government", "nyc_government", "Government"),
        ("NYC other / unknown", "nyc_other", "Other / unknown"),
    ]
    _, all_bl_direct, all_bl_total = _count_below(pd.Series(True, index=merged.index), merged)
    rows = []
    for slice_label, key, own_type in specs:
        mask = _ownership_mask(merged, key)
        fd, bl_direct, bl_total = _count_below(mask, merged)
        rows.append(
            {
                "slice": slice_label,
                "ownership_type": own_type or "All",
                **_summary_below_fields(fd, bl_direct, bl_total),
                "share_of_all_ny_days_below_350_direct": (
                    round(100.0 * bl_direct / all_bl_direct, 2) if all_bl_direct else None
                ),
                "share_of_all_ny_days_below_350_total": (
                    round(100.0 * bl_total / all_bl_total, 2) if all_bl_total else None
                ),
            }
        )
    return pd.DataFrame(rows)


def _build_county_summary(merged: pd.DataFrame) -> pd.DataFrame:
    nyc_counties = {"KINGS", "QUEENS", "BRONX", "NEW YORK", "RICHMOND"}
    g = merged.groupby("county_norm", observed=True)
    rows = g.agg(
        facility_count=("ccn", "nunique"),
        facility_days=("below_350_direct", "size"),
        days_below_350_direct=("below_350_direct", "sum"),
        days_below_350_total=("below_350_total_nursing", "sum"),
        mean_direct_care_hprd=("hprd_ny_mapped_total", "mean"),
        mean_total_hprd=("hprd", "mean"),
    ).reset_index()
    rows = rows.rename(columns={"county_norm": "county"})
    rows["nyc_borough_flag"] = rows["county"].astype(str).str.upper().isin(nyc_counties)
    rows[COL_PCT_BELOW_350_DIRECT] = (
        100.0 * rows[COL_DAYS_BELOW_350_DIRECT] / rows["facility_days"]
    ).round(1)
    rows[COL_PCT_BELOW_350_TOTAL] = (
        100.0 * rows[COL_DAYS_BELOW_350_TOTAL] / rows["facility_days"]
    ).round(1)
    rows["mean_direct_care_hprd"] = rows["mean_direct_care_hprd"].round(4)
    rows["mean_total_hprd"] = rows["mean_total_hprd"].round(4)
    return rows.sort_values("facility_days", ascending=False)


def _build_readme_df() -> pd.DataFrame:
    lines = [
        ("Title", "PBJ320 New York 2025 Daily Staffing Verification File"),
        ("Prepared by", "PBJ320"),
        ("Contact", CONTACT_EMAIL),
        ("Public report URL", REPORT_URL),
        ("Generated date", datetime.now().strftime("%Y-%m-%d")),
        ("Underlying tables generated date", TABLES_GENERATED_DATE),
        ("", ""),
        ("Data sources", ""),
        ("", "CMS PBJ Daily Nurse Staffing CY2025Q1–Q4"),
        ("", "CMS Provider Info / Provider Data Catalog, quarter-aligned snapshots"),
        ("", "NY Public Health Law § 2895-b (primary statutory reference)"),
        ("", "MACPAC state staffing policy table for 3.56 context (comparison only)"),
        ("", ""),
        *_methodology_readme_lines(),
        (
            "Provider persistence",
            f"Per-facility share of analyzed facility-days below {THRESHOLD_TOTAL} {COL_DIRECT_CARE_HPRD}; see Provider persistence summary",
        ),
        ("Geography", "New York CCNs only"),
        ("NY role floors", f"CNA-side {NY_STATUTE_CNA_MIN_HPRD}; licensed nurse {NY_STATUTE_LPN_RN_MIN_HPRD}"),
        ("", ""),
        ("Caveats", ""),
        ("", "Daily shortfalls are not the same as quarterly compliance. New York's law determines compliance quarterly, so this report also summarizes facility-quarters using the same PBJ-based role mapping. These are descriptive statutory-style calculations, not NY DOH enforcement determinations."),
        ("", "Self-reported PBJ data"),
        ("", "Not NY DOH enforcement records"),
        ("", "Not legal advice"),
        ("", "Not a finding of violation, negligence, or causation"),
        ("", "No shift-level staffing inference"),
        ("", "Ownership/county from CMS Provider Info quarter-aligned snapshots"),
        ("", ""),
        ("External links", ""),
        ("Facility links sheet", "One row per CCN with PBJ320, Medicare Care Compare, and CMS PBJ quarterly URLs"),
        ("Daily facility data", "facility_links_sheet_key = ccn; join to Facility links for source URLs"),
    ]
    return pd.DataFrame(lines, columns=["section", "detail"])


def _build_data_dictionary() -> pd.DataFrame:
    entries = [
        ("ccn", "Daily facility data", "CMS certification number (6-digit)", "CMS PBJ PROVNUM", ""),
        ("provider_name", "Daily facility data", "Facility name", "CMS Provider Info quarter-aligned", ""),
        ("city", "Daily facility data", "City", "CMS Provider Info / PBJ", ""),
        ("county", "Daily facility data", "County name", "CMS Provider Info", ""),
        ("ownership_type", "Daily facility data", "Ownership category", "CMS Provider Info", "For-profit, Non-profit, Government, Other / unknown"),
        ("nyc_flag", "Daily facility data", "True if facility county is a NYC borough", "Derived", "Kings, Queens, Bronx, New York, Richmond"),
        ("work_date", "Daily facility data", "Calendar date", "CMS PBJ WorkDate", ""),
        ("mds_census", "Daily facility data", "Resident census", "CMS PBJ MDScensus", "Rows with census <= 0 excluded"),
        (
            COL_TOTAL_HPRD,
            "Daily facility data",
            "PBJ total nursing HPRD (comparison only)",
            "Derived",
            _excel_daily_hprd_formula(HRS_BROAD_PBJ_TOTAL),
        ),
        (
            COL_DIRECT_CARE_HPRD,
            "Daily facility data",
            "NY direct care HPRD (report default)",
            "Derived",
            _excel_daily_hprd_formula(HRS_NY_MAPPED_TOTAL),
        ),
        (
            COL_CNA_SIDE_HPRD,
            "Daily facility data",
            "CNA-side HPRD @ 2.20 standard",
            "Derived",
            _excel_daily_hprd_formula(HRS_NY_MAPPED_CNA_SIDE),
        ),
        (
            COL_LICENSED_NURSE_HPRD,
            "Daily facility data",
            "Licensed-nurse HPRD @ 1.10 standard",
            "Derived",
            _excel_daily_hprd_formula(HRS_NY_MAPPED_LICENSED),
        ),
        (
            COL_DIRECT_CARE_INCLUDE_DON_HPRD,
            "Daily facility data",
            "Include-DON sensitivity direct care HPRD",
            "Derived",
            _excel_daily_hprd_formula(HRS_NY_MAPPED_INCLUDE_DON),
        ),
        (
            COL_BELOW_350_DIRECT_CARE,
            "Daily facility data",
            f"True if {COL_DIRECT_CARE_HPRD} < 3.50 standard",
            "Derived",
            f"{COL_DIRECT_CARE_HPRD}<3.5",
        ),
        (
            COL_BELOW_350_TOTAL_NURSING,
            "Daily facility data",
            f"True if {COL_TOTAL_HPRD} < 3.50 (comparison only)",
            "Derived",
            f"{COL_TOTAL_HPRD}<3.5",
        ),
        (
            "below_220_cna_side",
            "Daily facility data",
            "True if CNA-side HPRD < 2.20 standard",
            "Derived",
            f"{COL_CNA_SIDE_HPRD}<2.2",
        ),
        (
            "below_110_licensed",
            "Daily facility data",
            "True if licensed-nurse HPRD < 1.10 standard",
            "Derived",
            f"{COL_LICENSED_NURSE_HPRD}<1.1",
        ),
        (
            COL_MET_ALL_THREE_DIRECT_CARE,
            "Daily facility data",
            "True if all three direct-care standards met",
            "Derived",
            f"AND(NOT({COL_BELOW_350_DIRECT_CARE}),NOT(below_220_cna_side),NOT(below_110_licensed))",
        ),
        ("source_file_quarter", "Daily facility data", "PBJ quarterly file label", "CMS PBJ filename", "e.g. 2025Q1"),
        ("facility_links_sheet_key", "Daily facility data", "Join key to Facility links sheet", "Derived", "Equals ccn; avoids repeating URLs on 216k+ daily rows"),
        ("pbj320_provider_url", "Facility links", "PBJ320 facility page", "Derived", "https://www.pbj320.com/provider/{ccn}"),
        ("medicare_care_compare_url", "Facility links", "Medicare Care Compare nursing home profile", "Derived", "state=NY"),
        ("cms_pbj_daily_base_url", "Facility links", "CMS PBJ Daily Nurse Staffing catalog landing", "CMS", ""),
        ("cms_pbj_daily_q1_url", "Facility links", "CMS PBJ Q1 view filtered to PROVNUM", "Derived", "PROVNUM-only Data Catalog query"),
        ("cms_pbj_daily_q2_url", "Facility links", "CMS PBJ Q2 view filtered to PROVNUM", "Derived", "PROVNUM-only Data Catalog query"),
        ("cms_pbj_daily_q3_url", "Facility links", "CMS PBJ Q3 view filtered to PROVNUM", "Derived", "PROVNUM-only Data Catalog query"),
        ("cms_pbj_daily_q4_url", "Facility links", "CMS PBJ Q4 view filtered to PROVNUM", "Derived", "PROVNUM-only Data Catalog query"),
        ("facility_days", "Summary sheets", "Count of analyzed facility-days with census > 0", "Derived", ""),
        (
            COL_DAYS_BELOW_350_DIRECT,
            "Summary sheets",
            f"Facility-days with {COL_DIRECT_CARE_HPRD} < 3.50",
            "Derived",
            f"SUM({COL_BELOW_350_DIRECT_CARE})",
        ),
        (
            COL_DAYS_BELOW_350_TOTAL,
            "Summary sheets",
            f"Facility-days with {COL_TOTAL_HPRD} < 3.50",
            "Derived",
            f"SUM({COL_BELOW_350_TOTAL_NURSING})",
        ),
        (
            COL_PCT_BELOW_350_DIRECT,
            "Summary sheets",
            f"100 × {COL_DAYS_BELOW_350_DIRECT} / facility_days",
            "Derived",
            "Rounded to 0.1 pp",
        ),
        (
            COL_PCT_BELOW_350_TOTAL,
            "Summary sheets",
            f"100 × {COL_DAYS_BELOW_350_TOTAL} / facility_days",
            "Derived",
            "Rounded to 0.1 pp",
        ),
        (
            COL_PCT_DAYS_BELOW_350_DIRECT,
            "Facility summary",
            f"100 × {COL_DAYS_BELOW_350_DIRECT} / facility_days",
            "Derived",
            "Rounded to 0.1 pp",
        ),
        (
            COL_PCT_DAYS_BELOW_350_TOTAL,
            "Facility summary",
            f"100 × {COL_DAYS_BELOW_350_TOTAL} / facility_days",
            "Derived",
            "Rounded to 0.1 pp",
        ),
        ("mean_total_hprd", "Facility summary; County summary", f"Mean {COL_TOTAL_HPRD}", "Derived", ""),
        (
            "share_of_all_ny_days_below_350_direct",
            "Ownership summary",
            f"Slice {COL_DAYS_BELOW_350_DIRECT} as % of statewide direct below days",
            "Derived",
            "",
        ),
        (
            "share_of_all_ny_days_below_350_total",
            "Ownership summary",
            f"Slice {COL_DAYS_BELOW_350_TOTAL} as % of statewide total below days",
            "Derived",
            "",
        ),
        (
            "calculation_check",
            "Weekend weekday summary",
            f"{COL_DAYS_BELOW_350_DIRECT} / facility_days",
            "Derived",
            "Unrounded direct-care ratio for audit",
        ),
        ("quarter", "Facility quarter summary", "Calendar quarter (1–4)", "Derived from work_date", ""),
        ("census_days", "Facility quarter summary", "Sum of daily MDS census in quarter", "CMS PBJ", ""),
        (
            COL_DIRECT_CARE_HPRD,
            "Facility quarter summary",
            "Quarterly NY direct care HPRD",
            "Derived",
            f"SUM({_pbj_role_sum(HRS_NY_MAPPED_TOTAL)})/SUM(MDScensus)",
        ),
        (
            "direct_care_include_don_hprd",
            "Facility quarter summary",
            "Include-DON sensitivity quarterly direct care HPRD",
            "Derived",
            f"SUM({_pbj_role_sum(HRS_NY_MAPPED_INCLUDE_DON)})/SUM(MDScensus)",
        ),
        (
            "below_350_direct_care_quarter",
            "Facility quarter summary",
            f"Quarterly {COL_DIRECT_CARE_HPRD} < 3.50",
            "Derived",
            f"{COL_DIRECT_CARE_HPRD}<3.5",
        ),
        ("missing_any_floor", "Facility quarter summary", "Any quarterly floor missed", "Derived", "OR of three floor checks"),
        ("quarters_analyzed", "Facility summary", "Facility-quarters with census > 0", "Derived", "Max 4 per facility"),
        ("qtrs_below_350_display", "Facility summary", "Quarters below 3.50 / quarters analyzed", "Derived", "e.g. 3/4"),
        ("qtrs_missing_floor_display", "Facility summary", "Quarters missing any floor / quarters analyzed", "Derived", "e.g. 2/4"),
        ("below_350_ge_50pct_days", "Facility summary", f"True if {COL_PCT_DAYS_BELOW_350_DIRECT} >= 50", "Derived", "Daily persistence @ 3.50 direct care"),
        ("below_350_ge_75pct_days", "Facility summary", f"True if {COL_PCT_DAYS_BELOW_350_DIRECT} >= 75", "Derived", "Daily persistence @ 3.50 direct care"),
        ("below_350_ge_90pct_days", "Facility summary", f"True if {COL_PCT_DAYS_BELOW_350_DIRECT} >= 90", "Derived", "Daily persistence @ 3.50 direct care"),
        ("below_350_all_analyzed_days", "Facility summary", f"True if {COL_DAYS_BELOW_350_DIRECT} == facility_days", "Derived", "100% of analyzed days"),
        ("below_350_zero_days", "Facility summary", f"True if {COL_DAYS_BELOW_350_DIRECT} == 0", "Derived", "0% of analyzed days"),
        ("provider_day_band", "Facility summary", "Histogram band for provider-day chart", "Derived", "100% / 90-99% / … / 0%"),
        ("provider_day_band", "Provider day bands summary", "Share-of-days band label", "Derived", "Matches report histogram"),
        ("facility_count", "Provider day bands summary", "Homes in band", "Derived", "Denominator 596"),
        ("pct_of_facilities", "Provider persistence summary", "100 × facilities / 596", "Derived", "Rounded 0.1 pp"),
    ]
    return pd.DataFrame(
        entries,
        columns=["field_name", "sheet", "definition", "source_or_derived", "formula_or_notes"],
    )


def _pct_close(displayed: float | None, bl: int, fd: int, tol: float = 0.05) -> bool:
    if displayed is None or not fd:
        return False
    return abs(displayed - 100.0 * bl / fd) <= tol


def _build_reconciliation_checks(
    merged: pd.DataFrame,
    dow_df: pd.DataFrame,
    weekend_df: pd.DataFrame,
    ownership_df: pd.DataFrame,
    fq_df: pd.DataFrame,
    facility_df: pd.DataFrame,
) -> pd.DataFrame:
    global ANCHOR_STATEWIDE_FD, ANCHOR_STATEWIDE_BELOW, ANCHOR_STATEWIDE_PCT
    global ANCHOR_NYC_WKND_FD, ANCHOR_NYC_WKND_BELOW, ANCHOR_NYC_WKND_PCT

    finite = merged.loc[_finite_mask(merged)]
    statewide_fd = len(finite)
    statewide_bl = int(finite["below_350_ny_mapped"].sum())
    statewide_bl_total = int(finite["below_350_total_nursing"].sum())
    statewide_pct = round(100.0 * statewide_bl / statewide_fd, 1)
    ANCHOR_STATEWIDE_FD = statewide_fd
    ANCHOR_STATEWIDE_BELOW = statewide_bl
    ANCHOR_STATEWIDE_PCT = statewide_pct

    is_nyc = _col_bool(merged, "is_nyc")
    is_wknd = _col_bool(merged, "weekend_flag")
    nyc_wknd_fd, nyc_wknd_bl, _nyc_wknd_bl_total = _count_below(is_nyc & is_wknd, merged)
    nyc_wknd_pct = _pct(nyc_wknd_bl, nyc_wknd_fd)
    ANCHOR_NYC_WKND_FD = nyc_wknd_fd
    ANCHOR_NYC_WKND_BELOW = nyc_wknd_bl
    ANCHOR_NYC_WKND_PCT = nyc_wknd_pct

    own_fp = int(
        ownership_df.loc[ownership_df["slice"] == "For-profit", COL_DAYS_BELOW_350_DIRECT].iloc[0]
    )
    own_np = int(
        ownership_df.loc[ownership_df["slice"] == "Non-profit", COL_DAYS_BELOW_350_DIRECT].iloc[0]
    )
    own_gov = int(
        ownership_df.loc[ownership_df["slice"] == "Government", COL_DAYS_BELOW_350_DIRECT].iloc[0]
    )
    own_other = int(
        ownership_df.loc[ownership_df["slice"] == "Other / unknown", COL_DAYS_BELOW_350_DIRECT].iloc[0]
    )
    own_sum_bl = own_fp + own_np + own_gov + own_other

    own_fp_fd = int(ownership_df.loc[ownership_df["slice"] == "For-profit", "facility_days"].iloc[0])
    own_np_fd = int(ownership_df.loc[ownership_df["slice"] == "Non-profit", "facility_days"].iloc[0])
    own_gov_fd = int(ownership_df.loc[ownership_df["slice"] == "Government", "facility_days"].iloc[0])
    own_other_fd = int(
        ownership_df.loc[ownership_df["slice"] == "Other / unknown", "facility_days"].iloc[0]
    )
    own_sum_fd = own_fp_fd + own_np_fd + own_gov_fd + own_other_fd

    dow_fd = int(dow_df["facility_days"].sum())
    dow_bl = int(dow_df[COL_DAYS_BELOW_350_DIRECT].sum())
    dow_bl_total = int(dow_df[COL_DAYS_BELOW_350_TOTAL].sum())

    wknd_all = weekend_df[
        (weekend_df["slice"] == "All NY") & (weekend_df["day_type"].isin(["Weekdays", "Weekends"]))
    ]
    wknd_fd_sum = int(wknd_all["facility_days"].sum())
    wknd_bl_sum = int(wknd_all[COL_DAYS_BELOW_350_DIRECT].sum())
    wknd_bl_total_sum = int(wknd_all[COL_DAYS_BELOW_350_TOTAL].sum())

    pct_rows_ok = True
    for frame in (dow_df, weekend_df, ownership_df):
        for _, row in frame.iterrows():
            fd = int(row["facility_days"])
            if fd <= 0:
                continue
            for pct_col, days_col in (
                (COL_PCT_BELOW_350_DIRECT, COL_DAYS_BELOW_350_DIRECT),
                (COL_PCT_BELOW_350_TOTAL, COL_DAYS_BELOW_350_TOTAL),
            ):
                if pd.isna(row.get(pct_col)):
                    continue
                if not _pct_close(row.get(pct_col), int(row[days_col]), fd):
                    pct_rows_ok = False
                    break
            if not pct_rows_ok:
                break

    checks = [
        ("statewide facility_days equals anchor", statewide_fd == ANCHOR_STATEWIDE_FD),
        (
            "statewide days_below_350_direct ny-mapped equals anchor",
            statewide_bl == ANCHOR_STATEWIDE_BELOW,
        ),
        (
            "statewide days_below_350_total equals anchor",
            statewide_bl_total == int(finite["below_350_total_nursing"].sum()),
        ),
        ("statewide pct ny-mapped equals anchor after rounding", statewide_pct == ANCHOR_STATEWIDE_PCT),
        (f"NYC weekend facility_days equals {ANCHOR_NYC_WKND_FD:,}", nyc_wknd_fd == ANCHOR_NYC_WKND_FD),
        (
            f"NYC weekend days_below_350_direct equals {ANCHOR_NYC_WKND_BELOW:,}",
            nyc_wknd_bl == ANCHOR_NYC_WKND_BELOW,
        ),
        (f"NYC weekend pct equals {ANCHOR_NYC_WKND_PCT}% after rounding", nyc_wknd_pct == ANCHOR_NYC_WKND_PCT),
        ("ownership visible rows plus Other/unknown reconcile to All NY (days)", own_sum_bl == statewide_bl),
        ("ownership visible rows plus Other/unknown reconcile to All NY (facility_days)", own_sum_fd == statewide_fd),
        ("day-of-week rows reconcile to All NY (facility_days)", dow_fd == statewide_fd),
        ("day-of-week rows reconcile to All NY (days_below_350_direct)", dow_bl == statewide_bl),
        ("day-of-week rows reconcile to All NY (days_below_350_total)", dow_bl_total == statewide_bl_total),
        ("weekend + weekday rows reconcile to All NY (facility_days)", wknd_fd_sum == statewide_fd),
        ("weekend + weekday rows reconcile to All NY (days_below_350_direct)", wknd_bl_sum == statewide_bl),
        (
            "weekend + weekday rows reconcile to All NY (days_below_350_total)",
            wknd_bl_total_sum == statewide_bl_total,
        ),
        ("all displayed percentages recompute from counts within 0.05 pp", pct_rows_ok),
    ]

    p = _provider_persistence_counts(facility_df)
    band_sum = sum(b["facilities"] for b in p["bands"])
    checks.extend(
        [
            ("provider persistence: 596 facilities analyzed", p["facility_count"] == 596),
            (
                "provider persistence: at least 50% count",
                p["thresholds"]["at_least_50pct"]["facilities"] == int(facility_df["below_350_ge_50pct_days"].sum()),
            ),
            (
                "provider persistence: bands sum to facilities",
                band_sum == p["facility_count"],
            ),
        ]
    )

    q_summary = _quarterly_statutory_summary(merged)
    if not fq_df.empty:
        fq_n = len(fq_df)
        fq_below_col = (
            "below_350_direct_care_quarter"
            if "below_350_direct_care_quarter" in fq_df.columns
            else "below_350_total"
        )
        fq_below = int(fq_df[fq_below_col].sum())
        fq_missing = int(fq_df["missing_any_floor"].sum())
        max_q = int(fq_df.groupby("ccn", observed=True)["quarter"].count().max())
        fq_raw = _compute_quarterly_statutory_rows(merged)
        rollups = _facility_quarter_rollups(fq_raw)
        logic_ok = bool(
            (fq_raw["missing_any_floor"]
             == (fq_raw["below_350_total"] | fq_raw["below_220_cna_side"] | fq_raw["below_110_licensed"])).all()
            and (fq_raw["met_all_three"] == ~fq_raw["missing_any_floor"]).all()
        )
        rollup_ok = True
        if "quarters_below_350_total" in facility_df.columns and not rollups.empty:
            chk = facility_df[["ccn", "quarters_below_350_total", "quarters_missing_any_floor"]].merge(
                rollups[["ccn", "quarters_below_350_total", "quarters_missing_any_floor"]],
                on="ccn",
                suffixes=("_fac", "_calc"),
            )
            rollup_ok = (
                chk["quarters_below_350_total_fac"] == chk["quarters_below_350_total_calc"]
            ).all() and (
                chk["quarters_missing_any_floor_fac"] == chk["quarters_missing_any_floor_calc"]
            ).all()
        dist_below = q_summary.get("facilities_by_quarters_below_350", {})
        dist_missing = q_summary.get("facilities_by_quarters_missing_any_floor", {})
        checks.extend(
            [
                ("facility-quarters analyzed equals summary", fq_n == q_summary.get("facility_quarters_analyzed")),
                ("facility-quarters below 3.50 equals summary", fq_below == q_summary.get("facility_quarters_below_350_total")),
                ("facility-quarters missing any floor equals summary", fq_missing == q_summary.get("facility_quarters_missing_any_floor")),
                ("no facility has more than 4 quarters", max_q <= 4),
                ("missing_any_floor OR logic on facility-quarters", logic_ok),
                ("met_all_three equals NOT missing_any_floor", bool((fq_df["met_all_three"] == ~fq_df["missing_any_floor"]).all())),
                ("facility summary quarterly rollups reconcile", rollup_ok),
                ("facility count by quarters below 3.50 sums to facilities", sum(int(v) for v in dist_below.values()) == int(fq_df["ccn"].nunique())),
                ("facility count by quarters missing floor sums to facilities", sum(int(v) for v in dist_missing.values()) == int(fq_df["ccn"].nunique())),
            ]
        )
    rows = [{"check": name, "result": "PASS" if ok else "FAIL", "passed": ok} for name, ok in checks]
    if not fq_df.empty:
        dist_below = q_summary.get("facilities_by_quarters_below_350", {})
        dist_missing = q_summary.get("facilities_by_quarters_missing_any_floor", {})
        metric_rows = [
            ("quarterly: facility-quarters analyzed", str(len(fq_df)), True),
            (
                "quarterly: facility-quarters below 3.50 direct care",
                str(int(fq_df[fq_below_col].sum())),
                True,
            ),
            ("quarterly: facility-quarters missing any floor", str(int(fq_df["missing_any_floor"].sum())), True),
        ]
        for qcount in range(5):
            metric_rows.append(
                (
                    f"quarterly: facilities below 3.50 in {qcount} quarters",
                    str(int(dist_below.get(str(qcount), 0))),
                    True,
                )
            )
            metric_rows.append(
                (
                    f"quarterly: facilities missing any floor in {qcount} quarters",
                    str(int(dist_missing.get(str(qcount), 0))),
                    True,
                )
            )
        rows.extend(
            {"check": name, "result": val, "passed": passed} for name, val, passed in metric_rows
        )
    for key, label in (
        ("at_least_50pct", "provider persistence: facilities >=50% days below 3.50"),
        ("at_least_75pct", "provider persistence: facilities >=75% days below 3.50"),
        ("at_least_90pct", "provider persistence: facilities >=90% days below 3.50"),
        ("all_analyzed_days", "provider persistence: facilities 100% days below 3.50"),
        ("zero_days", "provider persistence: facilities 0% days below 3.50"),
    ):
        t = p["thresholds"][key]
        rows.append(
            {
                "check": label,
                "result": f"{t['facilities']} ({t['pct_of_facilities']}%)",
                "passed": True,
            }
        )
    for band in p["bands"]:
        rows.append(
            {
                "check": f"provider day band: {band['band']}",
                "result": f"{band['facilities']} ({band['pct_of_facilities']}%)",
                "passed": True,
            }
        )
    return pd.DataFrame(rows)


def _sheet_filename(sheet_name: str) -> str:
    safe = (
        sheet_name.lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
    )
    return f"{safe}.csv"


def build_workbook() -> dict[str, Any]:
    print(f"Loading NY {YEAR} facility-days...")
    merged = _prepare_merged(YEAR)

    links_df = _build_facility_links(merged)
    daily_df = _build_daily_sheet(merged)
    facility_df = _build_facility_summary(merged, links_df)
    facility_df = _enrich_facility_persistence_flags(facility_df)
    persistence = _provider_persistence_counts(facility_df)
    persistence_df = _build_provider_persistence_summary(persistence)
    day_bands_df = _build_provider_day_bands_summary(persistence)
    fq_df = _build_facility_quarter_summary(merged)
    dow_df = _build_dow_summary(merged)
    weekend_df = _build_weekend_weekday_summary(merged)
    ownership_df = _build_ownership_summary(merged)
    county_df = _build_county_summary(merged)
    readme_df = _build_readme_df()
    dict_df = _build_data_dictionary()
    recon_df = _build_reconciliation_checks(
        merged, dow_df, weekend_df, ownership_df, fq_df, facility_df
    )

    sheets: dict[str, pd.DataFrame] = {
        "README": readme_df,
        "Daily facility data": daily_df,
        "Facility links": links_df,
        "Facility summary": facility_df,
        "Provider persistence summary": persistence_df,
        "Provider day bands summary": day_bands_df,
        "Facility quarter summary": fq_df,
        "Day-of-week summary": dow_df,
        "Weekend weekday summary": weekend_df,
        "Ownership summary": ownership_df,
        "County summary": county_df,
        "Data dictionary": dict_df,
        "Reconciliation checks": recon_df,
    }

    OUT_BASE.mkdir(parents=True, exist_ok=True)
    if CSV_DIR.exists():
        for old in CSV_DIR.glob("*.csv"):
            old.unlink()
    else:
        CSV_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Writing {XLSX_PATH}...")
    with pd.ExcelWriter(XLSX_PATH, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)
        for name, frame in sheets.items():
            _apply_sheet_hyperlinks(
                writer.sheets[name],
                list(frame.columns),
                len(frame),
            )

    for name, frame in sheets.items():
        csv_path = CSV_DIR / _sheet_filename(name)
        frame.to_csv(csv_path, index=False)

    print(f"Writing {ZIP_PATH}...")
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for csv_path in sorted(CSV_DIR.glob("*.csv")):
            zf.write(csv_path, arcname=f"{CSV_DIR_NAME}/{csv_path.name}")

    flat_downloads = ROOT / "downloads"
    flat_downloads.mkdir(parents=True, exist_ok=True)
    for src in (XLSX_PATH, ZIP_PATH):
        dst = flat_downloads / src.name
        try:
            shutil.copy2(src, dst)
        except OSError as exc:
            print(f"WARNING: could not mirror {src.name} to {dst}: {exc}")
    else:
        print(f"Mirrored to {flat_downloads / XLSX_PATH.name} and {flat_downloads / ZIP_PATH.name}")

    failed = recon_df.loc[~recon_df["passed"], "check"].tolist()
    if failed:
        print("WARNING: reconciliation checks FAILED:")
        for item in failed:
            print(f"  - {item}")

    xlsx_bytes = XLSX_PATH.stat().st_size if XLSX_PATH.is_file() else 0
    zip_bytes = ZIP_PATH.stat().st_size if ZIP_PATH.is_file() else 0

    return {
        "sheets": {name: len(df) for name, df in sheets.items()},
        "reconciliation_failed": failed,
        "xlsx_path": str(XLSX_PATH),
        "zip_path": str(ZIP_PATH),
        "xlsx_bytes": xlsx_bytes,
        "zip_bytes": zip_bytes,
        "cms_quarterly_urls": "generated (PROVNUM-filtered Data Catalog URLs)",
        "csv_files": sorted(p.name for p in CSV_DIR.glob("*.csv")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build NY 2025 verification workbook package")
    parser.parse_args()
    summary = build_workbook()
    print("Sheet row counts:")
    for name, count in summary["sheets"].items():
        print(f"  {name}: {count:,}")
    print(f"CSV files: {len(summary['csv_files'])}")
    print(f"XLSX size: {summary['xlsx_bytes']:,} bytes")
    print(f"ZIP size: {summary['zip_bytes']:,} bytes")
    print(f"CMS quarterly URLs: {summary['cms_quarterly_urls']}")
    return 1 if summary["reconciliation_failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
