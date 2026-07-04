#!/usr/bin/env python3
"""Generate static/img/pbj320-premium-og.png (1200x630) for Premium OG/Twitter cards."""
from __future__ import annotations

import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "static" / "img" / "pbj320-premium-og.png"
DASHBOARD_HTML = Path(__file__).resolve().parent / "assets" / "og-premium-dashboard-mock.html"
DASHBOARD_PNG_CACHE = ROOT / "premium" / "demo" / "og-dashboard-render.png"
FAVICON = ROOT / "pbj_favicon.png"
COMPLIANCE_JSON = ROOT / "premium" / "demo" / "320365-compliance-data.json"

W, H = 1200, 630

# Premium audit palette (premium-site.css + premium-hub.css)
PAGE_BG = (235, 240, 248)       # #EBF0F8
BG_TOP = (224, 231, 255)        # #e0e7ff
BG_BOTTOM = (248, 250, 252)     # #f8fafc
CARD = (255, 255, 255)
INK = (15, 23, 42)              # #0f172a
MUTED = (71, 85, 105)           # #475569
MUTED_LIGHT = (100, 116, 139)   # #64748b
ACCENT = (79, 70, 229)          # #4f46e5 — “320”
ACCENT_NAVY = (30, 58, 95)      # #1e3a5f
ACCENT_DARK = (91, 33, 182)     # #5b21b6
PILL_BORDER = (129, 140, 248)   # #818cf8
TOP_ACCENT = (30, 58, 95)       # --pbj-premium-accent

FEATURES = [
    ("Daily staffing", "#4338ca"),
    ("Employee roster", "#4f46e5"),
    ("Ownership context", "#6366f1"),
    ("Report-ready exports", "#7c3aed"),
]


def _render_dashboard_html() -> Path | None:
    """Screenshot self-contained dashboard mock via Playwright (sharp, real layout)."""
    if not DASHBOARD_HTML.is_file():
        return None
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    DASHBOARD_PNG_CACHE.parent.mkdir(parents=True, exist_ok=True)
    url = DASHBOARD_HTML.resolve().as_uri()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": 1080, "height": 720},
                device_scale_factor=2,
            )
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.locator(".dash").screenshot(path=str(DASHBOARD_PNG_CACHE))
            browser.close()
        return DASHBOARD_PNG_CACHE if DASHBOARD_PNG_CACHE.is_file() else None
    except Exception as exc:
        print(f"Playwright render skipped: {exc}")
        return None


