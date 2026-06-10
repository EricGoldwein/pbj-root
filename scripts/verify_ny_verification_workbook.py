#!/usr/bin/env python3
"""QA gate for NY 2025 verification workbook + CSV package."""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_BASE = ROOT / "public" / "downloads"
XLSX = OUT_BASE / "PBJ320_NY_2025_daily_staffing_verification_file.xlsx"
CSV_DIR = OUT_BASE / "PBJ320_NY_2025_daily_staffing_verification_csvs"
ZIP_PATH = OUT_BASE / "PBJ320_NY_2025_daily_staffing_verification_csvs.zip"

REQUIRED_SHEETS = (
    "README",
    "Daily facility data",
    "Facility links",
    "Facility summary",
    "Provider persistence summary",
    "Provider day bands summary",
    "Facility quarter summary",
    "Day-of-week summary",
    "Weekend weekday summary",
    "Ownership summary",
    "County summary",
    "Data dictionary",
    "Reconciliation checks",
)

SEAGATE_CCN = "335513"
SEAGATE_PBJ320 = f"https://www.pbj320.com/provider/{SEAGATE_CCN}"
SEAGATE_CARE_COMPARE = (
    f"https://www.medicare.gov/care-compare/details/nursing-home/"
    f"{SEAGATE_CCN}/view-all/?state=NY"
)

# Prior package without Facility links sheet (~25 MB xlsx, ~8 MB zip)
MAX_XLSX_BYTES = 40_000_000
MAX_ZIP_BYTES = 15_000_000

FORBIDDEN_COLUMNS = (
    "employee",
    "ssn",
    "incident",
    "attorney",
    "client_note",
    "provnum",
    "shift_id",
    "window_start",
    "window_end",
)

README_REQUIRED_PHRASES = (
    "CMS PBJ Daily Nurse Staffing",
    "Provider Data Catalog",
    "facility-day",
    "Not legal advice",
    "Not NY DOH enforcement",
    "Strict threshold rule",
    "Daily shortfalls are not the same as quarterly compliance",
    "statutory-style calculations",
    "direct_care_hprd",
    "total_hprd (Excel)",
)

ANCHOR_STATEWIDE_FD = 216_134
ANCHOR_STATEWIDE_BELOW = 123_428
ANCHOR_NYC_WKND_FD = 16_978
ANCHOR_NYC_WKND_BELOW = 14_162
ANCHOR_PROVIDER_PERSISTENCE = {
    "at_least_50pct": 348,
    "at_least_75pct": 228,
    "at_least_90pct": 158,
    "all_analyzed_days": 58,
    "zero_days": 21,
}


def _sheet_csv_name(sheet: str) -> str:
    return (
        sheet.lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
        + ".csv"
    )


