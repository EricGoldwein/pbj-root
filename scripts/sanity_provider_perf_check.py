#!/usr/bin/env python3
"""Sanity checks for provider perf / bot policy (local Flask client or production HTTP)."""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

HUMAN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
GPTBOT = "Mozilla/5.0 (compatible; GPTBot/1.0; +https://openai.com/gptbot)"
GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


def _http_get(url: str, *, ua: str, timeout: float = 180.0) -> tuple[int, dict, float, int]:
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "text/html,application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            elapsed = round((time.perf_counter() - t0) * 1000, 1)
            headers = {k: v for k, v in resp.headers.items()}
            return resp.status, headers, elapsed, len(body)
    except urllib.error.HTTPError as e:
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        headers = {k: v for k, v in (e.headers.items() if e.headers else [])}
        try:
            body = e.read()
        except Exception:
            body = b""
        return e.code, headers, elapsed, len(body)


def _pick_random_ccns(n: int, *, seed: int, base_url: str = "") -> list[str]:
    path = ROOT / "search_index.json"
    ua = "PBJ320ProdCheck/1.0"
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        origin = (base_url or "https://www.pbj320.com").rstrip("/")
        url = f"{origin}/search_index.json"
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    ccns = []
    for f in data.get("f") or []:
        raw = f.get("c") or f.get("ccn") or f.get("provnum")
        c = str(raw or "").strip().zfill(6)[-6:]
        if len(c) == 6 and c.isdigit():
            ccns.append(c)
    if len(ccns) < n:
        raise RuntimeError(f"search_index has only {len(ccns)} CCNs")
    rng = random.Random(seed)
    return rng.sample(ccns, n)


def _run_production_checks(base_url: str, ccn: str, entity_id: int) -> list[tuple[str, bool, str]]:
    base = base_url.rstrip("/")
    results: list[tuple[str, bool, str]] = []

    def note(name: str, ok: bool, detail: str) -> None:
        results.append((f"[PROD] {name}", ok, detail))

    # 1–2: human HTML + headers (first request may be cold)
    caches: list[str] = []
    timings: list[str] = []
    last_status = 0
    last_len = 0
    last_cc = ""
    for i in range(3):
        st, hdr, ms, blen = _http_get(f"{base}/provider/{ccn}", ua=HUMAN)
        cache_h = hdr.get("X-PBJ-Provider-Cache") or hdr.get("x-pbj-provider-cache") or "?"
        cc_ctl = hdr.get("Cache-Control") or hdr.get("cache-control") or ""
        caches.append(cache_h)
        timings.append(f"#{i+1} {cache_h} {ms}ms status={st}")
        last_status, last_len, last_cc = st, blen, cc_ctl
        if i < 2:
            time.sleep(0.3)

    note(
        "human provider HTML",
        last_status == 200 and last_len > 2000,
        f"status={last_status} len={last_len}",
    )
    note(
        "headers X-PBJ-Provider-Cache + Cache-Control",
        "max-age=300" in last_cc and "private" in last_cc,
        f"last_cache={caches[-1]} Cache-Control={last_cc}",
    )
    note(
        "3x same provider cache progression",
        caches[1] == "HIT" and caches[2] == "HIT",
        "; ".join(timings) + (" (first may be HIT if already warm in prod)" if caches[0] == "HIT" else ""),
    )

    # GPTBot uncached: CCN not warmed in this run (smoke anchors are often already hot in prod)
    try:
        fresh_pool = _pick_random_ccns(50, seed=99, base_url=base)
        uncached = next((c for c in fresh_pool if c != ccn), fresh_pool[0])
    except Exception:
        uncached = "165475"
    st, hdr, ms, _ = _http_get(f"{base}/provider/{uncached}", ua=GPTBOT)
    note(
        "GPTBot uncached provider",
        st == 429,
        f"ccn={uncached} status={st} cache={hdr.get('X-PBJ-Provider-Cache', hdr.get('x-pbj-provider-cache', '?'))} {ms}ms",
    )

    # GPTBot cached (warm ccn with human first)
    _http_get(f"{base}/provider/{ccn}", ua=HUMAN)
    st, hdr, ms, _ = _http_get(f"{base}/provider/{ccn}", ua=GPTBOT)
    ch = hdr.get("X-PBJ-Provider-Cache") or hdr.get("x-pbj-provider-cache")
    note(
        "GPTBot cached provider",
        st == 200 and ch == "HIT",
        f"status={st} cache={ch} {ms}ms",
    )

    st, _, ms, _ = _http_get(f"{base}/entity/{entity_id}", ua=GPTBOT)
    note("GPTBot entity", st == 429, f"status={st} {ms}ms")

    st, hdr, ms, _ = _http_get(f"{base}/provider/{uncached}", ua=GOOGLEBOT)
    note(
        "Googlebot uncached provider not blocked",
        st in (200, 404) and st != 429,
        f"status={st} cache={hdr.get('X-PBJ-Provider-Cache', hdr.get('x-pbj-provider-cache', '?'))} {ms}ms",
    )

    for path in ("/", "/search_index.json", "/state/wyoming", "/data-sources"):
        st, _, ms, _ = _http_get(f"{base}{path}", ua=GPTBOT, timeout=60)
        note(
            f"GPTBot not blocked {path}",
            st in (200, 301, 302),
            f"status={st} {ms}ms",
        )

    return results


