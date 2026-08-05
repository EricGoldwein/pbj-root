"""Rasterize rankings tilemap SVG to LinkedIn-friendly OG PNG (1200×630).

LinkedIn and most crawlers ignore SVG for og:image; keep SVG for in-page charts.
Uses cairosvg when libcairo is available; otherwise Playwright (see requirements.txt).
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "insights-rankings-state-hprd-tilemap-q1-2026.svg"
OUT = ROOT / "insights-rankings-state-hprd-tilemap-q1-2026-og.png"
OG_W, OG_H = 1200, 630
# Tilemap viewBox is 860×560
MAP_W, MAP_H = 860, 560


def _rasterize_svg_playwright(svg_path: Path, width: int, height: int) -> bytes:
    from playwright.sync_api import sync_playwright

    html = (
        "<!DOCTYPE html><html><body style=\"margin:0;background:#0f172a\">"
        f"<img src=\"{svg_path.as_uri()}\" width=\"{width}\" height=\"{height}\" />"
        "</body></html>"
    )
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge")
        except Exception:
            browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})
        page.set_content(html)
        png = page.screenshot(type="png")
        browser.close()
    return png


def _rasterize_svg_cairosvg(svg_path: Path, width: int, height: int) -> bytes:
    import cairosvg

    return cairosvg.svg2png(
        url=str(svg_path),
        output_width=width,
        output_height=height,
    )


def main() -> None:
    if not SVG.is_file():
        raise SystemExit(f"Missing {SVG}")
    scale = OG_W / MAP_W
    render_h = int(round(MAP_H * scale))
    try:
        png_bytes = _rasterize_svg_cairosvg(SVG, OG_W, render_h)
    except Exception:
        png_bytes = _rasterize_svg_playwright(SVG, OG_W, render_h)
    rendered = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    canvas = Image.new("RGB", (OG_W, OG_H), (15, 23, 42))
    y_off = max(0, (OG_H - render_h) // 2)
    canvas.paste(rendered, (0, y_off))
    canvas.save(OUT, format="PNG", optimize=True)
    print(f"Wrote {OUT} ({OG_W}x{OG_H})")


if __name__ == "__main__":
    main()
