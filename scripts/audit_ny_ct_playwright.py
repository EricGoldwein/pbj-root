#!/usr/bin/env python3
"""Playwright audit: NY/CT owners, compliance warnings, APIs, speed (production by default).

QA doc: docs/ny_ct_production_playwright_qa.md
Report: scripts/_ny_ct_playwright_report.json

CT Q4 sample: use 075011 (not 075001 — prior-quarter warning possible without CY2025Q4 bundle row).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from typing import Any

from playwright.sync_api import APIRequestContext, Page, sync_playwright

INIT = """
window.__pbjLongTasks = [];
try {
  const obs = new PerformanceObserver((list) => {
    for (const e of list.getEntries()) {
      window.__pbjLongTasks.push({ startTime: e.startTime, duration: e.duration });
    }
  });
  obs.observe({ entryTypes: ['longtask'] });
} catch (_) {}
"""

ERROR_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"\bInternal Server Error\b",
        r"\b502 Bad Gateway\b",
        r"\b503 Service Unavailable\b",
        r"<title>\s*404\b",
        r"\bPage not found\b",
    )
]

DEFAULT_CHECKS: list[dict[str, Any]] = [
    {
        "label": "owners_hub",
        "url": "/owners/",
        "kind": "html",
        "must_contain": ["owners-hub-state-card", "New York", "Connecticut"],
    },
    {
        "label": "owners_ny_index",
        "url": "/owners/ny",
        "kind": "html",
        "must_contain": [
            "owners-state-index",
            "owners-state-index-stats",
            "New York Nursing Home Ownership",
        ],
        "min_owner_rows": 5,
    },
    {
        "label": "owners_ct_index",
        "url": "/owners/ct",
        "kind": "html",
        "must_contain": [
            "owners-state-index",
            "Connecticut Nursing Home Ownership",
        ],
        "min_owner_rows": 5,
    },
    {
        "label": "owner_profile_ny",
        "url": "/owners/6608785985",
        "kind": "html",
        "must_contain": ["6608785985", "facility"],
        "must_not_contain": ["Owner profile not found"],
    },
    {
        "label": "owner_profile_ct",
        "url": "/owners/0244206886",
        "kind": "html",
        "must_contain": ["0244206886", "facility"],
        "must_not_contain": ["Owner profile not found"],
    },
    {
        "label": "provider_ny_seagate",
        "url": "/provider/335513",
        "kind": "html",
        "must_contain": ["335513", "HPRD"],
        "must_not_contain_visible": ["Reported HPRD not available"],
        "expect_compliance_api": True,
    },
    {
        "label": "provider_ny_below_threshold",
        "url": "/provider/335003",
        "kind": "html",
        "must_contain": ["335003"],
        "expect_below_threshold_warning": True,
        "expect_compliance_api": True,
    },
    {
        "label": "provider_ct_below_threshold",
        "url": "/provider/075011",
        "kind": "html",
        "must_contain": ["075011"],
        "expect_below_threshold_warning": True,
        "expect_compliance_api": True,
        "compliance_quarter": "CY2025Q4",
    },
    {
        "label": "provider_ct_clean",
        "url": "/provider/075441",
        "kind": "html",
        "must_contain": ["075441", "HPRD"],
        "expect_compliance_api": True,
    },
]

API_CHECKS: list[dict[str, Any]] = [
    {
        "label": "api_compliance_335003",
        "path": "/api/provider/335003/staffing-compliance-summary.json?quarter=CY2025Q4",
        "expect_available": True,
        "expect_state": "NY",
        "min_below_days": 1,
    },
    {
        "label": "api_compliance_075011",
        "path": "/api/provider/075011/staffing-compliance-summary.json?quarter=CY2025Q4",
        "expect_available": True,
        "expect_state": "CT",
        "min_below_days": 1,
    },
    {
        "label": "api_compliance_335513",
        "path": "/api/provider/335513/staffing-compliance-summary.json?quarter=CY2025Q4",
        "expect_available": True,
        "expect_state": "NY",
        "min_below_days": 1,
    },
    {
        "label": "api_owners_stats",
        "path": "/owners/api/stats",
        "required_keys": [],
        "min_json_keys": 1,
    },
]


def _nav_timing(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const n = performance.getEntriesByType('navigation')[0];
          if (!n) return {};
          return {
            ttfb_ms: Math.round(n.responseStart),
            domContentLoaded_ms: Math.round(n.domContentLoadedEventEnd),
            load_ms: Math.round(n.loadEventEnd),
          };
        }"""
    )


