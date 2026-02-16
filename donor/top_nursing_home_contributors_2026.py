"""
Find top FEC contributors (by total amount) who match nursing home owners.
Uses all available parquet files (indiv26, indiv24, indiv22, indiv20). Prefers owner-extract
parquet when available (small, all committees). Falls back to full, then conduit-only.
Sorts by money to surface big players.

Usage:
  python -m donor.top_nursing_home_contributors_2026 [--top 500] [--out top_contributors.csv]
  python -m donor.top_nursing_home_contributors_2026 --top 0   # all matches (no limit)

Output: CSV with Owner (CMS), FEC name, total amount, # contributions, top_recipients, facilities, years_included.
"""

from pathlib import Path
from typing import Dict, List, Tuple, Any

import pandas as pd

from donor.owner_contributor_utils import build_owner_lookup, find_owner, normalize_name
from donor.common_names import is_common_name, is_likely_conflated


def _load_committee_master(data_dir: Path, base_path: Path) -> Dict[str, str]:
    """Load CMTE_ID -> CMTE_NM from cm*.csv files."""
    cm_map: Dict[str, str] = {}
    for fname in reversed(["cm26_2025_2026.csv", "cm24_2023_2024.csv", "cm22_2021_2022.csv", "cm20_2019_2020.csv",
                          "cm26.csv", "cm24.csv", "cm22.csv", "cm20.csv"]):
        for subdir in [data_dir, base_path / "data" / "fec_committee_master"]:
            path = subdir / fname
            if path.exists():
                try:
                    cm = pd.read_csv(path, dtype=str, usecols=["CMTE_ID", "CMTE_NM"], low_memory=False, on_bad_lines="skip")
                    for _, row in cm.iterrows():
                        cid = str(row.get("CMTE_ID") or "").strip()
                        nm = str(row.get("CMTE_NM") or "").strip()
                        if cid and cid != "nan":
                            cm_map[cid] = nm
                except Exception:
                    pass
                break
    return cm_map


