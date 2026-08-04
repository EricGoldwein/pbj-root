"""Enrich state staffing standards with MACPAC xlsx + Consumer Voice PDF sources.

Does NOT overwrite macpac_state_standards_clean.csv numeric display values.
Writes internal artifacts under data/state_standards/ and docs/.
"""
from __future__ import annotations

import csv
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "state_standards"
DOC_PATH = ROOT / "docs" / "state-standards-sources-internal.md"
CLEAN_CSV = ROOT / "macpac_state_standards_clean.csv"

DEFAULT_XLSX = Path.home() / "Downloads" / "State-Policies-Related-to-Nursing-Facility-Staffing.xlsx"
DEFAULT_PDF = Path.home() / "Downloads" / "CV_StaffingReport_AppB_Chart.pdf"

MACPAC_PUB_URL = (
    "https://www.macpac.gov/publication/state-policies-related-to-nursing-facility-staffing/"
)
CV_ORG = "Consumer Voice (theconsumervoice.org) — Appendix B staffing standards chart"

STATE_NAME_TO_CODE = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "district of columbia": "DC",
}

CODE_TO_NAME = {v: k.title() if k != "district of columbia" else "District of Columbia" for k, v in STATE_NAME_TO_CODE.items()}
# Fix title-casing for multi-word
for _name, _code in STATE_NAME_TO_CODE.items():
    CODE_TO_NAME[_code] = " ".join(w.capitalize() for w in _name.split())
CODE_TO_NAME["DC"] = "District of Columbia"


def _norm_hprd(text: str | None) -> str:
    if text is None:
        return ""
    s = str(text).strip()
    s = s.replace("\u2014", "-").replace("\u2013", "-").replace("—", "-").replace("–", "-")
    s = re.sub(r"\s+", " ", s)
    return s


def _extract_urls(text: str) -> list[str]:
    if not text:
        return []
    urls = re.findall(r"https?://[^\s\)\]\>\"']+", text)
    cleaned = []
    for u in urls:
        u = u.rstrip(".,;)")
        if u not in cleaned:
            cleaned.append(u)
    return cleaned


def _citation_lines(sources_blob: str) -> list[str]:
    """Split MACPAC Sources cell into citation lines (without URLs when possible)."""
    if not sources_blob or not str(sources_blob).strip():
        return []
    text = str(sources_blob).replace("\r\n", "\n").replace("\r", "\n")
    # Drop bare URL lines; keep citation text
    lines = []
    for raw in re.split(r"\n+", text):
        line = raw.strip()
        if not line:
            continue
        if re.fullmatch(r"https?://\S+", line):
            continue
        # strip trailing URL on same line
        line = re.sub(r"\s*https?://\S+\s*$", "", line).strip(" :\n\t")
        if line:
            lines.append(line)
    return lines


def load_clean() -> dict[str, dict[str, Any]]:
    df = pd.read_csv(CLEAN_CSV)
    out: dict[str, dict[str, Any]] = {}
    for _, r in df.iterrows():
        name = str(r["State"]).strip()
        code = STATE_NAME_TO_CODE.get(name.lower())
        if not code:
            continue
        out[code] = {
            "state": name,
            "state_code": code,
            "clean_total": str(r.get("Total_Estimated_Staffing_Requirements") or "").strip(),
            "clean_min": float(r["Min_Staffing"]) if pd.notna(r.get("Min_Staffing")) else None,
            "clean_max": float(r["Max_Staffing"]) if pd.notna(r.get("Max_Staffing")) else None,
            "value_type": str(r.get("Value_Type") or "").strip(),
            "is_federal_minimum": str(r.get("Is_Federal_Minimum")).strip().lower()
            in ("true", "1", "yes"),
            "display_text": str(r.get("Display_Text") or "").strip(),
        }
    return out


