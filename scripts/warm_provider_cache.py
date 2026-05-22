#!/usr/bin/env python3
"""
Optional post-deploy HTTP warmup for in-memory provider HTML cache.

Only warmed URLs benefit; each Gunicorn worker has its own cache (~15k facilities
cannot all fit). Warming costs CPU (cold MISS ~5–15s each) — keep modest on 1-CPU Render.

ANCHOR_CCNS are deploy smoke fixtures, not high-traffic facilities.

Examples:
  python scripts/warm_provider_cache.py --base-url https://www.pbj320.com --limit 20 --passes 3
  python scripts/warm_provider_cache.py --anchors-only   # smoke only (3 CCNs)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = "https://www.pbj320.com"
UA = "PBJ320ProviderWarm/1.0"
# Deploy smoke + /warmup probe CCNs (always warmed first)
# Smoke-test fixtures only (deploy checks) — not high-traffic facilities.
ANCHOR_CCNS = ("075325", "335513", "075263")


def _normalize_ccn(raw: object) -> str | None:
    c = str(raw or "").strip().zfill(6)[-6:]
    return c if len(c) == 6 and c.isdigit() else None


def load_ccn_list(
    *,
    base_url: str,
    index_path: Path | None,
    extra_ccns: list[str],
    limit: int,
) -> list[str]:
    """Unique CCNs: anchors first, then extras, then search index facilities."""
    out: list[str] = []
    seen: set[str] = set()

    def add(ccn: str | None) -> None:
        if not ccn or ccn in seen:
            return
        seen.add(ccn)
        out.append(ccn)

    for raw in ANCHOR_CCNS:
        add(_normalize_ccn(raw))
    for raw in extra_ccns:
        add(_normalize_ccn(raw))

    if index_path and index_path.is_file():
        with index_path.open(encoding="utf-8") as f:
            data = json.load(f)
    else:
        url = base_url.rstrip("/") + "/search_index.json"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))

    for fac in data.get("f") or []:
        if len(out) >= limit:
            break
        add(_normalize_ccn(fac.get("c")))
    return out[:limit]


def fetch_provider(
    base_url: str,
    ccn: str,
    *,
    timeout: float,
) -> tuple[int, str, str, float]:
    url = f"{base_url.rstrip('/')}/provider/{ccn}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
            elapsed = time.perf_counter() - t0
            cache = resp.headers.get("X-PBJ-Provider-Cache", "")
            return resp.status, cache, "", elapsed
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - t0
        cache = e.headers.get("X-PBJ-Provider-Cache", "")
        err_body = (e.read() if e.fp else b"")[:200]
        return e.code, cache, err_body.decode("utf-8", errors="replace"), elapsed


def warm_providers(
    *,
    base_url: str,
    ccns: list[str],
    passes_per_ccn: int,
    timeout: float,
    delay_s: float,
) -> list[tuple[str, int, str, float]]:
    """Round-robin passes: pass i hits ccns[i % len(ccns)] to spread across workers."""
    if not ccns:
        return []
    results: list[tuple[str, int, str, float]] = []
    total = passes_per_ccn * len(ccns)
    step = 0
    for p in range(passes_per_ccn):
        for ccn in ccns:
            step += 1
            status, cache, err, elapsed = fetch_provider(base_url, ccn, timeout=timeout)
            results.append((ccn, status, cache or err[:80], elapsed))
            tag = cache or ("err" if status != 200 else "?")
            print(
                f"[{step}/{total}] {ccn} -> {status} "
                f"cache={tag} {elapsed:.1f}s",
                flush=True,
            )
            if delay_s > 0 and step < total:
                time.sleep(delay_s)
    return results


def summarize(results: list[tuple[str, int, str, float]]) -> int:
    ok = sum(1 for _, st, _, _ in results if st == 200)
    hits = sum(1 for _, st, cache, _ in results if st == 200 and cache.upper() == "HIT")
    misses = sum(1 for _, st, cache, _ in results if st == 200 and cache.upper() == "MISS")
    busy = sum(1 for _, st, _, _ in results if st == 503)
    print("---")
    print(f"requests: {len(results)}  ok={ok}  cache_hit={hits}  cache_miss={misses}  503={busy}")
    if misses and not hits:
        print("note: all MISS — cold renders may still be in flight; re-run once.")
    elif hits:
        print("note: HIT responses mean at least one worker has cached HTML for those CCNs.")
    return 0 if ok >= len(results) // 2 and busy == 0 else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--base-url",
        default=os.environ.get("PBJ_WARM_BASE_URL", DEFAULT_BASE),
        help=f"Site origin (default {DEFAULT_BASE} or PBJ_WARM_BASE_URL)",
    )
    p.add_argument(
        "--index",
        type=Path,
        default=None,
        help=f"Local search_index.json (default: {ROOT / 'search_index.json'} if present, else fetch from base-url)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=int(os.environ.get("PBJ_WARM_PROVIDER_LIMIT", "20")),
        help="Max CCNs to warm including anchors (default 20; not all ~15k facilities)",
    )
    p.add_argument(
        "--passes",
        type=int,
        default=int(os.environ.get("PBJ_WARM_PROVIDER_PASSES", "3")),
        help="Full rounds over the CCN list (default 3; each pass costs CPU on cold MISS)",
    )
    p.add_argument(
        "--ccns",
        default="",
        help="Comma-separated extra CCNs (merged with anchors and index)",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("PBJ_WARM_PROVIDER_TIMEOUT", "120")),
        help="Per-request timeout seconds (default 120)",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=float(os.environ.get("PBJ_WARM_PROVIDER_DELAY", "0.5")),
        help="Seconds between requests (default 0.5)",
    )
    p.add_argument(
        "--anchors-only",
        action="store_true",
        help="Only warm deploy anchor CCNs (fast smoke warm)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    base = args.base_url.rstrip("/")
    index_path = args.index
    if index_path is None:
        local_index = ROOT / "search_index.json"
        index_path = local_index if local_index.is_file() else None

    extra = [x.strip() for x in args.ccns.split(",") if x.strip()]
    limit = len(ANCHOR_CCNS) if args.anchors_only else max(args.limit, len(ANCHOR_CCNS))

    print(f"Warming provider cache at {base} (limit={limit}, passes={args.passes})")
    try:
        ccns = load_ccn_list(
            base_url=base,
            index_path=index_path,
            extra_ccns=extra,
            limit=limit,
        )
    except Exception as e:
        print(f"FAIL | could not load CCN list: {e}", file=sys.stderr)
        return 1

    print(f"CCNs ({len(ccns)}): {', '.join(ccns[:8])}{'...' if len(ccns) > 8 else ''}")
    results = warm_providers(
        base_url=base,
        ccns=ccns,
        passes_per_ccn=args.passes,
        timeout=args.timeout,
        delay_s=args.delay,
    )
    return summarize(results)


if __name__ == "__main__":
    raise SystemExit(main())
