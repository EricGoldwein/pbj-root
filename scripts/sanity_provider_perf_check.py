#!/usr/bin/env python3
"""Targeted sanity checks for provider perf / bot policy (run before commit)."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _run_checks(*, render_sim: bool) -> list[tuple[str, bool, str]]:
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

    # Fresh import with chosen env (app reads setdefaults at import).
    for mod in list(sys.modules):
        if mod in ("app", "pbj_provider_perf") or mod.startswith("app."):
            del sys.modules[mod]

    from app import (  # noqa: WPS433
        app,
        clear_provider_page_cache,
    )
    from pbj_provider_perf import (
        ai_heavy_routes_cache_only_enabled,
        provider_browser_cache_control,
        provider_perf_log_enabled,
    )

    results: list[tuple[str, bool, str]] = []
    ccn = "335513"
    entity_id = 9
    human = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    gptbot = "Mozilla/5.0 (compatible; GPTBot/1.0; +https://openai.com/gptbot)"
    googlebot = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"

    def note(name: str, ok: bool, detail: str) -> None:
        results.append((f"[{label}] {name}", ok, detail))

    with app.test_client() as client:
        # --- env expectations ---
        if render_sim:
            note(
                "env Render defaults",
                ai_heavy_routes_cache_only_enabled() and provider_perf_log_enabled(),
                f"ai_cache_only={ai_heavy_routes_cache_only_enabled()} perf_log={provider_perf_log_enabled()} cache_ctl={provider_browser_cache_control()}",
            )
        else:
            note(
                "env local: no Render bot lock",
                not ai_heavy_routes_cache_only_enabled(),
                f"ai_cache_only={ai_heavy_routes_cache_only_enabled()} cache_ctl={provider_browser_cache_control()}",
            )
            note(
                "env local: provider cache skipped by default",
                (os.environ.get("PBJ_SKIP_PROVIDER_PAGE_CACHE") or "").strip() in ("1", "true", "yes", "on"),
                f"PBJ_SKIP_PROVIDER_PAGE_CACHE={os.environ.get('PBJ_SKIP_PROVIDER_PAGE_CACHE')}",
            )

        if not render_sim:
            # Local: human provider HTML + no broad bot block
            r = client.get(f"/provider/{ccn}", headers={"User-Agent": human})
            html = r.get_data(as_text=True)
            note(
                "human provider HTML",
                r.status_code == 200 and "pbj" in html.lower() and len(html) > 2000,
                f"status={r.status_code} len={len(html)}",
            )
            for path in ("/", "/search_index.json", "/state/wyoming", "/data-sources"):
                rb = client.get(path, headers={"User-Agent": gptbot})
                note(
                    f"GPTBot not blocked {path}",
                    rb.status_code in (200, 301, 302),
                    f"status={rb.status_code}",
                )
            return results

        # --- Render-sim: headers, cache, bots ---
        clear_provider_page_cache()
        uncached_ccn = "075325"
        timings: list[str] = []
        caches: list[str] = []

        for i in range(3):
            t0 = time.perf_counter()
            r = client.get(f"/provider/{ccn}", headers={"User-Agent": human})
            ms = round((time.perf_counter() - t0) * 1000, 1)
            cache_h = r.headers.get("X-PBJ-Provider-Cache", "?")
            caches.append(cache_h)
            timings.append(f"#{i+1} {cache_h} {ms}ms status={r.status_code}")

        html = r.get_data(as_text=True)
        cc_ctl = r.headers.get("Cache-Control", "")
        note(
            "human provider HTML",
            r.status_code == 200 and "provider" in html.lower() and len(html) > 2000,
            f"status={r.status_code} len={len(html)}",
        )
        note(
            "headers X-PBJ-Provider-Cache + Cache-Control",
            "X-PBJ-Provider-Cache" in r.headers and "max-age=300" in cc_ctl and "private" in cc_ctl,
            f"cache_hdr={r.headers.get('X-PBJ-Provider-Cache')} Cache-Control={cc_ctl}",
        )
        note(
            "3x same provider cache progression",
            caches[0] == "MISS" and caches[1] == "HIT" and caches[2] == "HIT",
            "; ".join(timings),
        )

        # GPTBot uncached
        clear_provider_page_cache()
        r_gpt_miss = client.get(
            f"/provider/{uncached_ccn}",
            headers={"User-Agent": gptbot},
        )
        note(
            "GPTBot uncached provider",
            r_gpt_miss.status_code == 429,
            f"status={r_gpt_miss.status_code} X-PBJ-Provider-Cache={r_gpt_miss.headers.get('X-PBJ-Provider-Cache')}",
        )

        # Warm cache with human, GPTBot cached
        client.get(f"/provider/{ccn}", headers={"User-Agent": human})
        r_gpt_hit = client.get(f"/provider/{ccn}", headers={"User-Agent": gptbot})
        note(
            "GPTBot cached provider",
            r_gpt_hit.status_code == 200 and r_gpt_hit.headers.get("X-PBJ-Provider-Cache") == "HIT",
            f"status={r_gpt_hit.status_code} cache={r_gpt_hit.headers.get('X-PBJ-Provider-Cache')}",
        )

        r_ent = client.get(f"/entity/{entity_id}", headers={"User-Agent": gptbot})
        note(
            "GPTBot entity",
            r_ent.status_code == 429,
            f"status={r_ent.status_code}",
        )

        clear_provider_page_cache()
        r_goog = client.get(
            f"/provider/{uncached_ccn}",
            headers={"User-Agent": googlebot},
        )
        note(
            "Googlebot uncached provider not blocked",
            r_goog.status_code in (200, 404) and r_goog.status_code != 429,
            f"status={r_goog.status_code} cache={r_goog.headers.get('X-PBJ-Provider-Cache')}",
        )

        for path in ("/", "/search_index.json", "/state/wyoming", "/data-sources"):
            rb = client.get(path, headers={"User-Agent": gptbot})
            note(
                f"GPTBot not blocked {path}",
                rb.status_code in (200, 301, 302),
                f"status={rb.status_code}",
            )

    return results


def main() -> int:
    import io
    from contextlib import redirect_stdout

    all_results: list[tuple[str, bool, str]] = []
    log_capture = io.StringIO()

    # LOCAL first (default env)
    all_results.extend(_run_checks(render_sim=False))

    # RENDER sim second
    all_results.extend(_run_checks(render_sim=True))

    print("=== SANITY CHECK RESULTS ===")
    failed = 0
    for name, ok, detail in all_results:
        mark = "PASS" if ok else "FAIL"
        print(f"{mark}  {name}\n      {detail}")
        if not ok:
            failed += 1

    print("\n=== SAMPLE [PBJ_PROVIDER] log (Render sim, one cold request) ===")
    os.environ["RENDER"] = "1"
    os.environ["PBJ_SKIP_PROVIDER_PAGE_CACHE"] = "0"
    os.environ["PBJ_PROVIDER_PERF_LOG"] = "1"
    for mod in list(sys.modules):
        if mod in ("app", "pbj_provider_perf") or mod.startswith("app."):
            del sys.modules[mod]

    buf = io.StringIO()

    def fake_print(*args, **kwargs):
        msg = " ".join(str(a) for a in args)
        buf.write(msg + "\n")
        if kwargs.get("file") is sys.stdout:
            pass

    import builtins

    real_print = builtins.print
    builtins.print = lambda *a, **k: buf.write(" ".join(str(x) for x in a) + ("\n" if k.get("end", "\n") == "\n" else k.get("end", "")))

    try:
        from app import app, clear_provider_page_cache

        clear_provider_page_cache()
        with app.test_client() as client:
            client.get("/provider/075263", headers={"User-Agent": "Mozilla/5.0"})
        for line in buf.getvalue().splitlines():
            if line.startswith("[PBJ_PROVIDER]"):
                print(line)
                break
        else:
            print("(no [PBJ_PROVIDER] line captured — check PBJ_PROVIDER_PERF_LOG)")
    finally:
        builtins.print = real_print

    print(f"\n=== SUMMARY: {len(all_results) - failed}/{len(all_results)} passed ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