def main():
    import argparse
    base = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(description="Top nursing home owner contributors from FEC bulk parquet")
    p.add_argument("--top", type=int, default=500, help="Top N to output (0 = all matches)")
    p.add_argument("--out", default=None, help="Output CSV path")
    args = p.parse_args()

    data_dir = base / "FEC data"
    owners_path = base / "output" / "owners_database.csv"
    if not owners_path.exists():
        print(f"Owners database not found: {owners_path}", flush=True)
        return 1

    cycle_specs = [
        ("indiv26_owners.parquet", "indiv26.parquet", "indiv26_conduits.parquet", 2025, 2026),
        ("indiv24_owners.parquet", "indiv24.parquet", "indiv24_conduits.parquet", 2023, 2024),
        ("indiv22_owners.parquet", "indiv22.parquet", "indiv22_conduits.parquet", 2021, 2022),
        ("indiv20_owners.parquet", "indiv20.parquet", "indiv20_conduits.parquet", 2019, 2020),
    ]
    all_dfs: List[pd.DataFrame] = []
    years_included: List[int] = []
    for owners_fname, full_fname, conduit_fname, y1, y2 in cycle_specs:
        path = data_dir / owners_fname
        if not path.exists():
            path = data_dir / full_fname
        if not path.exists():
            path = data_dir / conduit_fname
        if not path.exists():
            continue
        try:
            print(f"Loading {path.name}...", flush=True)
            df = pd.read_parquet(path, columns=["NAME", "TRANSACTION_AMT", "CMTE_ID"])
            df["TRANSACTION_AMT"] = pd.to_numeric(df["TRANSACTION_AMT"], errors="coerce").fillna(0)
            df["name_clean"] = df["NAME"].fillna("").astype(str).str.strip()
            df["cycle"] = f"{y1}-{y2}"
            all_dfs.append(df)
            years_included.extend([y1, y2])
            print(f"  Loaded {len(df):,} rows ({y1}-{y2})", flush=True)
        except Exception as e:
            print(f"  [WARN] Could not read {path}: {e}", flush=True)
    if not all_dfs:
        print("No parquet found. Build with: python -m donor.fec_indiv_bulk build donor/FEC data/indiv26.zip", flush=True)
        return 1

    print("Concatenating...", flush=True)
    df = pd.concat(all_dfs, ignore_index=True)
    years_included = sorted(set(years_included))
    print(f"Combined {len(df):,} rows from years {years_included}", flush=True)

    print("Aggregating by contributor...", flush=True)
    agg_all = df.groupby("name_clean", as_index=False).agg(
        total_amount=("TRANSACTION_AMT", "sum"),
        num_contributions=("TRANSACTION_AMT", "count"),
    )
    by_committee = df.groupby(["name_clean", "CMTE_ID"], as_index=False).agg(amt=("TRANSACTION_AMT", "sum"))
    by_committee = by_committee.sort_values(["name_clean", "amt"], ascending=[True, False])
    n_names = by_committee["name_clean"].nunique()
    print(f"Building top-5 committees per contributor ({n_names:,} names)...", flush=True)
    top5_by_name: Dict[str, List[Tuple[str, float]]] = {}
    prog_interval = max(50_000, n_names // 20)
    for ni, (name, grp) in enumerate(by_committee.groupby("name_clean", sort=False)):
        if (ni + 1) % prog_interval == 0:
            print(f"  ... {ni + 1:,} / {n_names:,}", flush=True)
        for _, row in grp.head(5).iterrows():
            cid = str(row.get("CMTE_ID") or "").strip()
            amt = float(row.get("amt", 0))
            if name not in top5_by_name:
                top5_by_name[name] = []
            top5_by_name[name].append((cid, amt))
    del by_committee
    print(f"  Done. {len(top5_by_name):,} contributors with committee breakdown.", flush=True)

    print("Loading committee master...", flush=True)
    cm_map = _load_committee_master(data_dir, base)

    print(f"Loading owners from {owners_path}...", flush=True)
    owners_df = pd.read_csv(owners_path, dtype=str, low_memory=False)
    lookup = build_owner_lookup(owners_df)

    n_contributors = len(agg_all)
    print(f"Matching {n_contributors:,} unique contributors to owners...", flush=True)
    results = []
    progress_interval = max(100_000, n_contributors // 15)
    for i, (_, r) in enumerate(agg_all.iterrows()):
        if (i + 1) % progress_interval == 0 or (i + 1) == n_contributors:
            print(f"  ... checked {i + 1:,} / {n_contributors:,}, matched {len(results):,}", flush=True)
        name = (r["name_clean"] or "").strip()
        if not name or len(name) < 3:
            continue
        donor_norm = normalize_name(name)
        owner_row = find_owner(donor_norm, lookup)
        if owner_row is None:
            continue
        total = float(r["total_amount"])
        count = int(r["num_contributions"])
        facilities = (owner_row.get("facilities") or "")
        fac_list = [x.strip() for x in str(facilities).split(",") if x.strip()]
        owner_display = owner_row.get("owner_name_original", owner_row.get("owner_name", ""))

        top_recipients = []
        for cid, amt in top5_by_name.get(name, []):
            cname = cm_map.get(cid, cid) if cid else "Unknown"
            if len(cname) > 40:
                cname = cname[:37] + "..."
            top_recipients.append(f"{cname} ${amt:,.0f}")
        top_recipients_str = "; ".join(top_recipients) if top_recipients else ""

        owner_type = owner_row.get("owner_type", "")
        conflated = is_likely_conflated(name, owner_type, count)
        results.append({
            "owner_cms": owner_display,
            "fec_name": name,
            "total_amount": total,
            "num_contributions": count,
            "top_recipients": top_recipients_str[:300] + ("..." if len(top_recipients_str) > 300 else ""),
            "facilities": facilities[:200] + ("..." if len(str(facilities)) > 200 else ""),
            "owner_type": owner_type,
            "num_facilities": len(fac_list),
            "is_common_name": is_common_name(name, owner_type),
            "likely_conflated": conflated,
        })

    # Sort: non-conflated first by amount desc, then conflated by amount desc (demotes common+high-contrib)
    results.sort(key=lambda x: (x["likely_conflated"], -x["total_amount"]))
    top = results[: args.top] if args.top > 0 else results

    print(f"\nTop {len(top)} nursing home owners by FEC contributions ({years_included}):", flush=True)
    print("-" * 90, flush=True)
    for i, row in enumerate(top, 1):
        print(f"  {i:3}. {row['owner_cms'][:40]:<40}  ${row['total_amount']:>12,.0f}  ({row['num_contributions']} contrib)", flush=True)

    out_path = args.out
    if out_path:
        out_path = Path(out_path)
    else:
        out_path = data_dir / "top_nursing_home_contributors_2026.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df = pd.DataFrame(top)
    out_df["years_included"] = ",".join(str(y) for y in years_included)
    out_df.to_csv(out_path, index=False)
    print(f"\nWrote {len(top)} rows to {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
