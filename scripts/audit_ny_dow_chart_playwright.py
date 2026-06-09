#!/usr/bin/env python3
"""Playwright gate: DOW chart renders exactly seven Mon–Sun bars with sane % y-axis."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "insights-ny-minimum-staffing.html"
EXPECTED_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _launch_chromium(playwright):
    try:
        return playwright.chromium.launch(headless=True)
    except Exception as exc:
        print(f"SKIP Playwright Chromium not installed: {exc}", file=sys.stderr)
        return None


def main() -> int:
    if not HTML.is_file():
        print(f"missing report HTML: {HTML}", file=sys.stderr)
        return 1

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SKIP playwright not installed", file=sys.stderr)
        return 0

    file_url = HTML.resolve().as_uri() + "#calendar"

    with sync_playwright() as p:
        browser = _launch_chromium(p)
        if browser is None:
            return 0
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(file_url, wait_until="networkidle", timeout=120_000)
        page.wait_for_selector("#dowChart", timeout=30_000)
        page.wait_for_timeout(1500)

        state = page.evaluate(
            """() => {
              const chart = window.PBJ320Threshold && window.PBJ320Threshold.chartStore
                ? window.PBJ320Threshold.chartStore.dowChart
                : null;
              if (!chart || !chart.data) return { error: 'dowChart missing' };
              const labels = (chart.data.labels || []).slice();
              const data = (chart.data.datasets && chart.data.datasets[0]
                ? chart.data.datasets[0].data
                : []).slice();
              const yScale = chart.scales && chart.scales.y ? chart.scales.y : null;
              const ticks = yScale && yScale.ticks ? yScale.ticks.map(t => t.label) : [];
              return {
                labels,
                data,
                yMin: yScale ? yScale.min : null,
                yMax: yScale ? yScale.max : null,
                ticks,
              };
            }"""
        )
        browser.close()

    if state.get("error"):
        print(f"FAIL {state['error']}", file=sys.stderr)
        return 1

    labels = state["labels"]
    data = state["data"]
    if labels != EXPECTED_LABELS:
        print(f"FAIL labels {labels!r} != {EXPECTED_LABELS!r}", file=sys.stderr)
        return 1
    if len(data) != 7:
        print(f"FAIL bar count {len(data)} != 7", file=sys.stderr)
        return 1
    if any(not isinstance(v, (int, float)) or v < 0 or v > 100 for v in data):
        print(f"FAIL bar values out of range: {data!r}", file=sys.stderr)
        return 1

    y_min = state.get("yMin")
    y_max = state.get("yMax")
    if y_min is None or y_max is None or y_min >= y_max:
        print(f"FAIL y-axis bounds yMin={y_min} yMax={y_max}", file=sys.stderr)
        return 1

    ticks = state.get("ticks") or []
    pct_ticks = [t for t in ticks if isinstance(t, str) and t.endswith("%")]
    if pct_ticks:
        for tick in pct_ticks:
            num = tick[:-1]
            if not num.lstrip("-").isdigit():
                print(f"FAIL non-integer y-axis tick {tick!r}", file=sys.stderr)
                return 1
        if max(int(t[:-1]) for t in pct_ticks) > 100 or min(int(t[:-1]) for t in pct_ticks) < 0:
            print(f"FAIL y-axis tick range {pct_ticks!r}", file=sys.stderr)
            return 1

    # Move HPRD threshold via public API (slider lives in a hidden scenario panel).
    with sync_playwright() as p:
        browser = _launch_chromium(p)
        if browser is None:
            return 0
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(file_url, wait_until="networkidle", timeout=120_000)
        page.wait_for_selector("#dowChart", timeout=30_000)
        page.evaluate(
            """() => {
              if (!window.PBJ320Threshold || !window.PBJ320Threshold.applyThreshold) {
                throw new Error('PBJ320Threshold.applyThreshold missing');
              }
              window.PBJ320Threshold.applyThreshold(4.0, { scope: 'global' });
            }"""
        )
        page.wait_for_timeout(800)
        after = page.evaluate(
            """() => {
              const chart = window.PBJ320Threshold.chartStore.dowChart;
              return {
                labels: (chart.data.labels || []).slice(),
                data: (chart.data.datasets[0].data || []).slice(),
              };
            }"""
        )
        browser.close()

    if after["labels"] != EXPECTED_LABELS or len(after["data"]) != 7:
        print(
            f"FAIL after threshold update labels={after['labels']!r} data_len={len(after['data'])}",
            file=sys.stderr,
        )
        return 1

    # Metric-mode controls exist on the report; DOW chart must stay at seven bars.
    with sync_playwright() as p:
        browser = _launch_chromium(p)
        if browser is None:
            return 0
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(file_url, wait_until="networkidle", timeout=120_000)
        page.wait_for_selector("#dowChart", timeout=30_000)
        page.evaluate(
            """() => {
              window.PBJ_REPORT_METRIC_MODE = 'broad_pbj_total_hprd';
              if (!window.PBJ320Threshold || !window.PBJ320Threshold.applyThreshold) {
                throw new Error('PBJ320Threshold.applyThreshold missing');
              }
              window.PBJ320Threshold.applyThreshold(
                window.PBJ320Threshold.currentThreshold,
                { scope: 'global' }
              );
              if (window.PBJ320ScenarioControls && window.PBJ320ScenarioControls.updateChrome) {
                window.PBJ320ScenarioControls.updateChrome();
              }
            }"""
        )
        page.wait_for_timeout(800)
        after_mode = page.evaluate(
            """() => {
              const chart = window.PBJ320Threshold.chartStore.dowChart;
              return {
                labels: (chart.data.labels || []).slice(),
                data: (chart.data.datasets[0].data || []).slice(),
              };
            }"""
        )
        browser.close()

    if after_mode["labels"] != EXPECTED_LABELS or len(after_mode["data"]) != 7:
        print(
            f"FAIL after metric-mode update labels={after_mode['labels']!r} "
            f"data_len={len(after_mode['data'])}",
            file=sys.stderr,
        )
        return 1

    print(
        "PASS DOW chart:",
        f"bars={len(data)}",
        f"y={y_min}-{y_max}",
        f"values={data}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
