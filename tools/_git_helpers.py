"""Shared read-only git helpers for release workflow tools."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print("ERROR: not inside a git repository.", file=sys.stderr)
        sys.exit(2)
    return Path(result.stdout.strip())


def run_git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    root = cwd or repo_root()
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )


def git_output(*args: str) -> str:
    result = run_git(*args)
    if result.returncode != 0 and result.stderr.strip():
        return ""
    return result.stdout.strip()


def branch_name() -> str:
    return git_output("symbolic-ref", "--short", "HEAD") or git_output("rev-parse", "--short", "HEAD")


def origin_master_ref() -> str:
    if run_git("rev-parse", "--verify", "origin/master").returncode == 0:
        return git_output("rev-parse", "origin/master")
    if run_git("rev-parse", "--verify", "master").returncode == 0:
        return git_output("rev-parse", "master")
    return git_output("rev-parse", "HEAD")


def ahead_behind() -> tuple[int | None, int | None]:
    result = run_git("rev-list", "--left-right", "--count", f"{origin_master_ref()}...HEAD")
    if result.returncode != 0 or not result.stdout.strip():
        return None, None
    parts = result.stdout.strip().split()
    if len(parts) != 2:
        return None, None
    return int(parts[0]), int(parts[1])


def staged_files() -> list[str]:
    text = git_output("diff", "--cached", "--name-only")
    return [line for line in text.splitlines() if line.strip()]


def unstaged_modified_files() -> list[str]:
    text = git_output("diff", "--name-only")
    return [line for line in text.splitlines() if line.strip()]


def untracked_files() -> list[str]:
    text = git_output("ls-files", "--others", "--exclude-standard")
    return [line for line in text.splitlines() if line.strip()]


def stash_entries() -> list[str]:
    text = git_output("stash", "list")
    return [line for line in text.splitlines() if line.strip()]


def diff_stat(args: list[str]) -> str:
    result = run_git("diff", *args, "--stat")
    return result.stdout.strip() if result.stdout.strip() else "(no changes)"


def staged_diff_text(path: str | None = None) -> str:
    args = ["diff", "--cached", "-U0"]
    if path:
        args.extend(["--", path])
    result = run_git(*args)
    return result.stdout


def files_with_staged_and_unstaged() -> list[str]:
    staged = set(staged_files())
    unstaged = set(unstaged_modified_files())
    return sorted(staged & unstaged)