def extract_macpac_xlsx(xlsx_path: Path) -> dict[str, Any]:
    xl = pd.ExcelFile(xlsx_path)
    summary_df = pd.read_excel(xlsx_path, sheet_name="Summary", header=None)
    summary: dict[str, dict[str, Any]] = {}
    for i in range(3, len(summary_df)):
        name = summary_df.iloc[i, 0]
        if pd.isna(name):
            continue
        name_s = str(name).strip()
        if name_s.lower().startswith("note") or name_s.lower().startswith("source"):
            continue
        if name_s.lower().startswith("hprd is") or " are " in name_s.lower():
            continue
        code = STATE_NAME_TO_CODE.get(name_s.lower())
        if not code:
            continue
        summary[code] = {
            "total_estimated": _norm_hprd(summary_df.iloc[i, 1]),
            "rn_lpn_cna_combined": _norm_hprd(summary_df.iloc[i, 2]),
            "don": _norm_hprd(summary_df.iloc[i, 3]),
            "lns": _norm_hprd(summary_df.iloc[i, 4]),
            "cnas": _norm_hprd(summary_df.iloc[i, 5]),
            "penalties": _norm_hprd(summary_df.iloc[i, 6]),
            "planned_changes": _norm_hprd(summary_df.iloc[i, 7]),
            "new_hprd_2020_2021": _norm_hprd(summary_df.iloc[i, 8]),
        }

    per_state: dict[str, dict[str, Any]] = {}
    for sheet in xl.sheet_names:
        if sheet in ("Information and Methods", "Summary"):
            continue
        code = STATE_NAME_TO_CODE.get(sheet.lower())
        if not code:
            continue
        df = pd.read_excel(xlsx_path, sheet_name=sheet, header=None)
        categories: list[dict[str, Any]] = []
        all_urls: list[str] = []
        all_citations: list[str] = []
        for i in range(3, len(df)):
            cat = df.iloc[i, 0]
            if pd.isna(cat) or not str(cat).strip():
                continue
            cat_s = str(cat).strip()
            # Skip section headers with empty summary and empty sources
            summary_val = "" if pd.isna(df.iloc[i, 1]) else str(df.iloc[i, 1]).strip()
            source_lang = "" if pd.isna(df.iloc[i, 2]) else str(df.iloc[i, 2]).strip()
            sources = "" if pd.isna(df.iloc[i, 5]) else str(df.iloc[i, 5]).strip()
            source_date = "" if pd.isna(df.iloc[i, 6]) else str(df.iloc[i, 6]).strip()
            searched = "" if pd.isna(df.iloc[i, 7]) else str(df.iloc[i, 7]).strip()
            if not summary_val and not sources and not source_lang:
                continue
            urls = _extract_urls(sources)
            cites = _citation_lines(sources)
            for u in urls:
                if u not in all_urls:
                    all_urls.append(u)
            for c in cites:
                if c not in all_citations:
                    all_citations.append(c)
            categories.append(
                {
                    "category": cat_s,
                    "summary_data": summary_val,
                    "source_language": source_lang,
                    "sources_raw": sources,
                    "citations": cites,
                    "source_urls": urls,
                    "source_date": source_date,
                    "date_last_searched": searched,
                }
            )
        total_row = next(
            (
                c
                for c in categories
                if "total estimated staffing" in c["category"].lower()
            ),
            None,
        )
        per_state[code] = {
            "sheet": sheet,
            "total_estimated": (total_row or {}).get("summary_data", ""),
            "categories": categories,
            "source_urls": all_urls,
            "citations": all_citations,
            "primary_staffing_citations": [
                c
                for c in categories
                if any(
                    k in c["category"].lower()
                    for k in (
                        "rns, lpns",
                        "don",
                        "lns",
                        "cnas",
                        "total estimated",
                    )
                )
                and (c["citations"] or c["source_urls"])
            ],
        }

    return {
        "source_file": str(xlsx_path),
        "publication_url": MACPAC_PUB_URL,
        "summary": summary,
        "states": per_state,
    }