def _run_cold_sample(base_url: str, *, n: int, seed: int, delay_s: float) -> list[dict]:
    base = base_url.rstrip("/")
    ccns = _pick_random_ccns(n, seed=seed, base_url=base)
    rows: list[dict] = []
    for i, ccn in enumerate(ccns):
        if i:
            time.sleep(delay_s)
        st, hdr, ms, blen = _http_get(f"{base}/provider/{ccn}", ua=HUMAN)
        rows.append({
            "ccn": ccn,
            "status": st,
            "elapsed_ms": ms,
            "cache": hdr.get("X-PBJ-Provider-Cache") or hdr.get("x-pbj-provider-cache") or "?",
            "cache_control": hdr.get("Cache-Control") or hdr.get("cache-control") or "",
            "503": st == 503,
            "body_len": blen,
        })
    return rows


def _run_checks_local(*, render_sim: bool) -> list[tuple[str, bool, str]]:
    label = "RENDER_SIM" if render_sim else "LOCAL_DEV"
    if render_sim:
        os.environ["RENDER"] = "1"
        os.environ["PBJ_SKIP_PROVIDER_PAGE_CACHE"] = "0"
        os.environ.pop("PBJ_SKIP_PROVIDER_PAGE_CACHE", None)
        os.environ.setdefault("PBJ_PROVIDER_PERF_LOG", "1")
    else:
        os.environ.pop("RENDER", None)
        os.environ.pop("RENDER_SERVICE_ID", None)
        os.environ.setdefault("PBJ_SKIP_PROVIDER_PAGE_CACHE", "1")

    for mod in list(sys.modules):
        if mod in ("app", "pbj_provider_perf") or mod.startswith("app."):
            del sys.modules[mod]

    from app import app, clear_provider_page_cache
    from pbj_provider_perf import (
        ai_heavy_routes_cache_only_enabled,
        provider_browser_cache_control,
        provider_perf_log_enabled,
    )

    results: list[tuple[str, bool, str]] = []
    ccn = "335513"
    entity_id = 9

    def note(name: str, ok: bool, detail: str) -> None:
        results.append((f"[{label}] {name}", ok, detail))

    with app.test_client() as client:
        if render_sim:
            note(
                "env Render defaults",
                ai_heavy_routes_cache_only_enabled() and provider_perf_log_enabled(),
                f"ai_cache_only={ai_heavy_routes_cache_only_enabled()} cache_ctl={provider_browser_cache_control()}",
            )
        else:
            note(
                "env local: no Render bot lock",
                not ai_heavy_routes_cache_only_enabled(),
                f"ai_cache_only={ai_heavy_routes_cache_only_enabled()}",
            )
            r = client.get(f"/provider/{ccn}", headers={"User-Agent": HUMAN})
            html = r.get_data(as_text=True)
            note(
                "human provider HTML",
                r.status_code == 200 and len(html) > 2000,
                f"status={r.status_code} len={len(html)}",
            )
            for path in ("/", "/search_index.json", "/state/wyoming", "/data-sources"):
                rb = client.get(path, headers={"User-Agent": GPTBOT})
                note(f"GPTBot not blocked {path}", rb.status_code in (200,  302), f"status={rb.status_code}")
            return results

        clear_provider_page_cache()
        uncached_ccn = "075325"
        caches: list[str] = []
        timings: list[str] = []
        for i in range(3):
            t0 = time.perf_counter()
            r = client.get(f"/provider/{ccn}", headers={"User-Agent": HUMAN})
            ms = round((time.perf_counter() - t0) * 1000, 1)
            cache_h = r.headers.get("X-PBJ-Provider-Cache", "?")
            caches.append(cache_h)
            timings.append(f"#{i+1} {cache_h} {ms}ms status={r.status_code}")

        html = r.get_data(as_text=True)
        cc_ctl = r.headers.get("Cache-Control", "")
        note("human provider HTML", r.status_code == 200 and len(html) > 2000, f"status={r.status_code}")
        note(
            "headers",
            "max-age=300" in cc_ctl,
            f"Cache-Control={cc_ctl}",
        )
        note(
            "3x cache",
            caches[0] == "MISS" and caches[1] == "HIT" and caches[2] == "HIT",
            "; ".join(timings),
        )

        clear_provider_page_cache()
        r_gpt_miss = client.get(f"/provider/{uncached_ccn}", headers={"User-Agent": GPTBOT})
        note("GPTBot uncached provider", r_gpt_miss.status_code == 429, f"status={r_gpt_miss.status_code}")

        client.get(f"/provider/{ccn}", headers={"User-Agent": HUMAN})
        r_gpt_hit = client.get(f"/provider/{ccn}", headers={"User-Agent": GPTBOT})
        note(
            "GPTBot cached provider",
            r_gpt_hit.status_code == 200 and r_gpt_hit.headers.get("X-PBJ-Provider-Cache") == "HIT",
            f"status={r_gpt_hit.status_code}",
        )

        r_ent = client.get(f"/entity/{entity_id}", headers={"User-Agent": GPTBOT})
        note("GPTBot entity", r_ent.status_code == 429, f"status={r_ent.status_code}")

        clear_provider_page_cache()
        r_goog = client.get(f"/provider/{uncached_ccn}", headers={"User-Agent": GOOGLEBOT})
        note(
            "Googlebot uncached provider",
            r_goog.status_code in (200, 404) and r_goog.status_code != 429,
            f"status={r_goog.status_code}",
        )

        for path in ("/", "/search_index.json", "/state/wyoming", "/data-sources"):
            rb = client.get(path, headers={"User-Agent": GPTBOT})
            note(f"GPTBot not blocked {path}", rb.status_code in (200, 302), f"status={rb.status_code}")

    return results


