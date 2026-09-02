#!/usr/bin/env python3
"""Validate staged changes against declared release scope and protected regions."""
from __future__ import annotations

import argparse
import fnmatch
import re
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from _git_helpers import repo_root, staged_diff_text, staged_files


# High-blast-radius app.py symbols (PR #5 owners revert touched these).
PROTECTED_APP_SYMBOLS = (
    "_owners_cms_index_html",
    "_owners_hub_index_json_ld",
    "_owners_state_index_html",
    "generate_owner_profile_html",
)

PROTECTED_APP_ROUTE_FRAGMENTS = (
    "/owners/api/related-associates",
    "/owners/api/owner-facilities",
    "/owners/api/cms-search",
)

PROTECTED_PATH_PREFIXES = (
    "ownership/",
    "render.yaml",
    "scripts/ensure_deploy_csvs.py",
    "scripts/build_owners_database.py",
    "scripts/build_snf_owners_index.py",
    "scripts/validate_release.py",
    "instance/",
    "donor/.env",
)

PR5_REGRESSION_MARKERS = (
    "owners-hub-state-cards",
    "Public ownership index — links to NY/CT/FL",
)

OWNERS_HANDLER_NOTE = "app.py ownership handlers"


def _parse_scope(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"TASK": [], "INTENDED": [], "DO NOT SHIP": []}
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        header = line.split(":", 1)[0].strip().upper()
        if header == "TASK":
            current = "TASK"
            if ":" in line:
                sections["TASK"].append(line.split(":", 1)[1].strip())
            continue
        if header == "INTENDED":
            current = "INTENDED"
            continue
        if header == "DO NOT SHIP":
            current = "DO NOT SHIP"
            continue
        if current:
            sections[current].append(line)
    return sections


def _load_scope(path: Path) -> dict[str, list[str]]:
    if not path.is_file():
        example = path.with_name("release_scope.example.txt")
        if example.is_file():
            print(f"WARNING: {path.name} missing; using {example.name}", file=sys.stderr)
            return _parse_scope(example.read_text(encoding="utf-8"))
        print(f"ERROR: no release scope file at {path}", file=sys.stderr)
        sys.exit(2)
    return _parse_scope(path.read_text(encoding="utf-8"))


def _path_matches_pattern(path: str, pattern: str) -> bool:
    pat = pattern.strip()
    if not pat:
        return False
    if pat.endswith("/*") or pat.endswith("\\*"):
        return path.startswith(pat.rstrip("*").rstrip("/") + "/") or fnmatch.fnmatch(path, pat)
    if pat.endswith("*"):
        return fnmatch.fnmatch(path, pat)
    if pat == OWNERS_HANDLER_NOTE:
        return False
    return path == pat or path.startswith(pat.rstrip("/") + "/")


def _intended_allows(path: str, intended: list[str]) -> bool:
    if not intended:
        return True
    for pattern in intended:
        if _path_matches_pattern(path, pattern):
            return True
    return False


