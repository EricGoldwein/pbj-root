"""CLI entry: observe CMS metadata vs PBJ320 production freshness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Allow `python -m cms_watcher` and `python scripts/run_cms_release_watcher.py`
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cms_watcher.cms_fetch import fetch_cms_state  # noqa: E402
from cms_watcher.compare import SourceEvaluation, evaluate_source  # noqa: E402
from cms_watcher.notify import maybe_create_issue  # noqa: E402
from cms_watcher.production_state import read_production_state  # noqa: E402
from cms_watcher.registry import SOURCE_REGISTRY, dependency_graph_rows  # noqa: E402
from cms_watcher.state_store import (  # noqa: E402
    default_state_path,
    load_state,
    save_state,
    update_source_observation,
)


def _print_dependency_graph() -> None:
    rows = dependency_graph_rows()
    print("source_id\tartifact\tpersistence\tsurfaces\ttransform")
    for row in rows:
        print(
            f"{row['source_id']}\t{row['artifact']}\t{row.get('persistence','')}\t"
            f"{row.get('surfaces','')}\t{row.get('transform','')}"
        )


def run_watch(
    *,
    root: Path,
    state_path: Path,
    write_state: bool,
    notify: bool,
    dry_run_notify: bool,
    source_ids: list[str] | None,
) -> dict[str, Any]:
    state = load_state(state_path)
    catalog_cache: dict[str, Any] = {}
    evaluations: list[SourceEvaluation] = []
    notify_results: list[dict[str, Any]] = []

    selected = SOURCE_REGISTRY
    if source_ids:
        wanted = set(source_ids)
        selected = tuple(s for s in SOURCE_REGISTRY if s.source_id in wanted)

    for source in selected:
        prev = (state.get("sources") or {}).get(source.source_id) or {}
        prev_fp = prev.get("cms_fingerprint") if isinstance(prev, dict) else None
        production = read_production_state(source.source_id, root=root)
        cms = None
        err = None
        try:
            cms = fetch_cms_state(source, catalog_cache=catalog_cache)
        except Exception as exc:  # noqa: BLE001 — surface as CHECK_FAILED
            err = str(exc)

        evaluation = evaluate_source(
            source,
            cms=cms,
            production=production,
            previous_fingerprint=prev_fp if isinstance(prev_fp, str) else None,
            check_error=err,
        )
        evaluations.append(evaluation)

        if cms is not None and write_state:
            update_source_observation(
                state,
                source_id=source.source_id,
                cms_fingerprint=cms.raw_fingerprint,
                cms_snapshot=cms.to_dict(),
                production_snapshot=production.to_dict(),
                statuses=evaluation.statuses,
            )

        if notify or dry_run_notify:
            notify_results.append(
                maybe_create_issue(
                    evaluation,
                    dry_run=dry_run_notify or not notify,
                )
            )

    if write_state:
        save_state(state_path, state)

    report = {
        "evaluations": [e.to_dict() for e in evaluations],
        "notifications": notify_results,
        "state_path": str(state_path),
        "wrote_state": write_state,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only CMS release + PBJ320 downstream-freshness watcher. "
            "Does not download datasets or rebuild artifacts."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=_ROOT,
        help="pbj-root repository root (default: inferred)",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=None,
        help="Watcher state JSON (default: data/cms_watcher/watcher_state.json)",
    )
    parser.add_argument(
        "--write-state",
        action="store_true",
        help="Persist updated CMS fingerprints to the state file",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Create deduplicated GitHub issues for NEW_RELEASE statuses",
    )
    parser.add_argument(
        "--dry-run-notify",
        action="store_true",
        help="Print issue payloads without calling GitHub",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON report",
    )
    parser.add_argument(
        "--print-dependency-graph",
        action="store_true",
        help="Print source→artifact dependency map and exit",
    )
    parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        help="Limit to source_id (repeatable)",
    )
    args = parser.parse_args(argv)

    if args.print_dependency_graph:
        _print_dependency_graph()
        return 0

    root = args.root.resolve()
    state_path = (args.state_file or default_state_path(root)).resolve()
    report = run_watch(
        root=root,
        state_path=state_path,
        write_state=args.write_state,
        notify=args.notify,
        dry_run_notify=args.dry_run_notify,
        source_ids=args.sources,
    )

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for ev in report["evaluations"]:
            print("=" * 72)
            print(f"{ev['title']} ({ev['source_id']})")
            print(f"  statuses: {', '.join(ev['statuses'])}")
            print(f"  {ev['summary']}")
            if ev.get("check_error"):
                print(f"  error: {ev['check_error']}")
            cms = ev.get("cms") or {}
            if cms:
                print(
                    f"  CMS file: {cms.get('distribution_filename')} "
                    f"(modified={cms.get('modified')} released={cms.get('released')})"
                )
            prod = ev.get("production") or {}
            print(f"  PBJ320 vintage: {prod.get('vintage_label')} known={prod.get('status_known')}")
            print(f"  surfaces: {', '.join(ev.get('affected_surfaces') or [])}")
        for note in report.get("notifications") or []:
            print("-" * 72)
            print(f"notify: {note.get('action')} {note.get('title') or note.get('reason')}")
            if note.get("url"):
                print(f"  url: {note['url']}")

    # Exit 0 even when behind — this is observational, not a deploy gate failure.
    # Exit 2 only if every source CHECK_FAILED.
    evals = report["evaluations"]
    if evals and all("CHECK_FAILED" in e["statuses"] for e in evals):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
