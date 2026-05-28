#!/usr/bin/env python3
"""Audit provider URLs and classify status causes.

Usage examples:
  python scripts/audit_provider_url_statuses.py
  python scripts/audit_provider_url_statuses.py --input bing-export.csv
  python scripts/audit_provider_url_statuses.py --input affected.txt --no-http
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterable
from urllib import error, request

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as pbj_app  # noqa: E402
from ownership.owner_indexability import provider_ccns_for_sitemap  # noqa: E402


URL_RE = re.compile(r"https?://[^\s\"'<>]+/provider/[^\s\"'<>]+", re.IGNORECASE)
CCN_TYPE_RE = re.compile(r"[A-Za-z]")


def _discover_bing_like_inputs(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        name = p.name.lower()
        if any(k in name for k in ("bing", "crawl", "scan")) and p.suffix.lower() in {
            ".txt",
            ".csv",
            ".tsv",
            ".log",
            ".json",
            ".jsonl",
            ".md",
        }:
            out.append(p)
    return sorted(out)


def _extract_urls_from_text(text: str) -> list[str]:
    urls = URL_RE.findall(text or "")
    seen = set()
    ordered = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            ordered.append(u)
    return ordered


def _read_urls(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    urls = _extract_urls_from_text(text)
    if urls:
        return urls
    if path.suffix.lower() in {".csv", ".tsv"}:
        sep = "," if path.suffix.lower() == ".csv" else "\t"
        rows = text.splitlines()
        if not rows:
            return []
        reader = csv.DictReader(rows, delimiter=sep)
        vals = []
        for row in reader:
            for v in row.values():
                if isinstance(v, str) and "/provider/" in v:
                    vals.extend(_extract_urls_from_text(v))
        return vals
    return []


def _http_status(url: str, timeout: int = 20) -> str:
    req = request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return str(resp.getcode())
    except error.HTTPError as exc:
        return str(exc.code)
    except Exception:
        return "ERR"


def _load_ccn_set(path: Path, col: str) -> set[str]:
    out: set[str] = set()
    for chunk in pd.read_csv(path, usecols=[col], dtype=str, chunksize=200000, low_memory=False):
        s = (
            chunk[col]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
            .str.replace(r"\.0$", "", regex=True)
        )
        s = s[s != ""]
        out.update(s.str.zfill(6).tolist())
    return out


def _classify(
    status: str,
    in_provider_info: bool,
    in_fq: bool,
    in_sqlite: bool,
    ccn: str,
) -> str:
    malformed = not bool(pbj_app.normalize_ccn(ccn))
    has_alpha = bool(CCN_TYPE_RE.search(ccn))
    status_int = int(status) if status.isdigit() else -1

    if malformed:
        return "malformed URL"
    if status_int in (499, 502):
        return "valid page affected by deploy-window 502/499"
    if status_int == 429:
        return "valid page temporarily rate-limited"
    if status_int == 404 and in_provider_info and (in_fq or in_sqlite) and has_alpha:
        return "alphanumeric ID handling bug"
    if (not in_fq and not in_sqlite) and in_provider_info:
        return "invalid/stale provider ID"
    if status_int in {500, 503, 504}:
        return "real route/server bug"
    if status_int == 404 and not in_provider_info:
        return "invalid/stale provider ID"
    if status_int == 200:
        return "valid page (200)"
    return "real route/server bug"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=str, default="", help="Path to Bing/scan export or URL list")
    ap.add_argument("--no-http", action="store_true", help="Skip live HTTP probes")
    ap.add_argument("--out", type=str, default="", help="Optional output CSV path")
    args = ap.parse_args()

    urls: list[str] = []
    source = ""
    if args.input:
        p = Path(args.input)
        if not p.is_absolute():
            p = ROOT / p
        if not p.exists():
            raise SystemExit(f"Input not found: {p}")
        urls = _read_urls(p)
        source = str(p)
    else:
        candidates = _discover_bing_like_inputs(ROOT)
        for p in candidates:
            got = _read_urls(p)
            if got:
                urls = got
                source = str(p)
                break

    if not urls:
        raise SystemExit("No provider URLs found. Pass --input with a URL list/export.")

    # normalize unique URLs preserving order
    seen = set()
    norm_urls = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            norm_urls.append(u)
    urls = norm_urls

    pi_ccn = _load_ccn_set(ROOT / "provider_info_combined_latest.csv", "ccn")
    fq_ccn = _load_ccn_set(ROOT / "facility_quarterly_metrics.csv", "PROVNUM")

    search = json.load(open(ROOT / "search_index.json", encoding="utf-8"))
    search_ccn = {
        str(f.get("c") or "").strip().upper().zfill(6)
        for f in (search.get("f") or [])
        if str(f.get("c") or "").strip()
    }
    sitemap_ccn = set(provider_ccns_for_sitemap()[0])

    con = sqlite3.connect(ROOT / "data" / "provider_indexes" / "facility_quarterly_provider.sqlite")
    cur = con.cursor()

    status_map: dict[str, str] = {}
    if args.no_http:
        status_map = {u: "SKIP" for u in urls}
    else:
        with ThreadPoolExecutor(max_workers=12) as ex:
            results = ex.map(_http_status, urls)
            status_map = {u: st for u, st in zip(urls, results)}

    rows = []
    for u in urls:
        raw_id = u.rsplit("/", 1)[-1].strip()
        norm = pbj_app.normalize_ccn(raw_id)
        ccn = norm or raw_id
        id_type = "alphanumeric" if CCN_TYPE_RE.search(raw_id) else "numeric-only"
        status = status_map[u]
        in_provider_info = bool(norm and norm in pi_ccn)
        in_fq = bool(norm and norm in fq_ccn)
        in_sqlite = False
        if norm:
            in_sqlite = (
                cur.execute(
                    "select 1 from facility_quarterly where provnum = ? collate nocase limit 1",
                    (norm,),
                ).fetchone()
                is not None
            )
        in_sitemap = bool(norm and norm in sitemap_ccn)
        in_search = bool(norm and norm in search_ccn)
        cls = _classify(status, in_provider_info, in_fq, in_sqlite, raw_id)
        rows.append(
            {
                "url": u,
                "http_status": status,
                "provider_id": ccn,
                "id_type": id_type,
                "exists_provider_info": in_provider_info,
                "exists_facility_or_sqlite": (in_fq or in_sqlite),
                "exists_in_sitemap_or_search": (in_sitemap or in_search),
                "classification": cls,
            }
        )

    con.close()

    # print markdown-ish table for quick review
    print(f"Source: {source or 'manual/discovered'}")
    print("url\thttp_status\tprovider_id\tid_type\texists_provider_info\texists_facility_or_sqlite\texists_in_sitemap_or_search\tclassification")
    for r in rows:
        print(
            f"{r['url']}\t{r['http_status']}\t{r['provider_id']}\t{r['id_type']}\t"
            f"{r['exists_provider_info']}\t{r['exists_facility_or_sqlite']}\t"
            f"{r['exists_in_sitemap_or_search']}\t{r['classification']}"
        )

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["classification"]] = counts.get(r["classification"], 0) + 1
    print("\nclassification_counts")
    for k in sorted(counts):
        print(f"{k}\t{counts[k]}")

    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\nWrote: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
