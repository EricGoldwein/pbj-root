#!/usr/bin/env python3
"""Run preflight + release diff check + smoke tests (no deploy)."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], *, cwd: Path) -> int:
    print()
    print("$", " ".join(cmd))
    print("-" * 72)
    result = subprocess.run(cmd, cwd=str(cwd))
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Release preflight wrapper: scope check + smoke tests. Does not deploy."
    )
    parser.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Skip pytest smoke suite.",
    )
    parser.add_argument(
        "--scope-file",
        default="tools/release_scope.txt",
        help="Release scope file path.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    tools = root / "tools"
    scope_arg = ["--scope-file", args.scope_file]

    codes: list[tuple[str, int]] = []

    codes.append(("preflight", _run([sys.executable, str(tools / "preflight.py"), *scope_arg], cwd=root)))

    codes.append(
        (
            "check_release_diff",
            _run([sys.executable, str(tools / "check_release_diff.py"), *scope_arg], cwd=root),
        )
    )

    if not args.skip_smoke:
        smoke_targets = [
            "tests/test_owners_hub_index_markers.py",
            "tests/test_release_smoke_invariants.py",
        ]
        codes.append(
            (
                "smoke_tests",
                _run([sys.executable, "-m", "pytest", "-q", *smoke_targets], cwd=root),
            )
        )

    print()
    print("=" * 72)
    print("RELEASE CHECK SUMMARY")
    print("=" * 72)
    failed = False
    for name, code in codes:
        status = "PASS" if code == 0 else "FAIL"
        print(f"  {name}: {status} (exit {code})")
        if code != 0:
            failed = True

    print()
    if failed:
        print("Release check FAILED — do not commit/push/deploy until resolved.")
        return 1
    print("Release check PASSED for currently staged changes.")
    print("Commit/push/deploy only when explicitly requested.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
