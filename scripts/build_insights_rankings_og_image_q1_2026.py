"""Rasterize rankings tilemap SVG to LinkedIn-friendly OG PNG (1200×630).

LinkedIn and most crawlers ignore SVG for og:image; keep SVG for in-page charts.
Uses cairosvg when libcairo is available; otherwise Playwright (Chromium/Edge).
Always inlines SVG markup (file:// img src fails under Playwright set_content).
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pbj_og_raster import assert_og_raster_ok  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "insights-rankings-state-hprd-tilemap-q1-2026.svg"
OUT = ROOT / "insights-rankings-state-hprd-tilemap-q1-2026-og.png"
OG_W, OG_H = 1200, 630
MAP_W, MAP_H = 860, 560
TITLE = "Nursing Home PBJ State Staffing Trends, Q1 2026"
BRAND = "PBJ320"
BG = (15, 23, 42)
HEAD_H = 78

def _strip_xml_decl(svg: str) -> str:
    return re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", svg, count=1, flags=re.I)


def _rasterize_svg_playwright(svg_markup: str, width: int, height: int) -> bytes:
    from playwright.sync_api import sync_playwright

    body = _strip_xml_decl(svg_markup)
    # Force explicit pixel size so screenshot matches viewport.
    if 'width="' not in body[:200]:
        body = body.replace(
            "<svg ",
            f'<svg width="{width}" height="{height}" ',
            1,
        )
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<style>html,body{margin:0;padding:0;background:#0f172a;overflow:hidden}"
        f"svg{{display:block;width:{width}px;height:{height}px}}</style></head>"
        f"<body>{body}</body></html>"
    )
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge")
        except Exception:
            browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": width, "height": height},
            device_scale_factor=1,
        )
        page.set_content(html, wait_until="load")
        page.wait_for_timeout(150)
        png = page.screenshot(type="png", clip={"x": 0, "y": 0, "width": width, "height": height})
        browser.close()
    return png


def _rasterize_svg_cairosvg(svg_path: Path, width: int, height: int) -> bytes:
    import cairosvg

    return cairosvg.svg2png(
        url=str(svg_path),
        output_width=width,
        output_height=height,
    )


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend(
            [
                r"C:\Windows\Fonts\segoeuib.ttf",
                r"C:\Windows\Fonts\arialbd.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            ]
        )
    candidates.extend(
        [
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_header(canvas: Image.Image) -> None:
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, OG_W, HEAD_H), fill=(10, 16, 28))
    draw.line((0, HEAD_H - 1, OG_W, HEAD_H - 1), fill=(51, 65, 85), width=1)
    title_font = _font(28, bold=True)
    brand_font = _font(22, bold=True)
    # Title left, brand right — one band, no extra rows.
    draw.text((36, 24), TITLE, fill=(248, 250, 252), font=title_font)
    brand_bbox = draw.textbbox((0, 0), BRAND, font=brand_font)
    brand_w = brand_bbox[2] - brand_bbox[0]
    draw.text((OG_W - 36 - brand_w, 28), BRAND, fill=(148, 163, 184), font=brand_font)


def _assert_map_layer(im: Image.Image, raw_bytes: int) -> None:
    colors = im.getcolors(maxcolors=200_000)
    n_colors = len(colors) if colors else 200_000
    if raw_bytes < 20_000 or n_colors < 80:
        raise SystemExit(
            f"OG map layer empty (bytes={raw_bytes}, unique_colors≈{n_colors}). "
            "Inline SVG for Playwright; do not use file:// img src."
        )


def main() -> None:
    if not SVG.is_file():
        raise SystemExit(f"Missing {SVG}")

    svg_text = SVG.read_text(encoding="utf-8")
    # Fit map under header band.
    map_area_h = OG_H - HEAD_H
    scale = min(OG_W / MAP_W, map_area_h / MAP_H)
    render_w = int(round(MAP_W * scale))
    render_h = int(round(MAP_H * scale))

    png_bytes: bytes | None = None
    try:
        png_bytes = _rasterize_svg_cairosvg(SVG, render_w, render_h)
    except Exception:
        png_bytes = None
    if png_bytes is None:
        png_bytes = _rasterize_svg_playwright(svg_text, render_w, render_h)

    rendered = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    if rendered.size != (render_w, render_h):
        rendered = rendered.resize((render_w, render_h), Image.Resampling.LANCZOS)

    _assert_map_layer(rendered, len(png_bytes))

    canvas = Image.new("RGB", (OG_W, OG_H), BG)
    _draw_header(canvas)
    x_off = max(0, (OG_W - render_w) // 2)
    y_off = HEAD_H + max(0, (map_area_h - render_h) // 2)
    canvas.paste(rendered, (x_off, y_off))
    canvas.save(OUT, format="PNG", optimize=True)
    assert_og_raster_ok(OUT)
    print(f"Wrote {OUT} ({OG_W}x{OG_H}, {OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