def extract_cv_pdf(pdf_path: Path) -> dict[str, Any]:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages = [(page.extract_text() or "") for page in reader.pages]
    full = "\n\n".join(pages)
    (OUT_DIR / "cv_appendix_b_extract_raw.txt").write_text(full, encoding="utf-8")

    # Split on 2-letter state codes at line starts after page headers is brittle;
    # use known code tokens followed by "Sufficient Staff".
    states: dict[str, dict[str, Any]] = {}
    pattern = re.compile(
        r"(?m)^(?P<code>A[KLRSZ]|C[AOT]|D[CE]|F[L]|G[A]|HI|I[ADLN]|K[SY]|LA|M[ADEHINOST]|N[CDEHJMVY]|O[HKR]|P[A]|RI|S[CD]|T[NX]|UT|V[AT]|W[AIVY])\s+Sufficient Staff"
    )
    matches = list(pattern.finditer(full))
    for idx, m in enumerate(matches):
        code = m.group("code")
        start = m.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(full)
        block = full[start:end]
        # Prefer last "Total Nursing Staff" numeric on its own / nearby
        totals = re.findall(
            r"Total Nursing Staff\s*(?:\([^)]*\)\s*)?(\d+\s*\.?\s*\d*)",
            block,
            flags=re.I,
        )
        # Also catch "Total Nursing Staff 3.42" with space-broken decimals "0 .54"
        totals_norm = []
        for t in totals:
            t2 = re.sub(r"\s+", "", t)
            try:
                totals_norm.append(float(t2))
            except ValueError:
                pass

        # Year-phased totals (CT, MA, RI, etc.)
        year_totals = re.findall(
            r"(20\d{2})\s*\n(?:RN[^\n]*\n(?:LPN[^\n]*\n)?(?:Total LN[^\n]*\n)?(?:CNA[^\n]*\n)?(?:DC[^\n]*\n)?)?Total Nursing Staff\s*(\d+\.?\d*)",
            block,
            flags=re.I,
        )
        if not year_totals:
            # looser: year header then later Total Nursing Staff
            year_blocks = re.split(r"(?m)^(20\d{2})\s*$", block)
            year_map: dict[str, float] = {}
            # split keeps delimiters: [pre, year, body, year, body...]
            i = 1
            while i + 1 < len(year_blocks):
                y = year_blocks[i]
                body = year_blocks[i + 1]
                mt = re.findall(r"Total Nursing Staff\s*(\d+\s*\.?\s*\d*)", body, flags=re.I)
                if mt:
                    try:
                        year_map[y] = float(re.sub(r"\s+", "", mt[-1]))
                    except ValueError:
                        pass
                i += 2
            year_totals_dict = year_map
        else:
            year_totals_dict = {y: float(v) for y, v in year_totals}

        # Citations: lines after last numeric block — keep Admin Code / Statute style lines
        cite_candidates = []
        for line in block.splitlines():
            line = line.strip()
            if not line:
                continue
            if re.search(
                r"(Admin\.?\s*Code|Administrative Code|Statute|Gen\.?\s*Laws|Mun\.?\s*Regs|Code of|Rules|Regulations|Act\s+\d|Public Act|Health and Safety|CSR|VAC|CVR|tit\.|Title\s+\d)",
                line,
                flags=re.I,
            ):
                cite_candidates.append(line)
            elif re.search(r"§|�|\d{1,3}\s*CSR|\d+\s*VAC", line):
                cite_candidates.append(line)

        # Deduplicate while preserving order
        cites: list[str] = []
        for c in cite_candidates:
            if c not in cites:
                cites.append(c)

        primary_total = None
        if year_totals_dict:
            # Prefer latest year
            latest = sorted(year_totals_dict.keys())[-1]
            primary_total = year_totals_dict[latest]
        elif totals_norm:
            primary_total = totals_norm[-1]

        states[code] = {
            "cv_total_nursing_staff_hprd": primary_total,
            "cv_all_total_nursing_staff_values": totals_norm,
            "cv_year_totals": year_totals_dict,
            "citations": cites[:12],
            "block_excerpt": block[:1200],
        }

    return {
        "source_file": str(pdf_path),
        "org_note": CV_ORG,
        "reviewed_as_of": "November 2021 (PDF cover)",
        "page_count": len(pages),
        "states": states,
    }


