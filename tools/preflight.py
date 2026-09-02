#!/usr/bin/env python3
"""Read-only repo preflight: production baseline vs staged release vs local WIP."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from _git_helpers import (
    ahead_behind,
    branch_name,
    diff_stat,
    files_with_staged_and_unstaged,
    origin_master_ref,
    repo_root,
    run_git,
    staged_files,
    stash_entries,
    unstaged_modified_files,
    untracked_files,
)


def _short_sha(ref: str) -> str:
    result = run_git("rev-parse", "--short", ref)
    return result.stdout.strip() if result.returncode == 0 else ref[:12]


def _section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def _bullet_list(items: list[str], empty: str = "(none)") -> None:
    if not items:
        print(f"  {empty}")
        return
    for item in items:
        print(f"  - {item}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only git/release preflight for pbj-root.")
    parser.add_argument(
        "--scope-file",
        default="tools/release_scope.txt",
        help="Path to release scope file (informational only).",
    )
    args = parser.parse_args()

    root = repo_root()
    master = origin_master_ref()
    behind, ahead = ahead_behind()
    staged = staged_files()
    unstaged = unstaged_modified_files()
    untracked = untracked_files()
    stashes = stash_entries()
    overlap = files_with_staged_and_unstaged()

    scope_path = root / args.scope_file
    scope_exists = scope_path.is_file()

    _section("PRODUCTION BASELINE")
    print(f"  repo:            {root}")
    print(f"  branch:          {branch_name()}")
    print(f"  origin/master:   {_short_sha(master)} ({master})")
    if ahead is not None and behind is not None:
        print(f"  vs master:       {ahead} ahead, {behind} behind")
    else:
        print("  vs master:       (could not compute ahead/behind)")
    print()
    print("  Baseline is origin/master. Do not infer release intent from local WIP.")

    _section("STAGED / RELEASE CANDIDATE")
    print(f"  count: {len(staged)}")
    _bullet_list(staged)
    print()
    print("  staged diff summary:")
    for line in diff_stat(["--cached"]).splitlines():
        print(f"    {line}")
    if overlap:
        print()
        print("  WARNING: these files have BOTH staged and unstaged changes:")
        _bullet_list(overlap)
        print("  Partial staging is ambiguous — review hunks before commit.")

    _section("LOCAL WIP / NOT STAGED")
    print(f"  modified (unstaged): {len(unstaged)}")
    _bullet_list(unstaged[:40], empty="(none)")
    if len(unstaged) > 40:
        print(f"  ... and {len(unstaged) - 40} more modified files")
    print()
    print(f"  untracked: {len(untracked)}")
    _bullet_list(untracked[:25], empty="(none)")
    if len(untracked) > 25:
        print(f"  ... and {len(untracked) - 25} more untracked files")
    print()
    print("  unstaged diff summary (first 15 files):")
    stat = diff_stat([])
    lines = stat.splitlines()
    for line in lines[:15]:
        print(f"    {line}")
    if len(lines) > 15:
        print(f"    ... ({len(lines) - 15} more stat lines)")
    print()
    print(f"  stashes: {len(stashes)}")
    _bullet_list(stashes[:10], empty="(none)")

    _section("RELEASE INTENT")
    if scope_exists:
        print(f"  scope file: {scope_path.relative_to(root)}")
        try:
            scope_text = scope_path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            print(f"  WARNING: could not read scope file: {exc}")
            scope_text = []
        for line in scope_text[:20]:
            if line.strip():
                print(f"    {line}")
        if len(scope_text) > 20:
            print("    ...")
    else:
        print(f"  scope file missing: {scope_path.relative_to(root)}")
        print("  Copy tools/release_scope.example.txt → tools/release_scope.txt before shipping.")

    _section("AMBIGUITY CHECK")
    warnings: list[str] = []
    if not staged:
        warnings.append("Nothing staged — no release candidate selected.")
    if unstaged and staged:
        unstaged_only = sorted(set(unstaged) - set(staged))
        if unstaged_only:
            warnings.append(
                f"{len(unstaged_only)} modified file(s) exist locally but are NOT staged "
                "(expected for WIP; do not git add -A)."
            )
    if overlap:
        warnings.append(f"{len(overlap)} file(s) partially staged — review before commit.")
    staged_not_in_unstaged = sorted(set(staged) - set(unstaged) - set(untracked))
    if staged_not_in_unstaged:
        warnings.append(
            "Some staged files have no unstaged diff (fully staged or new file) — verify intent."
        )

    if warnings:
        for w in warnings:
            print(f"  WARNING: {w}")
    else:
        print("  No major ambiguity flags.")

    print()
    print("Existing local changes are NOT authorization to commit, push, merge, or deploy.")
    print("Next: python tools/check_release_diff.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
