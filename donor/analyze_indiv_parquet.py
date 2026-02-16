"""
Analyze FEC indiv parquet to find massive committees (unsustainable via API).

Usage:
  python -m donor.analyze_indiv_parquet [path/to/indiv26.parquet]
  python -m donor.analyze_indiv_parquet --threshold 50000 --top 50

Output: distribution of committees by contribution count, top N by size,
and a suggested list of "massive" committee IDs (those above threshold).
Use that list to ensure we serve those from local bulk only, never API.
"""

from pathlib import Path
import argparse
import sys


def main() -> None:
    p = argparse.ArgumentParser(description="Analyze indiv parquet: find massive committees")
    p.add_argument(
        "parquet_path",
        nargs="*",
        default=None,
        help="Path to parquet (parts joined if split by spaces; default: donor/FEC data/indiv26.parquet)",
    )
    p.add_argument(
        "--threshold",
        type=int,
        default=50000,
        help="Count above which committee is 'massive' / unsustainable for API (default: 50000)",
    )
    p.add_argument(
        "--top",
        type=int,
        default=30,
        help="Show top N committees by contribution count (default: 30)",
    )
    p.add_argument(
        "--output-ids",
        action="store_true",
        help="Print only massive committee IDs (one per line) for use in code",
    )
    args = p.parse_args()

    data_dir = Path(__file__).resolve().parent / "FEC data"
    path_parts = args.parquet_path if isinstance(args.parquet_path, list) else [args.parquet_path] if args.parquet_path else []
    path_str = " ".join(str(p) for p in path_parts).strip() if path_parts else None
    path = Path(path_str) if path_str else data_dir / "indiv26.parquet"
    if not path.exists():
        print(f"Parquet not found: {path}", file=sys.stderr)
        print('Run with a path, e.g.: python -m donor.analyze_indiv_parquet "donor/FEC data/indiv26.parquet"', file=sys.stderr)
        sys.exit(1)

    try:
        import pandas as pd
    except ImportError:
        print("Requires pandas.", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {path}...", flush=True)
    df = pd.read_parquet(path, columns=["CMTE_ID"])
    total_rows = len(df)

    counts = df["CMTE_ID"].value_counts()
    n_committees = len(counts)

    thresholds = [1_000, 10_000, 50_000, 100_000, 250_000, 500_000, 1_000_000, 5_000_000]
    print(f"\nTotal rows: {total_rows:,}  |  Committees: {n_committees:,}\n")
    print("Distribution (committees with at least X contributions):")
    print("-" * 50)
    for t in thresholds:
        n = (counts >= t).sum()
        pct = 100 * n / n_committees if n_committees else 0
        print(f"  >= {t:>10,}: {n:>6,} committees ({pct:5.2f}%)")

    massive = counts[counts >= args.threshold]
    print(f"\n'Massive' (>= {args.threshold:,} contributions): {len(massive):,} committees")
    if args.output_ids:
        for cid in massive.index.tolist():
            print(cid)
        sys.exit(0)

    print(f"\nTop {args.top} committees by contribution count:")
    print("-" * 70)
    top_df = counts.head(args.top)
    for i, (cid, cnt) in enumerate(top_df.items(), 1):
        mark = " <-- MASSIVE" if cnt >= args.threshold else ""
        print(f"  {i:3}. {cid}  {cnt:>12,}{mark}")

    # Try to resolve names from committee master
    cm_paths = [
        data_dir.parent / "data" / "fec_committee_master" / "cm26.csv",
        data_dir / "cm26.csv",
    ]
    cm_map = {}
    for cp in cm_paths:
        if cp.exists():
            try:
                cm = pd.read_csv(cp, dtype=str, usecols=["CMTE_ID", "CMTE_NM"], low_memory=False)
                cm_map.update(dict(zip(cm["CMTE_ID"].str.strip(), cm["CMTE_NM"])))
            except Exception:
                pass
            break

    if cm_map:
        print("\nTop committees with names:")
        print("-" * 70)
        for i, (cid, cnt) in enumerate(top_df.items(), 1):
            name = cm_map.get(str(cid).strip(), "(unknown)")[:50]
            mark = " [MASSIVE]" if cnt >= args.threshold else ""
            print(f"  {i:3}. {cid}  {cnt:>12,}  {name}{mark}")

    print(f"\nSuggested massive IDs (>= {args.threshold:,}): {sorted(massive.index.tolist())}")
    print("Use these to serve from local bulk only, never API.")

    # Quick check: would ActBlue/WinRed be found?
    check_ids = [("C00401224", "ActBlue"), ("C00694323", "WinRed")]
    norm_index = {str(k).strip().upper(): v for k, v in counts.items()}
    for cid, label in check_ids:
        cnt = norm_index.get(cid.upper(), 0)
        status = f"{cnt:,} rows (bulk would work)" if cnt else "NOT FOUND (would fall back to API)"
        print(f"\n  {label} ({cid}): {status}")


if __name__ == "__main__":
    main()