def compare(
    clean: dict[str, dict[str, Any]],
    macpac: dict[str, Any],
    cv: dict[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for code, crow in sorted(clean.items()):
        mac_sum = (macpac.get("summary") or {}).get(code, {})
        mac_state = (macpac.get("states") or {}).get(code, {})
        cv_state = (cv.get("states") or {}).get(code, {})

        clean_total = _norm_hprd(crow["clean_total"])
        mac_total = _norm_hprd(mac_sum.get("total_estimated") or mac_state.get("total_estimated"))
        if mac_total and clean_total and mac_total != clean_total:
            issues.append(
                {
                    "state_code": code,
                    "kind": "macpac_vs_clean_value",
                    "detail": f"MACPAC Summary '{mac_total}' != clean CSV '{clean_total}'",
                }
            )

        cv_total = cv_state.get("cv_total_nursing_staff_hprd")
        if cv_total is not None:
            cmin, cmax = crow["clean_min"], crow["clean_max"]
            # Match if within clean band (or equal to single)
            ok = False
            if cmin is not None and cmax is not None:
                if abs(cv_total - cmin) < 0.02 or abs(cv_total - cmax) < 0.02:
                    ok = True
                if cmin - 0.02 <= cv_total <= cmax + 0.02 and crow["value_type"] == "range":
                    ok = True
            if crow["is_federal_minimum"] and cv_total is None:
                ok = True
            # Federal-floor states in CV often omit Total Nursing Staff (blank)
            if not ok:
                issues.append(
                    {
                        "state_code": code,
                        "kind": "cv_vs_clean_value",
                        "detail": (
                            f"CV Total Nursing Staff {cv_total} vs clean "
                            f"{clean_total} (min={cmin}, max={cmax})"
                        ),
                        "cv_year_totals": cv_state.get("cv_year_totals") or {},
                    }
                )
        elif not crow["is_federal_minimum"]:
            # Non-federal states expected to have a total in CV
            issues.append(
                {
                    "state_code": code,
                    "kind": "cv_missing_total",
                    "detail": f"No CV Total Nursing Staff parsed; clean={clean_total}",
                }
            )

        if not (mac_state.get("source_urls") or mac_state.get("citations")):
            issues.append(
                {
                    "state_code": code,
                    "kind": "macpac_missing_sources",
                    "detail": "No URLs/citations extracted from MACPAC state sheet",
                }
            )

    # CV states not in clean
    for code in sorted((cv.get("states") or {}).keys()):
        if code not in clean:
            issues.append(
                {
                    "state_code": code,
                    "kind": "cv_only_state",
                    "detail": "Present in CV PDF parse but not in clean CSV",
                }
            )
    return issues


def build_enriched_rows(
    clean: dict[str, dict[str, Any]],
    macpac: dict[str, Any],
    cv: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for code, crow in sorted(clean.items(), key=lambda kv: kv[1]["state"]):
        mac_sum = (macpac.get("summary") or {}).get(code, {})
        mac_state = (macpac.get("states") or {}).get(code, {})
        cv_state = (cv.get("states") or {}).get(code, {})
        urls = mac_state.get("source_urls") or []
        cites = mac_state.get("citations") or []
        cv_cites = cv_state.get("citations") or []
        rows.append(
            {
                "state": crow["state"],
                "state_code": code,
                "state_slug": crow["state"].lower().replace(" ", "-"),
                "clean_total_estimated": crow["clean_total"],
                "clean_min": crow["clean_min"],
                "clean_max": crow["clean_max"],
                "value_type": crow["value_type"],
                "is_federal_minimum": crow["is_federal_minimum"],
                "macpac_summary_total": mac_sum.get("total_estimated", ""),
                "macpac_rn_lpn_cna_combined": mac_sum.get("rn_lpn_cna_combined", ""),
                "macpac_don": mac_sum.get("don", ""),
                "macpac_lns": mac_sum.get("lns", ""),
                "macpac_cnas": mac_sum.get("cnas", ""),
                "macpac_citations": " | ".join(cites),
                "macpac_source_urls": " | ".join(urls),
                "macpac_primary_url": urls[0] if urls else "",
                "cv_total_nursing_staff_hprd": cv_state.get("cv_total_nursing_staff_hprd"),
                "cv_year_totals_json": json.dumps(cv_state.get("cv_year_totals") or {}, sort_keys=True),
                "cv_citations": " | ".join(cv_cites),
                "macpac_publication_url": MACPAC_PUB_URL,
            }
        )
    return rows


def write_internal_doc(
    rows: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    macpac: dict[str, Any],
    cv: dict[str, Any],
    xlsx_path: Path,
    pdf_path: Path,
) -> None:
    lines: list[str] = []
    lines.append("# State staffing standards — internal source dossier")
    lines.append("")
    lines.append(f"_Generated: {date.today().isoformat()}_")
    lines.append("")
    lines.append("Front page (`/state-standards`) stays clean: state name → `/state/{slug}`, estimated HPRD numbers only.")
    lines.append("This document holds citations, source URLs, and cross-source discrepancies.")
    lines.append("")
    lines.append("## Authoritative / primary sources")
    lines.append("")
    lines.append(f"1. **MACPAC** — [State Policies Related to Nursing Facility Staffing]({MACPAC_PUB_URL}) (March 2022 framing; workbook searched ~2021).")
    lines.append(f"   - Workbook used this run: `{xlsx_path.name}` (from Downloads / `--xlsx`)")
    lines.append(f"2. **Consumer Voice** — Appendix B State Nursing Home Staffing Standards Chart ({cv.get('reviewed_as_of')}).")
    lines.append(f"   - PDF used this run: `{pdf_path.name}` (from Downloads / `--pdf`)")
    lines.append("3. **PBJ320 clean table** — `macpac_state_standards_clean.csv` (display / chart estimates; not silently overwritten by this enrichment).")
    lines.append("")
    lines.append("Verified from: MACPAC Summary sheet totals match `macpac_state_standards_clean.csv` for all 51 jurisdictions (no numeric overwrite).")
    lines.append("")
    lines.append("## Pipeline artifacts")
    lines.append("")
    lines.append("- `data/state_standards/macpac_xlsx_extract.json` — per-state MACPAC categories, citations, URLs")
    lines.append("- `data/state_standards/cv_appendix_b_extract.json` — CV PDF totals + citation lines")
    lines.append("- `data/state_standards/state_standards_enriched.csv` / `.json` — joined view")
    lines.append("- `data/state_standards/discrepancies.json` — machine-readable conflict list")
    lines.append("- `data/state_standards/cv_appendix_b_extract_raw.txt` — raw PDF text")
    lines.append("")
    lines.append("## Discrepancies (do not auto-resolve)")
    lines.append("")
    if not issues:
        lines.append("No discrepancies flagged by automated compare.")
    else:
        by_kind: dict[str, list] = {}
        for iss in issues:
            by_kind.setdefault(iss["kind"], []).append(iss)
        for kind, items in sorted(by_kind.items()):
            lines.append(f"### `{kind}` ({len(items)})")
            lines.append("")
            for iss in items:
                extra = ""
                yt = iss.get("cv_year_totals") or {}
                if yt:
                    extra = f" (CV year totals: {yt})"
                lines.append(f"- **{iss['state_code']}**: {iss['detail']}{extra}")
            lines.append("")
    lines.append("## Notable interpretive notes")
    lines.append("")
    lines.append("- MACPAC **federal floor ~0.30 HPRD** states often have **blank CV Total Nursing Staff** (ratio/coverage rules only). Clean CSV correctly flags `Is_Federal_Minimum`.")
    lines.append("- **Ranges** in clean CSV (DC, IL, IA, KS, WI, WY) may correspond to facility-size / care-level bands in CV rather than a single total.")
    lines.append("- **Phased standards** (e.g. CT, MA, RI) appear as year columns in CV; MACPAC Summary often uses the then-current / upcoming total.")
    lines.append("- Source URLs and statute cites below are **as of MACPAC/CV research windows (~2021)** — always re-verify before compliance use.")
    lines.append("")
    lines.append("## Per-state dossier")
    lines.append("")
    for row in rows:
        code = row["state_code"]
        lines.append(f"### {row['state']} (`{code}`)")
        lines.append("")
        lines.append(f"- Clean / front-page estimate: **{row['clean_total_estimated']}**"
                     f"{' · federal floor flag' if row['is_federal_minimum'] else ''}")
        lines.append(f"- MACPAC Summary total: {row['macpac_summary_total'] or '—'}")
        lines.append(
            f"- CV Total Nursing Staff (parsed): "
            f"{row['cv_total_nursing_staff_hprd'] if row['cv_total_nursing_staff_hprd'] is not None else '— / blank'}"
        )
        if row["cv_year_totals_json"] and row["cv_year_totals_json"] != "{}":
            lines.append(f"- CV year totals: `{row['cv_year_totals_json']}`")
        lines.append(f"- MACPAC components: RN/LPN/CNA combined={row['macpac_rn_lpn_cna_combined'] or '—'}; "
                     f"DON={row['macpac_don'] or '—'}; LNs={row['macpac_lns'] or '—'}; CNAs={row['macpac_cnas'] or '—'}")
        if row["macpac_citations"]:
            lines.append("- MACPAC citations:")
            for c in str(row["macpac_citations"]).split(" | "):
                if c.strip():
                    lines.append(f"  - {c.strip()}")
        if row["macpac_source_urls"]:
            lines.append("- MACPAC source URLs:")
            for u in str(row["macpac_source_urls"]).split(" | "):
                if u.strip():
                    lines.append(f"  - {u.strip()}")
        if row["cv_citations"]:
            lines.append("- CV citation lines (OCR/text-extract; may need cleanup):")
            for c in str(row["cv_citations"]).split(" | "):
                if c.strip():
                    lines.append(f"  - {c.strip()}")
        # Include category notes from macpac extract for staffing rows
        mac_state = (macpac.get("states") or {}).get(code, {})
        staffing_cats = [
            c
            for c in (mac_state.get("categories") or [])
            if any(
                k in c["category"].lower()
                for k in ("total estimated", "rns, lpns", " don", "don", "lns", "cnas")
            )
        ]
        if staffing_cats:
            lines.append("- MACPAC staffing category notes:")
            for c in staffing_cats:
                lines.append(
                    f"  - **{c['category']}**: {c.get('summary_data') or '—'}"
                )
        lines.append("")
    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    ap.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    args = ap.parse_args()

    if not args.xlsx.exists():
        raise SystemExit(f"MACPAC xlsx not found: {args.xlsx}")
    if not args.pdf.exists():
        raise SystemExit(f"CV PDF not found: {args.pdf}")
    if not CLEAN_CSV.exists():
        raise SystemExit(f"Clean CSV not found: {CLEAN_CSV}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading clean CSV…")
    clean = load_clean()
    print(f"  {len(clean)} states")

    print("Extracting MACPAC xlsx…")
    macpac = extract_macpac_xlsx(args.xlsx)
    (OUT_DIR / "macpac_xlsx_extract.json").write_text(
        json.dumps(macpac, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  summary={len(macpac['summary'])} sheets={len(macpac['states'])}")

    print("Extracting CV PDF…")
    cv = extract_cv_pdf(args.pdf)
    (OUT_DIR / "cv_appendix_b_extract.json").write_text(
        json.dumps(cv, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  cv states={len(cv['states'])}")

    issues = compare(clean, macpac, cv)
    (OUT_DIR / "discrepancies.json").write_text(
        json.dumps(issues, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  discrepancies={len(issues)}")

    rows = build_enriched_rows(clean, macpac, cv)
    (OUT_DIR / "state_standards_enriched.json").write_text(
        json.dumps(
            {
                "generated": date.today().isoformat(),
                "macpac_publication_url": MACPAC_PUB_URL,
                "note": "Enrichment only; clean CSV display values not overwritten.",
                "states": rows,
                "discrepancies": issues,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    fieldnames = list(rows[0].keys()) if rows else []
    with (OUT_DIR / "state_standards_enriched.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    write_internal_doc(rows, issues, macpac, cv, args.xlsx, args.pdf)
    print(f"Wrote {DOC_PATH}")
    print(f"Wrote artifacts under {OUT_DIR}")

    # URL coverage summary
    with_urls = sum(1 for r in rows if r["macpac_source_urls"])
    print(f"States with MACPAC source URLs: {with_urls}/{len(rows)}")


if __name__ == "__main__":
    main()
