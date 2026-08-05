"""Shared guards for insights/social OG rasters.

Call from build scripts so blank PNGs cannot ship without a separate agent checklist.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

# Blank Playwright/cairo failures were ~3–5KB of near-solid navy.
DEFAULT_MIN_BYTES = 40_000
DEFAULT_MIN_UNIQUE_COLORS = 80


def assert_og_raster_ok(
    path: Path | str,
    *,
    min_bytes: int = DEFAULT_MIN_BYTES,
    min_unique_colors: int = DEFAULT_MIN_UNIQUE_COLORS,
    expect_size: tuple[int, int] | None = (1200, 630),
) -> None:
    """Raise SystemExit if the file looks like a failed/blank OG render."""
    p = Path(path)
    if not p.is_file():
        raise SystemExit(f"OG raster missing: {p}")
    size = p.stat().st_size
    if size < min_bytes:
        raise SystemExit(
            f"OG raster too small ({size} bytes < {min_bytes}): likely blank. Refusing ship: {p}"
        )
    with Image.open(p) as im:
        rgb = im.convert("RGB")
        if expect_size is not None and rgb.size != expect_size:
            raise SystemExit(f"OG size {rgb.size} != {expect_size}: {p}")
        colors = rgb.getcolors(maxcolors=200_000)
        n = len(colors) if colors else 200_000
        if n < min_unique_colors:
            raise SystemExit(
                f"OG looks empty (unique_colors≈{n} < {min_unique_colors}): {p}"
            )
