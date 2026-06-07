#!/usr/bin/env python3
"""Pre-push: run ensure_deploy_csvs build gates using only git-tracked artifacts.

Render clones the repo — not your full working tree. Local-only files (e.g.
provider_info/NH_ProviderInfo_May2026.csv when gitignored) make validate/backfill
pass locally but fail on Render.

Usage (required before push when touching deploy gates or ProviderInfoNorm):

    python scripts/simulate_render_deploy_gates.py

Exit 0 = gates OK on tracked files only. Exit 1 = would fail Render build.
"""
from __future__ import annotations

import contextlib
import glob
import os
import subprocess
import sys

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _log(msg: str) -> None:
    print(msg, flush=True)


def _git_tracked_paths() -> set[str]:
    proc = subprocess.run(
        ['git', 'ls-files'],
        cwd=APP_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        _log('simulate_render_deploy_gates: ERROR git ls-files failed')
        sys.exit(1)
    return {line.strip().replace('\\', '/') for line in proc.stdout.splitlines() if line.strip()}


def _newest_tracked_norm_rel(tracked: set[str]) -> str | None:
    norms = sorted(
        p for p in tracked if p.startswith('provider_info/ProviderInfoNorm_') and p.endswith('.csv')
    )
    return norms[-1] if norms else None


@contextlib.contextmanager
def _hide_untracked_provider_info(tracked: set[str]):
    """Temporarily hide provider_info files not in git (simulate Render clone)."""
    provider_dir = os.path.join(APP_ROOT, 'provider_info')
    hidden: list[tuple[str, str]] = []
    if not os.path.isdir(provider_dir):
        yield
        return
    for name in os.listdir(provider_dir):
        rel = f'provider_info/{name}'.replace('\\', '/')
        if rel in tracked:
            continue
        src = os.path.join(provider_dir, name)
        if not os.path.isfile(src):
            continue
        stash = src + '.deploy_sim_hidden'
        os.rename(src, stash)
        hidden.append((src, stash))
    if hidden:
        _log(
            'simulate_render_deploy_gates: hiding local-only provider_info files: '
            + ', '.join(os.path.basename(s) for s, _ in hidden)
        )
    try:
        yield
    finally:
        for src, stash in hidden:
            if os.path.isfile(stash):
                os.rename(stash, src)


def _run_gate(script_name: str) -> int:
    path = os.path.join(APP_ROOT, 'scripts', script_name)
    if not os.path.isfile(path):
        _log(f'simulate_render_deploy_gates: skip missing {script_name}')
        return 0
    _log(f'simulate_render_deploy_gates: running {script_name} ...')
    return subprocess.call([sys.executable, path], cwd=APP_ROOT)


def main() -> int:
    os.chdir(APP_ROOT)
    tracked = _git_tracked_paths()
    norm = _newest_tracked_norm_rel(tracked)
    if not norm:
        _log('simulate_render_deploy_gates: ERROR no tracked ProviderInfoNorm_*.csv')
        return 1
    _log(f'simulate_render_deploy_gates: tracked norm={norm}')

    # Warn when paired NH exists locally but is not deployed (common footgun).
    import importlib.util

    validate_path = os.path.join(APP_ROOT, 'scripts', 'validate_provider_norm_snapshot.py')
    spec = importlib.util.spec_from_file_location('validate_provider_norm_snapshot', validate_path)
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        norm_abs = os.path.join(APP_ROOT, norm)
        nh_abs = mod._nh_path_for_norm(norm_abs)
        if nh_abs:
            nh_rel = os.path.relpath(nh_abs, APP_ROOT).replace('\\', '/')
            if nh_rel not in tracked:
                _log(
                    f'simulate_render_deploy_gates: NOTE paired NH not in git ({nh_rel}) '
                    f'-- Render uses Norm self-check only'
                )

    failed = False
    with _hide_untracked_provider_info(tracked):
        for script in ('backfill_provider_norm_urban.py', 'validate_provider_norm_snapshot.py'):
            rc = _run_gate(script)
            if rc != 0:
                failed = True
                _log(f'simulate_render_deploy_gates: FAIL {script} exited {rc}')

    if failed:
        _log('simulate_render_deploy_gates: ERROR would fail Render build — fix before push')
        return 1

    _log('simulate_render_deploy_gates: OK (tracked artifacts only)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