def _gradient_bg() -> Image.Image:
    img = Image.new("RGB", (W, H), PAGE_BG)
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / max(H - 1, 1)
        r = int(BG_TOP[0] * (1 - t) + BG_BOTTOM[0] * t)
        g = int(BG_TOP[1] * (1 - t) + BG_BOTTOM[1] * t)
        b = int(BG_TOP[2] * (1 - t) + BG_BOTTOM[2] * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    return img


def _load_fonts() -> dict:
    candidates = [
        ("C:/Windows/Fonts/segoeuib.ttf", "bold"),
        ("C:/Windows/Fonts/segoeui.ttf", "regular"),
        ("C:/Windows/Fonts/segoeuisb.ttf", "semibold"),
    ]
    loaded: dict[str, str] = {}
    for path, key in candidates:
        if key not in loaded and os.path.isfile(path):
            loaded[key] = path
    reg = loaded.get("regular", loaded.get("bold", ""))
    bold = loaded.get("bold", reg)
    semi = loaded.get("semibold", bold)
    fonts: dict = {}
    try:
        fonts["brand"] = ImageFont.truetype(bold, 44)
        fonts["brand320"] = ImageFont.truetype(bold, 44)
        fonts["pill"] = ImageFont.truetype(bold, 16)
        fonts["h1"] = ImageFont.truetype(bold, 34)
        fonts["sub"] = ImageFont.truetype(reg, 19)
        fonts["feat"] = ImageFont.truetype(semi, 14)
        fonts["chrome"] = ImageFont.truetype(reg, 13)
    except Exception:
        default = ImageFont.load_default()
        fonts = {k: default for k in ("brand", "brand320", "pill", "h1", "sub", "feat", "chrome")}
    return fonts


def _rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def _wrap_text(draw, text, font, max_width):
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        trial = " ".join(current + [word])
        if draw.textlength(trial, font=font) <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


def _draw_left_panel(base: Image.Image, fonts: dict) -> None:
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    card_x, card_y = 44, 44
    card_w, card_h = 548, H - 88
    _rounded_rect(draw, (card_x, card_y, card_x + card_w, card_y + card_h), 18, (*CARD, 252), outline=(*PILL_BORDER, 70), width=1)
    draw.rectangle((card_x, card_y, card_x + card_w, card_y + 4), fill=TOP_ACCENT)

    px, py = card_x + 32, card_y + 32
    if FAVICON.is_file():
        icon = Image.open(FAVICON).convert("RGBA")
        icon = icon.resize((32, 32), Image.Resampling.LANCZOS)
        overlay.paste(icon, (px, py), icon)
        tx = px + 40
    else:
        tx = px

    draw.text((tx, py), "PBJ", font=fonts["brand"], fill=INK)
    pbj_w = draw.textlength("PBJ", font=fonts["brand"])
    draw.text((tx + pbj_w, py), "320", font=fonts["brand320"], fill=ACCENT)

    pill_x = int(tx + pbj_w + draw.textlength("320", font=fonts["brand320"]) + 14)
    pill_y = py + 4
    pill_text = "PREMIUM"
    pill_tw = int(draw.textlength(pill_text, font=fonts["pill"]) + 24)
    _rounded_rect(draw, (pill_x, pill_y, pill_x + pill_tw, pill_y + 26), 999, (255, 255, 255, 255), outline=PILL_BORDER, width=1)
    draw.text((pill_x + 12, pill_y + 5), pill_text, font=fonts["pill"], fill=ACCENT_DARK)

    py += 52
    headline = "Nursing Home Staffing & Ownership Intelligence"
    for i, line in enumerate(_wrap_text(draw, headline, fonts["h1"], card_w - 64)):
        draw.text((px, py + i * 40), line, font=fonts["h1"], fill=INK)
    py += len(_wrap_text(draw, headline, fonts["h1"], card_w - 64)) * 40 + 14

    sub = "Daily PBJ patterns, employee rosters, ownership context, and report-ready exports."
    for i, line in enumerate(_wrap_text(draw, sub, fonts["sub"], card_w - 64)):
        draw.text((px, py + i * 26), line, font=fonts["sub"], fill=MUTED)
    py += len(_wrap_text(draw, sub, fonts["sub"], card_w - 64)) * 26 + 22

    col_w = (card_w - 64 - 12) // 2
    for idx, (label, dot_color) in enumerate(FEATURES):
        col = idx % 2
        row = idx // 2
        fx = px + col * (col_w + 12)
        fy = py + row * 36
        draw.ellipse((fx, fy + 4, fx + 8, fy + 12), fill=dot_color)
        draw.text((fx + 14, fy), label, font=fonts["feat"], fill=MUTED_LIGHT)

    base.paste(overlay, (0, 0), overlay)


def _paste_dashboard(base: Image.Image, fonts: dict, dash_path: Path) -> None:
    shot = Image.open(dash_path).convert("RGB")
    frame_x, frame_y = 608, 52
    frame_w, frame_h = 548, H - 104
    chrome_h = 32
    pad = 8

    shadow = Image.new("RGBA", (frame_w + 16, frame_h + 16), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    _rounded_rect(sd, (8, 8, frame_w + 8, frame_h + 8), 18, (15, 23, 42, 50))
    try:
        from PIL import ImageFilter
        shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    except Exception:
        pass
    base.paste(shadow, (frame_x - 6, frame_y + 6), shadow)

    frame_bg = Image.new("RGB", (frame_w, frame_h), CARD)
    fd = ImageDraw.Draw(frame_bg)
    fd.rectangle((0, 0, frame_w, 3), fill=TOP_ACCENT)
    fd.rectangle((0, 0, frame_w, chrome_h), fill=(248, 250, 252))
    for i, color in enumerate([(239, 68, 68), (250, 204, 21), (34, 197, 94)]):
        cx = 14 + i * 14
        fd.ellipse((cx, 11, cx + 8, 19), fill=color)
    fd.text((52, 9), "PBJ320 Premium — Phoebe Jay (320365)", font=fonts.get("chrome"), fill=MUTED_LIGHT)
    base.paste(frame_bg, (frame_x, frame_y))

    inner_w = frame_w - pad * 2
    inner_h = frame_h - chrome_h - pad
    sw, sh = shot.size
    scale = min(inner_w / sw, inner_h / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    shot_r = shot.resize((nw, nh), Image.Resampling.LANCZOS)
    paste_x = frame_x + pad + (inner_w - nw) // 2
    paste_y = frame_y + chrome_h + pad + (inner_h - nh) // 2
    base.paste(shot_r, (paste_x, paste_y))

    border = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(border)
    _rounded_rect(bd, (frame_x, frame_y, frame_x + frame_w, frame_y + frame_h), 14, fill=None, outline=(148, 163, 184), width=1)
    base.paste(border, (0, 0), border)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fonts = _load_fonts()
    img = _gradient_bg().convert("RGBA")
    _draw_left_panel(img, fonts)

    dash = _render_dashboard_html()
    if dash and dash.is_file():
        print(f"Dashboard render: {dash}")
        _paste_dashboard(img, fonts, dash)
    else:
        fallback = ROOT / "premium" / "demo" / "demo.png"
        if fallback.is_file():
            print(f"Dashboard fallback: {fallback}")
            _paste_dashboard(img, fonts, fallback)

    img.convert("RGB").save(OUT, "PNG", optimize=True)
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