def _summarize_render_logs(lines: list[str]) -> dict:
    records = []
    for line in lines:
        if "[PBJ_PROVIDER]" not in line:
            continue
        try:
            payload = line.split("[PBJ_PROVIDER]", 1)[1].strip()
            records.append(json.loads(payload))
        except json.JSONDecodeError:
            continue
    if not records:
        return {"count": 0}

    cold = [r["cold_render_ms"] for r in records if r.get("outcome") == "cold_render"]
    queue = [r["queue_wait_ms"] for r in records if r.get("queue_wait_ms")]
    return {
        "count": len(records),
        "hit": sum(1 for r in records if r.get("cache") == "HIT"),
        "miss": sum(1 for r in records if r.get("cache") == "MISS"),
        "503": sum(1 for r in records if r.get("status") == 503),
        "ai_429": sum(1 for r in records if r.get("status") == 429 and r.get("ua") == "ai_crawler"),
        "googlebot_cold": sum(
            1 for r in records
            if r.get("ua") == "googlebot" and r.get("outcome") == "cold_render"
        ),
        "median_cold_render_ms": round(statistics.median(cold), 1) if cold else None,
        "max_cold_render_ms": round(max(cold), 1) if cold else None,
        "median_queue_wait_ms": round(statistics.median(queue), 1) if queue else None,
        "max_queue_wait_ms": round(max(queue), 1) if queue else None,
    }