def _count_owner_rows(page: Page) -> int:
    return page.evaluate(
        """() => {
          const sel = [
            '.owners-state-owner-row',
            'table.owners-state-table tbody tr',
            '[data-owner-pac]',
            '.owners-state-results tbody tr',
          ];
          for (const s of sel) {
            const n = document.querySelectorAll(s).length;
            if (n > 0) return n;
          }
          const links = [...document.querySelectorAll('a[href*="/owners/"]')]
            .filter(a => /^\\/owners\\/\\d{10}$/.test(a.getAttribute('href') || ''));
          return links.length;
        }"""
    )


def _body_issues(text: str) -> list[str]:
    issues: list[str] = []
    for pat in ERROR_PATTERNS:
        if pat.search(text):
            issues.append(f"matched error pattern: {pat.pattern}")
    return issues


def audit_html_page(page: Page, base: str, spec: dict[str, Any]) -> dict[str, Any]:
    url = base.rstrip("/") + spec["url"]
    facility_reqs: list[str] = []
    page.on(
        "request",
        lambda r: facility_reqs.append(r.url)
        if "facility_quarterly" in r.url
        else None,
    )

    out: dict[str, Any] = {
        "label": spec["label"],
        "url": url,
        "kind": "html",
        "issues": [],
        "warnings": [],
    }

    t0 = time.perf_counter()
    try:
        resp = page.goto(url, wait_until="networkidle", timeout=180_000)
    except Exception as exc:
        out["issues"].append(f"navigation failed: {exc}")
        out["networkidle_s"] = round(time.perf_counter() - t0, 2)
        return out

    out["networkidle_s"] = round(time.perf_counter() - t0, 2)
    out["status"] = resp.status if resp else None
    out["navigation"] = _nav_timing(page)
    out["provider_cache"] = resp.headers.get("x-pbj-provider-cache") if resp else None
    out["facility_quarterly_requests"] = facility_reqs

    if out["status"] != 200:
        out["issues"].append(f"HTTP {out['status']}")

    body_text = page.inner_text("body", timeout=30_000)
    html = page.content()
    out["issues"].extend(_body_issues(html))

    for needle in spec.get("must_contain") or []:
        if needle not in html and needle not in body_text:
            out["issues"].append(f"missing expected text/markup: {needle!r}")

    for needle in spec.get("must_not_contain") or []:
        if needle in body_text or needle in html:
            out["issues"].append(f"found forbidden text: {needle!r}")

    for needle in spec.get("must_not_contain_visible") or []:
        if needle in body_text:
            out["issues"].append(f"found forbidden visible text: {needle!r}")

    min_rows = spec.get("min_owner_rows")
    if min_rows is not None:
        n = _count_owner_rows(page)
        out["owner_row_count"] = n
        if n < int(min_rows):
            out["issues"].append(f"owner rows {n} < minimum {min_rows}")

    if spec.get("expect_below_threshold_warning"):
        warn_ok = (
            "below" in body_text.lower()
            and ("threshold" in body_text.lower() or "staffing" in body_text.lower())
        ) or "reported pbj days" in body_text.lower()
        out["has_compliance_warning"] = warn_ok
        if not warn_ok:
            out["issues"].append("expected staffing compliance warning on provider page")

    ccn_match = re.search(r"/provider/(\d+)", spec["url"])
    if spec.get("expect_compliance_api") and ccn_match:
        ccn = ccn_match.group(1).zfill(6)
        q = spec.get("compliance_quarter") or "CY2025Q4"
        api_url = f"{base.rstrip('/')}/api/provider/{ccn}/staffing-compliance-summary.json?quarter={q}"
        api_resp = page.context.request.get(api_url, timeout=60_000)
        out["inline_api_status"] = api_resp.status
        if api_resp.status != 200:
            out["issues"].append(f"compliance API HTTP {api_resp.status}")
        else:
            try:
                payload = api_resp.json()
                summary = payload.get("summary") if isinstance(payload, dict) else None
                if not payload.get("available"):
                    out["issues"].append("compliance API available=false")
                elif isinstance(summary, dict):
                    out["inline_api_summary"] = {
                        k: summary.get(k)
                        for k in (
                            "state",
                            "total_days_reported",
                            "below_state_min_days_count",
                            "state_min_threshold_used",
                        )
                    }
                    if not summary.get("total_days_reported"):
                        out["warnings"].append("compliance API total_days_reported is 0/empty")
                else:
                    out["issues"].append("compliance API missing summary object")
            except Exception as exc:
                out["issues"].append(f"compliance API not JSON: {exc}")

    if spec["label"].startswith("provider"):
        out["has_hprd_narrative"] = bool(
            re.search(r"HPRD", body_text, re.I)
            and "Reported HPRD not available" not in body_text
        )
        if not out["has_hprd_narrative"]:
            out["issues"].append("missing HPRD narrative on provider page")

    if out["networkidle_s"] > 25:
        out["warnings"].append(f"slow networkidle ({out['networkidle_s']}s)")

    return out


