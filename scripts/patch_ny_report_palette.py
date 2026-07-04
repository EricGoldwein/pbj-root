"""One-shot palette patch for insights-ny-minimum-staffing.html (not .classic.html)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "insights-ny-minimum-staffing.html"

# Order: longer / more specific strings first to avoid partial clashes.
REPLACEMENTS: list[tuple[str, str]] = [
    # Chart COLORS block + fallbacks (slate-aligned semantic palette)
    ("bad: '#c1380a',\n    badBg: 'rgba(193,56,10,0.78)',\n    ok: '#2e6647',\n    okBg: 'rgba(46,102,71,0.78)',\n    warn: '#9b6a00',\n    warnBg: 'rgba(155,106,0,0.78)',\n    weekday: '#5a7a99',\n    weekdayBg: 'rgba(90,122,153,0.78)',\n    weekend: '#c1380a',\n    weekendBg: 'rgba(193,56,10,0.78)',\n    slate: '#1d3f6b',\n    slateBg: 'rgba(29,63,107,0.15)',\n    muted: '#6b6158',",
     "bad: '#dc2626',\n    badBg: 'rgba(220,38,38,0.78)',\n    ok: '#059669',\n    okBg: 'rgba(5,150,105,0.78)',\n    warn: '#d97706',\n    warnBg: 'rgba(217,119,6,0.78)',\n    weekday: '#64748b',\n    weekdayBg: 'rgba(100,116,139,0.78)',\n    weekend: '#dc2626',\n    weekendBg: 'rgba(220,38,38,0.78)',\n    slate: '#2563eb',\n    slateBg: 'rgba(37,99,235,0.15)',\n    muted: '#64748b',"),
    ("ok: 'rgba(46,102,71,0.85)',\n      warn: 'rgba(155,106,0,0.85)',\n      bad: 'rgba(193,56,10,0.85)',",
     "ok: 'rgba(5,150,105,0.85)',\n      warn: 'rgba(217,119,6,0.85)',\n      bad: 'rgba(220,38,38,0.85)',"),
    ("return (C && C.okBg) || 'rgba(46,102,71,0.85)';\n    if (pct <= th.mid) return (C && C.warnBg) || 'rgba(155,106,0,0.85)';\n    return (C && C.badBg) || 'rgba(193,56,10,0.85)';",
     "return (C && C.okBg) || 'rgba(5,150,105,0.85)';\n    if (pct <= th.mid) return (C && C.warnBg) || 'rgba(217,119,6,0.85)';\n    return (C && C.badBg) || 'rgba(220,38,38,0.85)';"),
    ("var bad = (C && C.badBg) || 'rgba(193,56,10,0.78)';\n    var warn = (C && C.warnBg) || 'rgba(155,106,0,0.78)';\n    var ok = (C && C.okBg) || 'rgba(46,102,71,0.78)';",
     "var bad = (C && C.badBg) || 'rgba(220,38,38,0.78)';\n    var warn = (C && C.warnBg) || 'rgba(217,119,6,0.78)';\n    var ok = (C && C.okBg) || 'rgba(5,150,105,0.78)';"),
    (".county-map-svg--bubbles .is-focus {\n  stroke: #1d3f6b !important;",
     ".county-map-svg--bubbles .is-focus {\n  stroke: var(--accent-blue) !important;"),
    ("background: #8a939c;", "background: #94a3b8;"),
    ("frame.setAttribute('stroke', '#b8c0c8');", "frame.setAttribute('stroke', '#cbd5e1');"),
]


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    changed: list[str] = []
    for old, new in REPLACEMENTS:
        if old not in text:
            continue
        count = text.count(old)
        text = text.replace(old, new)
        changed.append(f"  {count}x {old[:48]!r}...")
    if not changed:
        print("No replacements applied (already patched?).")
        return
    TARGET.write_text(text, encoding="utf-8")
    print(f"Patched {TARGET.name}:")
    print("\n".join(changed))


if __name__ == "__main__":
    main()