def _fetch_render_logs_via_api(service_id: str, *, minutes: int = 30) -> list[str]:
    key = (os.environ.get("RENDER_API_KEY") or "").strip()
    if not key:
        return []
    url = f"https://api.render.com/v1/services/{service_id}/logs?limit=500"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"(Render API logs unavailable: {e})")
        return []
    lines: list[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                lines.append(item.get("message") or item.get("text") or "")
            else:
                lines.append(str(item))
    elif isinstance(data, dict):
        for item in data.get("logs") or data.get("entries") or []:
            if isinstance(item, dict):
                lines.append(item.get("message") or item.get("text") or "")
    return [ln for ln in lines if ln]


def main() -> int:
    p = argparse.ArgumentParser(description="Provider perf sanity / production checks")
    p.add_argument("--base-url", default="", help="Production origin (e.g. https://www.pbj320.com)")
    p.add_argument("--ccn", default="335513")
    p.add_argument("--entity-id", type=int, default=9)
    p.add_argument("--cold-sample", type=int, default=0, help="N random CCNs cold-render sample (production)")
    p.add_argument("--cold-seed", type=int, default=42)
    p.add_argument("--cold-delay", type=float, default=1.5, help="Seconds between cold-sample requests")
    p.add_argument("--render-service-id", default=os.environ.get("RENDER_SERVICE_ID", ""))
    p.add_argument("--local-only", action="store_true", help="Skip production; run local+render_sim only")
    args = p.parse_args()

    failed = 0
    all_results: list[tuple[str, bool, str]] = []

    if args.base_url and not args.local_only:
        print(f"=== PRODUCTION SANITY ({args.base_url}) ===")
        all_results.extend(_run_production_checks(args.base_url, args.ccn, args.entity_id))
        if args.cold_sample > 0:
            print(f"\n=== PRODUCTION COLD SAMPLE (n={args.cold_sample}, seed={args.cold_seed}) ===")
            rows = _run_cold_sample(
                args.base_url, n=args.cold_sample, seed=args.cold_seed, delay_s=args.cold_delay
            )
            for row in rows:
                print(
                    f"  {row['ccn']}  status={row['status']}  {row['elapsed_ms']}ms  "
                    f"cache={row['cache']}  503={row['503']}"
                )
            n503 = sum(1 for r in rows if r["503"])
            misses = sum(1 for r in rows if r["cache"] == "MISS")
            elapsed = [r["elapsed_ms"] for r in rows if r["status"] == 200]
            print(
                f"  summary: 200={len(elapsed)} MISS={misses} 503={n503} "
                f"median_ms={round(statistics.median(elapsed), 1) if elapsed else 'n/a'} "
                f"max_ms={max(elapsed) if elapsed else 'n/a'}"
            )

        if args.render_service_id:
            print("\n=== RENDER LOG SUMMARY (API) ===")
            log_lines = _fetch_render_logs_via_api(args.render_service_id)
            summary = _summarize_render_logs(log_lines)
            print(json.dumps(summary, indent=2))
        else:
            print(
                "\n(Render log API: set RENDER_API_KEY + --render-service-id to auto-summarize; "
                "otherwise grep dashboard logs for [PBJ_PROVIDER])"
            )
    elif not args.local_only:
        print("No --base-url; skipping production checks.")

    if not args.base_url or args.local_only:
        print("=== LOCAL SANITY ===")
        all_results.extend(_run_checks_local(render_sim=False))
        all_results.extend(_run_checks_local(render_sim=True))

    print("\n=== SANITY CHECK RESULTS ===")
    for name, ok, detail in all_results:
        mark = "PASS" if ok else "FAIL"
        print(f"{mark}  {name}\n      {detail}")
        if not ok:
            failed += 1

    print(f"\n=== SUMMARY: {len(all_results) - failed}/{len(all_results)} passed ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