def audit_api(request: APIRequestContext, base: str, spec: dict[str, Any]) -> dict[str, Any]:
    url = base.rstrip("/") + spec["path"]
    out: dict[str, Any] = {"label": spec["label"], "url": url, "kind": "api", "issues": [], "warnings": []}
    t0 = time.perf_counter()
    resp = request.get(url, timeout=60_000)
    out["elapsed_s"] = round(time.perf_counter() - t0, 3)
    out["status"] = resp.status
    if resp.status != 200:
        out["issues"].append(f"HTTP {resp.status}")
        return out
    try:
        payload = resp.json()
    except Exception as exc:
        out["issues"].append(f"not JSON: {exc}")
        return out
    if isinstance(payload, dict):
        out["payload_keys"] = sorted(payload.keys())[:20]
        for key in spec.get("required_keys") or []:
            if key not in payload:
                out["issues"].append(f"missing key {key!r}")
        min_keys = spec.get("min_json_keys")
        if min_keys and len(payload) < int(min_keys):
            out["issues"].append(f"JSON object has {len(payload)} keys (< {min_keys})")
        if spec.get("expect_available") is True and not payload.get("available"):
            out["issues"].append("available=false")
        if spec.get("expect_available") is False and payload.get("available"):
            out["issues"].append("expected available=false")
        summary = payload.get("summary") if payload.get("available") else {}
        if not isinstance(summary, dict):
            summary = {}
        exp_st = spec.get("expect_state")
        if exp_st and str(summary.get("state", "")).upper() != exp_st:
            out["issues"].append(f"state {summary.get('state')!r} != {exp_st!r}")
        min_below = spec.get("min_below_days")
        if min_below is not None:
            try:
                below = int(summary.get("below_state_min_days_count") or 0)
            except (TypeError, ValueError):
                below = 0
            out["below_state_min_days_count"] = below
            if below < int(min_below):
                out["issues"].append(f"below_state_min_days_count {below} < {min_below}")
        th = summary.get("state_min_threshold_used")
        if th is not None:
            out["state_min_threshold_used"] = th
    else:
        out["warnings"].append(f"unexpected JSON type: {type(payload).__name__}")
    return out


def run_audit(base: str) -> dict[str, Any]:
    html_results: list[dict[str, Any]] = []
    api_results: list[dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        request = context.request

        for spec in API_CHECKS:
            api_results.append(audit_api(request, base, spec))

        for spec in DEFAULT_CHECKS:
            page = context.new_page()
            page.add_init_script(INIT)
            try:
                html_results.append(audit_html_page(page, base, spec))
            except Exception as exc:
                html_results.append(
                    {
                        "label": spec["label"],
                        "url": base.rstrip("/") + spec["url"],
                        "kind": "html",
                        "issues": [f"unexpected error: {exc}"],
                    }
                )
            finally:
                page.close()

        browser.close()

    all_results = html_results + api_results
    failed = [r for r in all_results if r.get("issues")]
    warned = [r for r in all_results if r.get("warnings") and not r.get("issues")]

    return {
        "base": base,
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "summary": {
            "checks": len(all_results),
            "failed": len(failed),
            "warned": len(warned),
            "pass": len(all_results) - len(failed),
        },
        "html_pages": html_results,
        "api_endpoints": api_results,
        "failures": [{k: v for k, v in r.items() if k != "navigation"} for r in failed],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default="https://www.pbj320.com",
        help="Site origin (default: production)",
    )
    parser.add_argument("--out", help="Write JSON report to this path")
    args = parser.parse_args()

    report = run_audit(args.base.rstrip("/"))
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
            print(f"\nWrote {args.out}", file=sys.stderr)

    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
