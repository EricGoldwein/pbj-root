#!/usr/bin/env python3
"""
Build chow_index.json for the public /chow Change of Ownership monitor.

Reads CMS SNF CHOW CSV(s) from:
  - ownership/Skilled Nursing Facility Change of Ownership.zip (default; Q2 2026 member SNF_CHOW_Q2_2026.csv when present)
  - data/chow/*.csv (e.g. CT_SNF_CHOW_Q1_2026.csv)
  - --csv path(s)

Output: chow_index.json at repo root (meta incl. cms_release/coverage/source_sha256, summary, records).

TODO: Join pre/post PBJ staffing (HPRD, RN, aide, weekend) by CCN around effective_date.
TODO: Join citations/penalties and CMS all-owner control entities when ETL is ready.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
DEFAULT_ZIP = REPO_ROOT / "ownership" / "Skilled Nursing Facility Change of Ownership.zip"
DEFAULT_OUT = REPO_ROOT / "chow_index.json"
DEFAULT_CHOW_DIR = REPO_ROOT / "data" / "chow"

# Column aliases (CMS headers + flexible CT/custom exports)
COL_MAP = {
    "effective_date": (
        "EFFECTIVE DATE",
        "CHOW EFFECTIVE DATE",
        "Effective Date",
        "effective_date",
    ),
    "state": (
        "ENROLLMENT STATE - BUYER",
        "STATE",
        "State",
        "state",
    ),
    "ccn": ("CCN - BUYER", "CCN", "ccn", "CMS Certification Number (CCN)"),
    "buyer_org": ("ORGANIZATION NAME - BUYER", "BUYER ORGANIZATION NAME", "buyer_org_name"),
    "buyer_dba": ("DOING BUSINESS AS NAME - BUYER", "BUYER DBA", "buyer_dba_name"),
    "buyer_enrollment": ("ENROLLMENT ID - BUYER", "buyer_enrollment_id"),
    "buyer_npi": ("NPI - BUYER", "buyer_npi"),
    "buyer_associate": ("ASSOCIATE ID - BUYER", "buyer_associate_id", "BUYER PAC ID"),
    "seller_org": ("ORGANIZATION NAME - SELLER", "SELLER ORGANIZATION NAME", "seller_org_name"),
    "seller_dba": ("DOING BUSINESS AS NAME - SELLER", "SELLER DBA", "seller_dba_name"),
    "seller_enrollment": ("ENROLLMENT ID - SELLER", "seller_enrollment_id"),
    "seller_npi": ("NPI - SELLER", "seller_npi"),
    "seller_associate": ("ASSOCIATE ID - SELLER", "seller_associate_id", "SELLER PAC ID"),
    "chow_type": ("CHOW TYPE TEXT", "CHOW TYPE", "chow_type"),
    "chow_type_code": ("CHOW TYPE CODE", "chow_type_code"),
}

PATTERN_RULES = (
    ("acquisition_operator", "buyer", "ACQUISITION OPERATOR LLC"),
    ("opco", "buyer", "OPCO LLC"),
    ("complete_care", "buyer", "COMPLETE CARE"),
    ("havencare", "both", "HAVENCARE"),
    ("harborside_seller", "seller", "HARBORSIDE"),
)


def _pick(row: dict, key: str) -> str:
    for col in COL_MAP.get(key, ()):
        if col in row:
            v = row[col]
            if v is not None and str(v).strip() not in ("", "nan", "None", "NA", "N/A"):
                return str(v).strip()
    return ""


def normalize_ccn(val: str) -> str:
    if not val:
        return ""
    s = str(val).strip()
    if "." in s:
        s = s.split(".")[0]
    digits = re.sub(r"[^0-9]", "", s)
    if not digits:
        return ""
    return digits.zfill(6)[-6:]


def normalize_org_name(val: str) -> str:
    if not val:
        return ""
    s = re.sub(r"\s+", " ", str(val).strip().upper())
    return s


def normalize_associate_id(val: str) -> str:
    if not val:
        return ""
    s = str(val).strip().replace("O", "").replace("o", "")
    digits = re.sub(r"[^0-9]", "", s)
    if len(digits) == 10:
        return digits
    if len(digits) == 9:
        return digits.zfill(10)
    if len(digits) == 11:
        return digits[-10:]
    return ""


def parse_effective_date(raw: str) -> tuple[str, int | None]:
    """Return (ISO date YYYY-MM-DD or '', year or None)."""
    if not raw:
        return "", None
    s = str(raw).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d"), dt.year
        except ValueError:
            continue
    return "", None


def owner_url_for_associate(associate_id: str, org_name: str = "") -> str:
    """Link to /owners/{pac}/{slug} — profile page resolves enrollment vs owner/control PAC."""
    try:
        from ownership.owner_profile import associate_profile_url

        return associate_profile_url(associate_id, org_name)
    except Exception:
        pac = normalize_associate_id(associate_id)
        if pac:
            return f"/owners/{pac}"
        return owner_search_url(org_name)


def _provider_canonical_path(ccn: str, facility_name: str = "") -> str:
    try:
        from canonical_urls import provider_url

        return provider_url(ccn, facility_name) if ccn else ""
    except Exception:
        return f"/provider/{ccn}" if ccn else ""


def owner_search_url(org_name: str) -> str:
    """FEC contributions hub (no per-name deep link until matching is reliable)."""
    if not (org_name or "").strip():
        return ""
    return "/owner"


def detect_pattern_tags(
    buyer_org: str,
    buyer_dba: str,
    seller_org: str,
    seller_dba: str,
    buyer_norm: str,
    seller_norm: str,
    buyer_count: int,
    seller_count: int,
) -> list[str]:
    tags: list[str] = []
    buyer_blob = f"{buyer_org} {buyer_dba}".upper()
    seller_blob = f"{seller_org} {seller_dba}".upper()
    both_blob = f"{buyer_blob} {seller_blob}"

    for tag, side, needle in PATTERN_RULES:
        hay = buyer_blob if side == "buyer" else seller_blob if side == "seller" else both_blob
        if needle in hay:
            tags.append(tag)

    if buyer_count >= 2:
        tags.append("repeat_buyer")
    if seller_count >= 2:
        tags.append("repeat_seller")
    return tags


def load_rows_from_zip(zip_path: Path) -> list[dict]:
    rows: list[dict] = []
    with zipfile.ZipFile(zip_path) as zf:
        csv_names = [
            n
            for n in zf.namelist()
            if n.lower().endswith(".csv")
            and "snf_chow" in n.lower()
            and "npi" not in n.lower()
            and "hospital" not in n.lower()
        ]
        if not csv_names:
            raise FileNotFoundError(f"No SNF CHOW CSV in {zip_path}")
        for name in sorted(csv_names):
            with zf.open(name) as f:
                text = io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace")
                rows.extend(csv.DictReader(text))
    return rows


def load_rows_from_csv_paths(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for p in paths:
        with p.open(encoding="utf-8-sig", errors="replace", newline="") as f:
            rows.extend(csv.DictReader(f))
    return rows


def build_records(raw_rows: list[dict]) -> tuple[list[dict], dict]:
    buyer_counts: Counter[str] = Counter()
    seller_counts: Counter[str] = Counter()
    parsed: list[dict] = []

    for row in raw_rows:
        buyer_org = _pick(row, "buyer_org")
        seller_org = _pick(row, "seller_org")
        bn = normalize_org_name(buyer_org)
        sn = normalize_org_name(seller_org)
        if bn:
            buyer_counts[bn] += 1
        if sn:
            seller_counts[sn] += 1
        parsed.append(
            {
                "row": row,
                "buyer_org": buyer_org,
                "seller_org": seller_org,
                "buyer_norm": bn,
                "seller_norm": sn,
            }
        )

    records: list[dict] = []
    for i, item in enumerate(parsed):
        row = item["row"]
        buyer_org = item["buyer_org"]
        seller_org = item["seller_org"]
        buyer_dba = _pick(row, "buyer_dba")
        seller_dba = _pick(row, "seller_dba")
        buyer_norm = item["buyer_norm"]
        seller_norm = item["seller_norm"]

        ccn = normalize_ccn(_pick(row, "ccn"))
        state = (_pick(row, "state") or "").upper()[:2]
        eff_raw = _pick(row, "effective_date")
        effective_date, effective_year = parse_effective_date(eff_raw)

        buyer_assoc = _pick(row, "buyer_associate")
        seller_assoc = _pick(row, "seller_associate")

        facility_display = ""
        if ccn:
            try:
                from ownership.owner_portfolio_metrics import _ccn_provider_lookup

                facility_display = str(
                    (_ccn_provider_lookup().get(ccn) or {}).get("provider_name") or ""
                ).strip()
            except Exception:
                facility_display = ""
        if not facility_display:
            facility_display = buyer_dba or buyer_org or seller_dba or ""
        chow_type = _pick(row, "chow_type") or _pick(row, "chow_type_code")

        buyer_owner_url = owner_url_for_associate(buyer_assoc, buyer_org) or owner_search_url(buyer_org)
        seller_owner_url = owner_url_for_associate(seller_assoc, seller_org) or owner_search_url(seller_org)
        try:
            from ownership.owner_profile import (
                associate_id_kind_label,
                associate_id_namespace,
            )

            buyer_assoc_kind = associate_id_kind_label(buyer_assoc) if buyer_assoc else ""
            seller_assoc_kind = associate_id_kind_label(seller_assoc) if seller_assoc else ""
            buyer_assoc_ns = associate_id_namespace(buyer_assoc) if buyer_assoc else "unknown"
            seller_assoc_ns = associate_id_namespace(seller_assoc) if seller_assoc else "unknown"
        except Exception as _assoc_ns_err:
            # Fail soft per row, but surface once so silent all-unknown rebuilds are visible.
            if not getattr(build_records, "_assoc_ns_warned", False):
                print(f"[build_chow_index] associate namespace lookup failed: {_assoc_ns_err}", flush=True)
                build_records._assoc_ns_warned = True  # type: ignore[attr-defined]
            buyer_assoc_kind = ""
            seller_assoc_kind = ""
            buyer_assoc_ns = "unknown"
            seller_assoc_ns = "unknown"

        pattern_tags = detect_pattern_tags(
            buyer_org,
            buyer_dba,
            seller_org,
            seller_dba,
            buyer_norm,
            seller_norm,
            buyer_counts.get(buyer_norm, 0),
            seller_counts.get(seller_norm, 0),
        )

        id_seed = f"{ccn}|{effective_date}|{buyer_org}|{seller_org}|{i}"
        chow_id = hashlib.sha1(id_seed.encode("utf-8")).hexdigest()[:12]

        records.append(
            {
                "chow_id": chow_id,
                "effective_date": effective_date,
                "effective_year": effective_year,
                "state": state,
                "ccn": ccn,
                "buyer_org_name": buyer_org,
                "buyer_dba_name": buyer_dba,
                "buyer_enrollment_id": _pick(row, "buyer_enrollment"),
                "buyer_npi": _pick(row, "buyer_npi"),
                "buyer_associate_id": buyer_assoc,
                "seller_org_name": seller_org,
                "seller_dba_name": seller_dba,
                "seller_enrollment_id": _pick(row, "seller_enrollment"),
                "seller_npi": _pick(row, "seller_npi"),
                "seller_associate_id": seller_assoc,
                "chow_type": chow_type,
                "facility_display_name": facility_display,
                "buyer_normalized": buyer_norm,
                "seller_normalized": seller_norm,
                "provider_url": _provider_canonical_path(ccn, facility_display),
                "buyer_owner_url": buyer_owner_url,
                "seller_owner_url": seller_owner_url,
                "buyer_associate_kind": buyer_assoc_kind,
                "seller_associate_kind": seller_assoc_kind,
                "buyer_associate_id_namespace": buyer_assoc_ns,
                "seller_associate_id_namespace": seller_assoc_ns,
                "pattern_tags": pattern_tags,
            }
        )

    records.sort(key=lambda r: (r.get("effective_date") or "", r.get("ccn") or ""), reverse=True)
    summary = build_summary(records, buyer_counts, seller_counts)
    return records, summary


def build_summary(
    records: list[dict],
    buyer_counts: Counter[str],
    seller_counts: Counter[str],
) -> dict:
    dates = [r["effective_date"] for r in records if r.get("effective_date")]
    states = {r["state"] for r in records if r.get("state")}
    years = Counter(r["effective_year"] for r in records if r.get("effective_year"))
    buyers = {r["buyer_normalized"] for r in records if r.get("buyer_normalized")}
    sellers = {r["seller_normalized"] for r in records if r.get("seller_normalized")}
    ccns = {r["ccn"] for r in records if r.get("ccn")}

    ct_records = [r for r in records if r.get("state") == "CT"]
    ct_2024 = sum(1 for r in ct_records if r.get("effective_year") == 2024)
    ct_2025 = sum(1 for r in ct_records if r.get("effective_year") == 2025)
    acq_op = sum(1 for r in records if "acquisition_operator" in r.get("pattern_tags", []))

    largest_year = years.most_common(1)[0] if years else (None, 0)

    clusters = build_clusters(records, buyer_counts, seller_counts)
    top_lists = build_top_parties_lists(records)

    state_counts: dict[str, int] = {}
    for r in records:
        st = r.get("state") or ""
        if st:
            state_counts[st] = state_counts.get(st, 0) + 1

    return {
        "total_records": len(records),
        "state_counts": state_counts,
        "top_buyers": top_lists["national"]["buyers"],
        "top_sellers": top_lists["national"]["sellers"],
        "top_by_state": top_lists["by_state"],
        "date_min": min(dates) if dates else "",
        "date_max": max(dates) if dates else "",
        "states_count": len(states),
        "most_recent_chow_date": max(dates) if dates else "",
        "unique_buyers": len(buyers),
        "unique_sellers": len(sellers),
        "unique_ccns": len(ccns),
        "largest_year": largest_year[0],
        "largest_year_count": largest_year[1],
        "ct_2024_count": ct_2024,
        "ct_2025_count": ct_2025,
        "acquisition_operator_count": acq_op,
        "clusters": clusters,
    }


def _party_list_from_records(
    records: list[dict],
    side: str,
    limit: int,
) -> list[dict]:
    """Top buyers or sellers by CHOW transaction count (side: buyer | seller)."""
    counts: Counter[str] = Counter()
    meta: dict[str, dict] = {}
    norm_key = f"{side}_normalized"
    name_key = f"{side}_org_name"
    assoc_key = f"{side}_associate_id"
    url_key = f"{side}_owner_url"
    for r in records:
        norm = r.get(norm_key) or ""
        if not norm:
            continue
        counts[norm] += 1
        if norm not in meta:
            meta[norm] = {
                "name": r.get(name_key) or norm,
                "associate_id": r.get(assoc_key) or "",
                "owner_url": r.get(url_key) or "",
                "normalized": norm,
            }
    out: list[dict] = []
    for norm, cnt in counts.most_common(limit):
        m = meta[norm]
        out.append(
            {
                "name": m["name"],
                "count": cnt,
                "associate_id": m["associate_id"],
                "owner_url": m["owner_url"],
                "normalized": norm,
            }
        )
    return out


def build_top_parties_lists(records: list[dict], national_limit: int = 8, state_limit: int = 6) -> dict:
    """National and per-state top buyer/seller lists for featured UI blocks."""
    national = {
        "buyers": _party_list_from_records(records, "buyer", national_limit),
        "sellers": _party_list_from_records(records, "seller", national_limit),
    }
    states = sorted({r.get("state") for r in records if r.get("state")})
    by_state: dict[str, dict] = {}
    for st in states:
        st_rows = [r for r in records if r.get("state") == st]
        by_state[st] = {
            "buyers": _party_list_from_records(st_rows, "buyer", state_limit),
            "sellers": _party_list_from_records(st_rows, "seller", state_limit),
        }
    return {"national": national, "by_state": by_state}


def build_clusters(
    records: list[dict],
    buyer_counts: Counter[str],
    seller_counts: Counter[str],
) -> list[dict]:
    clusters: list[dict] = []

    def add_cluster(label: str, predicate, cluster_type: str) -> None:
        matched = [r for r in records if predicate(r)]
        if not matched:
            return
        examples: list[str] = []
        seen: set[str] = set()
        for r in matched:
            label_txt = r.get("facility_display_name") or r.get("ccn") or ""
            if label_txt and label_txt not in seen and len(examples) < 3:
                seen.add(label_txt)
                examples.append(label_txt)
        clusters.append(
            {
                "cluster_type": cluster_type,
                "label": label,
                "count": len(matched),
                "examples": examples,
                "filter_key": cluster_type,
            }
        )

    for norm, cnt in buyer_counts.most_common(50):
        if cnt < 2:
            break
        sample = next((r for r in records if r.get("buyer_normalized") == norm), None)
        if not sample:
            continue
        display = sample.get("buyer_org_name") or norm
        clusters.append(
            {
                "cluster_type": "repeat_buyer",
                "label": f'Repeated buyer-name pattern: "{display}"',
                "count": cnt,
                "examples": _example_facilities(
                    [r for r in records if r.get("buyer_normalized") == norm]
                ),
                "filter_key": "repeat_buyer",
                "filter_value": norm,
            }
        )
        if len([c for c in clusters if c["cluster_type"] == "repeat_buyer"]) >= 8:
            break

    for norm, cnt in seller_counts.most_common(50):
        if cnt < 2:
            break
        sample = next((r for r in records if r.get("seller_normalized") == norm), None)
        if not sample:
            continue
        display = sample.get("seller_org_name") or norm
        clusters.append(
            {
                "cluster_type": "repeat_seller",
                "label": f'Repeated seller-name pattern: "{display}"',
                "count": cnt,
                "examples": _example_facilities(
                    [r for r in records if r.get("seller_normalized") == norm]
                ),
                "filter_key": "repeat_seller",
                "filter_value": norm,
            }
        )
        if len([c for c in clusters if c["cluster_type"] == "repeat_seller"]) >= 8:
            break

    pattern_labels = {
        "acquisition_operator": 'Buyer-name pattern contains "Acquisition Operator LLC"',
        "opco": 'Buyer-name pattern contains "OPCO LLC"',
        "complete_care": 'Buyer-name pattern contains "Complete Care"',
        "havencare": 'Buyer or DBA name pattern contains "Havencare"',
        "harborside_seller": 'Seller-name pattern contains "Harborside"',
    }
    for tag, label in pattern_labels.items():
        add_cluster(
            label,
            lambda r, t=tag: t in r.get("pattern_tags", []),
            tag,
        )

    return clusters[:20]


def _example_facilities(rows: list[dict], limit: int = 3) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for r in rows:
        txt = r.get("facility_display_name") or r.get("ccn") or ""
        if txt and txt not in seen:
            seen.add(txt)
            out.append(txt)
        if len(out) >= limit:
            break
    return out


def _detect_cms_chow_release(sources: list[str]) -> str:
    """Infer CMS CHOW release label from source path/filename markers."""
    blob = " ".join(sources).replace("\\", "/").lower()
    if "2026-q2" in blob or "q2_2026" in blob or "chow_q2" in blob:
        return "Q2 2026"
    if "2026-q1" in blob or "q1_2026" in blob or "2026.04.01" in blob:
        return "Q1 2026"
    # Default CMS zip at ownership/… may be Q2 content without quarter in path.
    return ""


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def infer_meta(
    records: list[dict],
    sources: list[str],
    ct_only: bool,
    *,
    source_paths: list[Path] | None = None,
    release_hint: str = "",
) -> dict:
    states = {r["state"] for r in records if r.get("state")}
    dates = [r["effective_date"] for r in records if r.get("effective_date")]
    date_min = min(dates) if dates else ""
    date_max = max(dates) if dates else ""

    cms_release = (release_hint or "").strip() or _detect_cms_chow_release(sources)
    if not cms_release:
        # Coverage heuristic when zip path has no quarter marker.
        if date_max >= "2026-01-01":
            cms_release = "Q2 2026"
        elif date_max >= "2025-10-01":
            cms_release = "Q1 2026"
        else:
            cms_release = "unknown"

    if ct_only or (len(states) <= 2 and states == {"CT"}):
        scope_note = (
            f"Currently showing Connecticut CHOW records from CMS {cms_release} data."
        )
        source_label = f"Connecticut SNF CHOW (CMS {cms_release} release)"
        ct_only = True
    else:
        scope_note = (
            f"National skilled nursing facility CHOW records from the CMS {cms_release} "
            "Skilled Nursing Facility Change of Ownership release."
        )
        source_label = f"CMS SNF Change of Ownership ({cms_release} release)"

    source_hashes: dict[str, str] = {}
    for p in source_paths or []:
        try:
            if p.is_file():
                key = str(p.relative_to(REPO_ROOT)) if p.is_relative_to(REPO_ROOT) else str(p)
                source_hashes[key.replace("\\", "/")] = _sha256_file(p)
        except OSError:
            continue

    return {
        "scope_note": scope_note,
        "is_ct_only": ct_only,
        "source_label": source_label,
        "cms_release": cms_release,
        "coverage_date_min": date_min,
        "coverage_date_max": date_max,
        "event_count": len(records),
        "sources": sources,
        "source_sha256": source_hashes,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build chow_index.json for /chow")
    parser.add_argument("--zip", type=Path, default=DEFAULT_ZIP, help="CMS CHOW zip path")
    parser.add_argument("--csv", type=Path, action="append", default=[], help="Additional CSV path(s)")
    parser.add_argument("--chow-dir", type=Path, default=DEFAULT_CHOW_DIR, help="Directory of CHOW CSVs")
    parser.add_argument("--ct-only", action="store_true", help="Mark output as CT-only scope")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--no-zip", action="store_true", help="Skip default CMS zip")
    args = parser.parse_args()

    raw_rows: list[dict] = []
    sources: list[str] = []
    source_paths: list[Path] = []

    if args.chow_dir.is_dir():
        for p in sorted(args.chow_dir.glob("*.csv")):
            raw_rows.extend(load_rows_from_csv_paths([p]))
            sources.append(str(p.relative_to(REPO_ROOT)))
            source_paths.append(p)

    for p in args.csv:
        if p.is_file():
            raw_rows.extend(load_rows_from_csv_paths([p]))
            sources.append(str(p))
            source_paths.append(p)

    if not args.no_zip and args.zip.is_file():
        zip_rows = load_rows_from_zip(args.zip)
        if not raw_rows:
            raw_rows = zip_rows
        else:
            raw_rows.extend(zip_rows)
        sources.append(str(args.zip.relative_to(REPO_ROOT)))
        source_paths.append(args.zip)

    if not raw_rows:
        raise SystemExit("No CHOW rows loaded. Provide --zip, --csv, or data/chow/*.csv")

    records, summary = build_records(raw_rows)
    # Canonical CMS zip members use SNF_CHOW_Q2_2026.csv; prefer explicit Q2 when present.
    release_hint = ""
    for p in source_paths:
        name = p.name.lower()
        if "q2" in name or (p.is_file() and p.suffix.lower() == ".zip"):
            try:
                if p.suffix.lower() == ".zip":
                    with zipfile.ZipFile(p) as zf:
                        members = " ".join(zf.namelist()).lower()
                        if "q2_2026" in members or "2026-q2" in members:
                            release_hint = "Q2 2026"
                            break
                        if "2026-q1" in members or "2026.04.01" in members:
                            release_hint = "Q1 2026"
                            break
                elif "q2" in name:
                    release_hint = "Q2 2026"
                    break
                elif "q1" in name:
                    release_hint = "Q1 2026"
                    break
            except (OSError, zipfile.BadZipFile):
                continue

    meta = infer_meta(
        records,
        sources,
        args.ct_only,
        source_paths=source_paths,
        release_hint=release_hint,
    )

    payload = {"meta": meta, "summary": summary, "records": records}
    args.output.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {len(records)} records to {args.output}")
    print(
        f"meta cms_release={meta.get('cms_release')} "
        f"coverage={meta.get('coverage_date_min')}..{meta.get('coverage_date_max')} "
        f"sha256_keys={list((meta.get('source_sha256') or {}).keys())}"
    )


if __name__ == "__main__":
    main()
