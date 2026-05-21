#!/usr/bin/env python3
"""Scan repo text files for U+FFFD and common UTF-8 mojibake."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".cursor",
}
SKIP_EXT = {
    ".pyc",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".zip",
    ".pdf",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".parquet",
    ".feather",
    ".pkl",
    ".pickle",
}
SKIP_EXT.add(".csv")

TEXT_EXT = {
    ".html",
    ".htm",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".md",
    ".txt",
    ".py",
    ".json",
    ".csv",
    ".xml",
    ".yml",
    ".yaml",
    ".sql",
    ".sh",
    ".ps1",
    ".bat",
    ".svg",
}

SKIP_PATH_PARTS = (
    "facility_quarterly_metrics",
    "facility_lite_metrics",
    "pbj-wrapped/public/data",
    ".pre_dedupe_",
    ".pre_unify_",
    "_archive",
)

PATTERNS = [
    ("\uFFFD (replacement)", "\uFFFD"),
    ("mojibake apostrophe", "â€™"),
    ("mojibake em dash", "â€”"),
    ("mojibake en dash", "â€“"),
]


def _skip_path(path: Path) -> bool:
    s = str(path)
    return any(part in s for part in SKIP_PATH_PARTS)


def iter_files() -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            if _skip_path(p) or p.name == Path(__file__).name:
                continue
            if p.suffix.lower() in SKIP_EXT:
                continue
            if p.suffix.lower() not in TEXT_EXT and p.name not in {
                "Dockerfile",
                "Makefile",
                ".gitignore",
            }:
                continue
            out.append(p)
    return out


def main() -> int:
    hits: list[tuple[str, Path, int, str]] = []
    for path in iter_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            hits.append(("non-UTF-8 file", path, 0, ""))
            continue
        for label, pat in PATTERNS:
            if pat not in text:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if pat in line:
                    hits.append((label, path, i, line.strip()[:120]))

    if not hits:
        print("No encoding glitches found.")
        return 0

    print(f"Found {len(hits)} hit(s):\n")
    for label, path, line_no, snippet in hits:
        rel = path.relative_to(ROOT)
        print(f"  [{label}] {rel}:{line_no}")
        if snippet:
            print(f"    {snippet}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