def verify() -> list[str]:
    errors: list[str] = []

    flat_xlsx = ROOT / "downloads" / XLSX.name
    flat_zip = ROOT / "downloads" / ZIP_PATH.name
    if not XLSX.is_file():
        errors.append(f"missing workbook: {XLSX}")
    if not ZIP_PATH.is_file():
        errors.append(f"missing zip: {ZIP_PATH}")
    if not flat_xlsx.is_file():
        errors.append(f"missing deploy mirror: {flat_xlsx}")
    if not flat_zip.is_file():
        errors.append(f"missing deploy mirror: {flat_zip}")
    if not CSV_DIR.is_dir():
        errors.append(f"missing csv dir: {CSV_DIR}")

    if errors:
        return errors

    xl = pd.ExcelFile(XLSX)
    for sheet in REQUIRED_SHEETS:
        if sheet not in xl.sheet_names:
            errors.append(f"missing sheet: {sheet}")

    for sheet in REQUIRED_SHEETS:
        csv_name = _sheet_csv_name(sheet)
        if not (CSV_DIR / csv_name).is_file():
            errors.append(f"missing csv: {csv_name}")

    with zipfile.ZipFile(ZIP_PATH) as zf:
        names = zf.namelist()
        for sheet in REQUIRED_SHEETS:
            csv_name = _sheet_csv_name(sheet)
            arc = f"PBJ320_NY_2025_daily_staffing_verification_csvs/{csv_name}"
            if arc not in names:
                errors.append(f"zip missing: {arc}")

    xlsx_size = XLSX.stat().st_size
    zip_size = ZIP_PATH.stat().st_size
    if xlsx_size > MAX_XLSX_BYTES:
        errors.append(f"xlsx too large: {xlsx_size:,} bytes (max {MAX_XLSX_BYTES:,})")
    if zip_size > MAX_ZIP_BYTES:
        errors.append(f"zip too large: {zip_size:,} bytes (max {MAX_ZIP_BYTES:,})")

    daily = pd.read_excel(XLSX, sheet_name="Daily facility data", nrows=5000)
    if "facility_links_sheet_key" not in daily.columns:
        errors.append("daily sheet missing facility_links_sheet_key")
    if "pbj320_provider_url" in daily.columns:
        errors.append("daily sheet should not repeat pbj320_provider_url (use Facility links)")
    for col in daily.columns:
        low = str(col).lower()
        for bad in FORBIDDEN_COLUMNS:
            if bad in low:
                errors.append(f"forbidden column in daily sheet: {col}")

    links = pd.read_excel(XLSX, sheet_name="Facility links")
    required_link_cols = (
        "ccn",
        "pbj320_provider_url",
        "medicare_care_compare_url",
        "cms_pbj_daily_base_url",
        "cms_pbj_daily_q1_url",
        "cms_pbj_daily_q2_url",
        "cms_pbj_daily_q3_url",
        "cms_pbj_daily_q4_url",
    )
    for col in required_link_cols:
        if col not in links.columns:
            errors.append(f"Facility links missing column: {col}")
    if not links.empty and "pbj320_provider_url" in links.columns:
        missing_pbj = links["pbj320_provider_url"].isna() | ~links[
            "pbj320_provider_url"
        ].astype(str).str.startswith("http")
        if missing_pbj.any():
            errors.append(f"{int(missing_pbj.sum())} CCNs missing PBJ320 URL")
        missing_mc = links["medicare_care_compare_url"].isna() | ~links[
            "medicare_care_compare_url"
        ].astype(str).str.startswith("http")
        if missing_mc.any():
            errors.append(f"{int(missing_mc.sum())} CCNs missing Care Compare URL")

    seagate_key = SEAGATE_CCN.zfill(6)
    seagate_rows = links.loc[links["ccn"].astype(str).str.zfill(6) == seagate_key]
    if seagate_rows.empty:
        seagate_rows = links.loc[links["ccn"].astype(str).str.lstrip("0") == SEAGATE_CCN]
    if seagate_rows.empty:
        errors.append(f"Facility links missing Seagate CCN {SEAGATE_CCN}")
    else:
        row = seagate_rows.iloc[0]
        if str(row["pbj320_provider_url"]).strip() != SEAGATE_PBJ320:
            errors.append(
                f"Seagate PBJ320 URL mismatch: {row['pbj320_provider_url']!r}"
            )
        if str(row["medicare_care_compare_url"]).strip() != SEAGATE_CARE_COMPARE:
            errors.append(
                f"Seagate Care Compare URL mismatch: {row['medicare_care_compare_url']!r}"
            )
        for q in (1, 2, 3, 4):
            qcol = f"cms_pbj_daily_q{q}_url"
            qurl = str(row.get(qcol, ""))
            if not qurl.startswith(f"https://data.cms.gov/"):
                errors.append(f"Seagate {qcol} invalid")
            if SEAGATE_CCN not in qurl and seagate_key not in qurl:
                errors.append(f"Seagate {qcol} missing CCN filter")

    facility = pd.read_excel(XLSX, sheet_name="Facility summary", nrows=10)
    for col in ("pbj320_provider_url", "medicare_care_compare_url", "cms_pbj_daily_base_url"):
        if col not in facility.columns:
            errors.append(f"facility summary missing {col}")

    readme = pd.read_excel(XLSX, sheet_name="README")
    readme_text = " ".join(readme.astype(str).fillna("").values.flatten())
    for phrase in README_REQUIRED_PHRASES:
        if phrase.lower() not in readme_text.lower():
            errors.append(f"README missing phrase: {phrase}")

    recon = pd.read_excel(XLSX, sheet_name="Reconciliation checks")
    if "result" not in recon.columns:
        errors.append("reconciliation sheet missing result column")
    elif "passed" in recon.columns:
        fails = recon.loc[~recon["passed"].astype(bool)]
        for _, row in fails.iterrows():
            errors.append(f"reconciliation FAIL: {row.get('check', row)}")
    else:
        fails = recon.loc[recon["result"].astype(str).str.upper() != "PASS"]
        for _, row in fails.iterrows():
            errors.append(f"reconciliation FAIL: {row.get('check', row)}")

    fq = pd.read_excel(XLSX, sheet_name="Facility quarter summary")
    fq_required = (
        "ccn",
        "quarter",
        "census_days",
        "direct_care_hprd",
        "below_350_direct_care_quarter",
        "below_220_cna_side",
        "below_110_licensed",
        "missing_any_floor",
        "met_all_three",
    )
    for col in fq_required:
        if col not in fq.columns:
            errors.append(f"Facility quarter summary missing column: {col}")
    if not fq.empty:
        max_q = int(fq.groupby("ccn")["quarter"].count().max())
        if max_q > 4:
            errors.append(f"facility has more than 4 quarters: max={max_q}")
        logic = (
            fq["missing_any_floor"]
            == (
                fq["below_350_direct_care_quarter"]
                | fq["below_220_cna_side"]
                | fq["below_110_licensed"]
            )
        ).all()
        if not logic:
            errors.append("missing_any_floor != OR(three below flags) on facility-quarters")
        if not (fq["met_all_three"] == ~fq["missing_any_floor"]).all():
            errors.append("met_all_three != NOT missing_any_floor on facility-quarters")

    facility_full = pd.read_excel(XLSX, sheet_name="Facility summary")
    if len(facility_full) != 596:
        errors.append(f"Facility summary row count {len(facility_full)} != 596")
    persist_cols = (
        "below_350_ge_50pct_days",
        "below_350_ge_75pct_days",
        "below_350_ge_90pct_days",
        "below_350_all_analyzed_days",
        "below_350_zero_days",
        "provider_day_band",
    )
    for col in persist_cols:
        if col not in facility_full.columns:
            errors.append(f"Facility summary missing persistence column: {col}")
    if all(c in facility_full.columns for c in persist_cols):
        counts = {
            "at_least_50pct": int(facility_full["below_350_ge_50pct_days"].sum()),
            "at_least_75pct": int(facility_full["below_350_ge_75pct_days"].sum()),
            "at_least_90pct": int(facility_full["below_350_ge_90pct_days"].sum()),
            "all_analyzed_days": int(facility_full["below_350_all_analyzed_days"].sum()),
            "zero_days": int(facility_full["below_350_zero_days"].sum()),
        }
        for key, expected in ANCHOR_PROVIDER_PERSISTENCE.items():
            if counts[key] != expected:
                errors.append(
                    f"provider persistence {key}: {counts[key]} != anchor {expected}"
                )
        band_sum = int(facility_full["provider_day_band"].value_counts().sum())
        if band_sum != 596:
            errors.append(f"provider_day_band rows {band_sum} != 596")

    persist_summary = pd.read_excel(XLSX, sheet_name="Provider persistence summary")
    if persist_summary.empty:
        errors.append("Provider persistence summary is empty")

    facility_full = pd.read_excel(XLSX, sheet_name="Facility summary")
    if "qtrs_below_350_display" in facility_full.columns:
        for _, row in facility_full.iterrows():
            qa = int(row["quarters_analyzed"])
            qb = int(row["quarters_below_350_total"])
            expected = f"{qb}/{qa}"
            if str(row["qtrs_below_350_display"]) != expected:
                errors.append(f"display mismatch ccn {row['ccn']}: {row['qtrs_below_350_display']} != {expected}")
            if qa < 4 and str(row["qtrs_below_350_display"]).endswith("/4"):
                errors.append(f"ccn {row['ccn']} shows x/4 with only {qa} analyzed quarters")
        at_four = facility_full[facility_full["quarters_below_350_total"] == 4]
        if not at_four.empty and not (at_four["quarters_analyzed"] == 4).all():
            errors.append("facilities with 4 quarters below include partial-year facilities")

    if "qtrs_below_350_display" in facility_full.columns and not fq.empty:
        roll = (
            fq.groupby("ccn", observed=True)
            .agg(
                quarters_below_350_total=("below_350_direct_care_quarter", "sum"),
                quarters_missing_any_floor=("missing_any_floor", "sum"),
            )
            .reset_index()
        )
        chk = facility_full[["ccn", "quarters_below_350_total", "quarters_missing_any_floor"]].merge(
            roll,
            on="ccn",
            suffixes=("_fac", "_calc"),
        )
        if not (chk["quarters_below_350_total_fac"] == chk["quarters_below_350_total_calc"]).all():
            errors.append("facility summary quarters_below_350_total does not reconcile")
        if not (chk["quarters_missing_any_floor_fac"] == chk["quarters_missing_any_floor_calc"]).all():
            errors.append("facility summary quarters_missing_any_floor does not reconcile")

    q_metric = recon.loc[recon["check"].astype(str).str.startswith("quarterly:")]
    q_summary_row = q_metric.loc[q_metric["check"] == "quarterly: facility-quarters analyzed"]
    if q_summary_row.empty:
        errors.append("reconciliation missing quarterly: facility-quarters analyzed")
    elif not fq.empty:
        expected = str(len(fq))
        actual = str(q_summary_row.iloc[0]["result"])
        if actual != expected:
            errors.append(
                f"quarterly summary facility-quarters analyzed {actual} != facility quarter rows {expected}"
            )

    weekend = pd.read_excel(XLSX, sheet_name="Weekend weekday summary")
    nyc_wknd = weekend[
        (weekend["slice"] == "NYC five boroughs") & (weekend["day_type"] == "Weekends")
    ]
    if nyc_wknd.empty:
        errors.append("NYC weekend row missing in weekend summary")
    else:
        row = nyc_wknd.iloc[0]
        if int(row["facility_days"]) != ANCHOR_NYC_WKND_FD:
            errors.append(
                f"NYC weekend facility_days {row['facility_days']} != {ANCHOR_NYC_WKND_FD}"
            )
        if int(row["days_below_350_direct"]) != ANCHOR_NYC_WKND_BELOW:
            errors.append(
                f"NYC weekend days_below_350_direct {row['days_below_350_direct']} != {ANCHOR_NYC_WKND_BELOW}"
            )
        pct = float(row["pct_below_350_direct"])
        if abs(pct - 83.4) > 0.05:
            errors.append(f"NYC weekend pct {pct} != 83.4")

    ownership = pd.read_excel(XLSX, sheet_name="Ownership summary")
    all_row = ownership.loc[ownership["slice"] == "All NY"].iloc[0]
    if int(all_row["facility_days"]) != ANCHOR_STATEWIDE_FD:
        errors.append(f"statewide facility_days {all_row['facility_days']} != {ANCHOR_STATEWIDE_FD}")
    if int(all_row["days_below_350_direct"]) != ANCHOR_STATEWIDE_BELOW:
        errors.append(
            f"statewide days_below_350_direct {all_row['days_below_350_direct']} != {ANCHOR_STATEWIDE_BELOW}"
        )

    visible = ownership.loc[
        ownership["slice"].isin(
            ["For-profit", "Non-profit", "Government", "Other / unknown"]
        )
    ]
    if int(visible["facility_days"].sum()) != int(all_row["facility_days"]):
        errors.append("ownership facility_days do not reconcile to All NY")
    if int(visible["days_below_350_direct"].sum()) != int(all_row["days_below_350_direct"]):
        errors.append("ownership days_below_350_direct do not reconcile to All NY")

    other_row = ownership.loc[ownership["slice"] == "Other / unknown"]
    if not other_row.empty and int(other_row.iloc[0]["facility_days"]) > 0:
        errors.append(
            f"Other/unknown facility-days remain: {int(other_row.iloc[0]['facility_days'])}"
        )

    daily_csv = CSV_DIR / "daily_facility_data.csv"
    if daily_csv.is_file():
        daily = pd.read_csv(daily_csv, dtype=str)
        daily["ccn"] = daily["ccn"].str.zfill(6)
        blank_name = daily["provider_name"].fillna("").astype(str).str.strip().str.lower().isin(
            ("", "nan", "none")
        )
        blank_county = daily["county"].fillna("").astype(str).str.strip().str.lower().isin(
            ("", "nan", "none")
        )
        if blank_name.any():
            errors.append(f"daily CSV blank provider_name rows: {int(blank_name.sum())}")
        if blank_county.any():
            errors.append(f"daily CSV blank county rows: {int(blank_county.sum())}")
        for ccn in ("335683", "335675"):
            sub = daily[daily["ccn"] == ccn]
            if sub.empty:
                errors.append(f"daily CSV missing CCN {ccn}")
            elif sub["nyc_flag"].astype(str).str.lower().eq("true").any():
                errors.append(f"daily CSV {ccn} has nyc_flag=True")

    html = (ROOT / "insights-ny-minimum-staffing.html").read_text(encoding="utf-8")
    if "PBJ320_NY_2025_daily_staffing_verification_file.xlsx" not in html:
        errors.append("report HTML missing workbook path")
    if "PBJ320 verification workbook" not in html and "Download verification workbook" not in html:
        errors.append("report HTML missing verification workbook link")
    if "window.PBJ_REPORT_QUARTERLY_STATUTORY = " not in html:
        errors.append("report HTML missing PBJ_REPORT_QUARTERLY_STATUTORY embed")
    quarterly_note_ok = (
        "Daily shortfalls are not the same as quarterly compliance" in html
        or (
            "Daily vs. quarterly:" in html
            and "not NY DOH enforcement determinations" in html
        )
    )
    if not quarterly_note_ok:
        errors.append("report HTML missing daily vs quarterly framing note")
    quarterly_section_ok = (
        'id="quarterly-statutory-summary"' in html
        or 'id="method-quarterly-statutory"' in html
    )
    if not quarterly_section_ok:
        errors.append("report HTML missing quarterly statutory mapping section")
    if 'data-sort="qtrs_below"' not in html:
        errors.append("report HTML missing Qtrs < Floor table column")

    return errors


def main() -> int:
    errors = verify()
    if errors:
        print("NY verification workbook QA FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("NY verification workbook QA PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