def _do_not_ship_blocks(path: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        if pattern.strip() == OWNERS_HANDLER_NOTE:
            continue
        if _path_matches_pattern(path, pattern):
            return pattern
    return None


def _app_py_staged_diff() -> str:
    return staged_diff_text("app.py")


def _protected_symbols_in_app_diff(diff: str) -> list[str]:
    found: list[str] = []
    for symbol in PROTECTED_APP_SYMBOLS:
        if symbol in diff:
            found.append(symbol)
    return found


def _pr5_regression_markers_in_app_diff(diff: str) -> list[str]:
    found: list[str] = []
    for marker in PR5_REGRESSION_MARKERS:
        if marker in diff:
            found.append(marker)
    return found


def _task_text(scope: dict[str, list[str]]) -> str:
    return " ".join(scope.get("TASK") or ["(not declared)"])


def _is_nav_like_task(task: str) -> bool:
    t = task.lower()
    return any(k in t for k in ("nav", "navbar", "menu", "site-shell", "site shell", "header", "footer"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check staged diff against release scope.")
    parser.add_argument(
        "--scope-file",
        default="tools/release_scope.txt",
        help="Release scope declaration file.",
    )
    args = parser.parse_args()

    root = repo_root()
    scope_path = root / args.scope_file
    scope = _load_scope(scope_path)
    task = _task_text(scope)
    intended = scope.get("INTENDED") or []
    do_not_ship = scope.get("DO NOT SHIP") or []

    staged = staged_files()
    failures: list[str] = []
    warnings: list[str] = []

    if not staged:
        print("FAIL: nothing staged")
        print("Stage only files intended for this release: git add -- <paths>")
        return 1

    # Unexpected staged files vs INTENDED list.
    if intended:
        unexpected = [p for p in staged if not _intended_allows(p, intended)]
        if unexpected:
            failures.append("Unexpected staged files (not listed under INTENDED):")
            for path in unexpected:
                failures.append(f"  - {path}")

    # DO NOT SHIP path patterns.
    for path in staged:
        blocked = _do_not_ship_blocks(path, do_not_ship)
        if blocked:
            failures.append(f"Staged file matches DO NOT SHIP pattern '{blocked}': {path}")

    # app.py protected regions.
    if "app.py" in staged:
        app_diff = _app_py_staged_diff()
        symbols = _protected_symbols_in_app_diff(app_diff)
        pr5 = _pr5_regression_markers_in_app_diff(app_diff)

        owners_handlers_blocked = any(
            p.strip().lower() in {OWNERS_HANDLER_NOTE.lower(), "app.py ownership handlers"}
            for p in do_not_ship
        )

        if symbols and owners_handlers_blocked:
            if _is_nav_like_task(task) and "app.py" not in intended:
                failures.append(
                    "Staged app.py modifies protected ownership handler(s) during a nav/site-shell task:"
                )
                for sym in symbols:
                    failures.append(f"  - app.py::{sym}")
            elif "app.py" in intended:
                warnings.append(
                    "app.py is INTENDED but touches protected ownership symbols — review every hunk:"
                )
                for sym in symbols:
                    warnings.append(f"  - app.py::{sym}")
            else:
                failures.append("Staged app.py touches protected ownership handler(s):")
                for sym in symbols:
                    failures.append(f"  - app.py::{sym}")

        if pr5:
            failures.append("Staged app.py contains PR #5-style owners hub regression marker(s):")
            for marker in pr5:
                failures.append(f"  - {marker!r}")

        for route in PROTECTED_APP_ROUTE_FRAGMENTS:
            if route in app_diff and route not in "".join(intended):
                if owners_handlers_blocked or _is_nav_like_task(task):
                    failures.append(f"Staged app.py modifies protected route fragment: {route}")

    # Protected prefixes even if not explicitly in DO NOT SHIP (warn only unless nav task).
    for path in staged:
        for prefix in PROTECTED_PATH_PREFIXES:
            if path.startswith(prefix) or path == prefix:
                if _is_nav_like_task(task) and not _intended_allows(path, intended):
                    failures.append(
                        f"High-blast-radius path staged during nav/site-shell task: {path} "
                        f"(matches protected prefix {prefix!r})"
                    )
                elif not _intended_allows(path, intended):
                    warnings.append(f"Staged path in protected area — confirm intent: {path}")

    # Local WIP warning when unstaged modifications exist (not a failure).
    from _git_helpers import unstaged_modified_files

    unstaged = unstaged_modified_files()
    unstaged_only = sorted(set(unstaged) - set(staged))
    if unstaged_only:
        warnings.append(
            f"{len(unstaged_only)} modified file(s) remain unstaged (local WIP - not part of this release)."
        )

    print()
    print("=" * 72)
    print("RELEASE DIFF CHECK")
    print("=" * 72)
    print(f"Declared task: {task}")
    print()
    print("Expected files (INTENDED):")
    if intended:
        for item in intended:
            print(f"  - {item}")
    else:
        print("  (none declared — scope check is permissive)")
    print()
    print(f"Staged files ({len(staged)}):")
    for path in staged:
        print(f"  - {path}")

    if warnings:
        print()
        print("WARNINGS:")
        for w in warnings:
            print(f"  {w}")

    if failures:
        print()
        print("FAIL: release scope mismatch")
        print()
        for line in failures:
            print(line)
        print()
        print("Do not commit until unexpected files/hunks are removed or explicitly added to INTENDED.")
        return 1

    print()
    print("PASS: staged changes match declared release scope.")
    if warnings:
        print("(Warnings present - review local WIP before commit.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
