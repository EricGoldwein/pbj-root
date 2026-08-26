"""CLI entry: observe CMS metadata vs PBJ320 production freshness.

Never commits, pushes, or writes tracked production-branch state.
Durable release dedup lives in GitHub issues (open or closed).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow `python -m cms_watcher` and `python scripts/run_cms_release_watcher.py`
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cms_watcher.cms_fetch import fetch_cms_state  # noqa: E402
from cms_watcher.compare import SourceEvaluation, evaluate_source  # noqa: E402
from cms_watcher.notify import maybe_create_issue, should_alert  # noqa: E402
from cms_watcher.production_state import read_production_state  # noqa: E402
from cms_watcher.registry import SOURCE_REGISTRY, dependency_graph_rows  # noqa: E402


def _print_dependency_graph() -> None:
    rows = dependency_graph_rows()
    print("source_id\tartifact\tpersistence\tsurfaces\ttransform")
    for row in rows:
        print(
            f"{row['source_id']}\t{row['artifact']}\t{row.get('persistence','')}\t"
            f"{row.get('surfaces','')}\t{row.get('transform','')}"
        )


def _annotate_new_release(evaluation: SourceEvaluation) -> None:
    if "NEW_RELEASE" not in evaluation.statuses:
        evaluation.statuses.insert(0, "NEW_RELEASE")
    evaluation.summary = (
        f"CMS CURRENT: "
        f"{(evaluation.cms or {}).get('data_vintage_label') or (evaluation.cms or {}).get('distribution_filename') or '?'} "
        f"| PBJ320 CURRENT: {(evaluation.production or {}).get('vintage_label') or 'UNKNOWN'} "
        f"| STATUS: {', '.join(evaluation.statuses)}"
    )


def run_watch(
    *,
    root: Path,
    notify: bool,
    dry_run_notify: bool,
    source_ids: list[str] | None,
    gh_api: Any | None = None,
    existing_issues_by_fp: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Observe CMS vs production. Never writes the git working tree.

    ``last_checked_at`` is returned in the report only (runtime output).
    """
    checked_at = datetime.now(timezone.utc).isoformat()
    catalog_cache: dict[str, Any] = {}
    evaluations: list[SourceEvaluation] = []
    notify_results: list[dict[str, Any]] = []

    selected = SOURCE_REGISTRY
    if source_ids:
        wanted = set(source_ids)
        selected = tuple(s for s in SOURCE_REGISTRY if s.source_id in wanted)

    for source in selected:
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
            check_error=err,
        )

        if notify or dry_run_notify:
            fp = str((evaluation.cms or {}).get("raw_fingerprint") or "")
            injected = None
            if existing_issues_by_fp is not None and fp:
                injected = existing_issues_by_fp.get(f"{source.source_id}:{fp}")
            note = maybe_create_issue(
                evaluation,
                dry_run=dry_run_notify or not notify,
                gh_api=gh_api,
                existing_issue=injected,
                skip_remote_lookup=existing_issues_by_fp is not None,
            )
            notify_results.append(note)
            # NEW_RELEASE = first alertable fingerprint with no prior open/closed issue.
            if note.get("would_set_new_release") and should_alert(evaluation):
                _annotate_new_release(evaluation)
        evaluations.append(evaluation)

    report = {
        "last_checked_at": checked_at,
        "evaluations": [e.to_dict() for e in evaluations],
        "notifications": notify_results,
        "wrote_repo_files": False,
        "git_commit": False,
        "git_push": False,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only CMS release + PBJ320 downstream-freshness watcher. "
            "Does not download datasets, rebuild artifacts, commit, or push."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=_ROOT,
        help="pbj-root repository root (default: inferred)",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Create deduplicated GitHub issues when PRODUCTION_BEHIND (no git writes)",
    )
    parser.add_argument(
        "--dry-run-notify",
        action="store_true",
        help="Print issue payloads without creating issues",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON report (includes last_checked_at)",
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
    report = run_watch(
        root=root,
        notify=args.notify,
        dry_run_notify=args.dry_run_notify,
        source_ids=args.sources,
    )

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"last_checked_at: {report['last_checked_at']}")
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
