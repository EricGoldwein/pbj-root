"""GitHub issue notifications — durable dedup via open+closed issues (no repo commits)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from .compare import SourceEvaluation

ISSUE_LABEL = "cms-release-watcher"
TITLE_PREFIX = "CMS release detected:"
FINGERPRINT_RE = re.compile(
    r"<!--\s*cms-release-watcher:([a-z0-9_]+):([^:\s]+)\s*-->",
    re.I,
)

GhApi = Callable[..., Any]


def fingerprint_marker(source_id: str, fingerprint: str) -> str:
    return f"<!-- cms-release-watcher:{source_id}:{fingerprint} -->"


def issue_title(evaluation: SourceEvaluation) -> str:
    cms = evaluation.cms or {}
    vintage = cms.get("data_vintage_label") or cms.get("distribution_filename") or "unknown"
    return f"{TITLE_PREFIX} {evaluation.title} — {vintage}"


def issue_body(evaluation: SourceEvaluation) -> str:
    cms = evaluation.cms or {}
    prod = evaluation.production or {}
    fp = str(cms.get("raw_fingerprint") or "")
    lines = [
        "## CMS release detected (read-only watcher)",
        "",
        f"**Source:** {evaluation.title} (`{evaluation.source_id}`)",
        f"**Stable dataset key:** `{cms.get('stable_key')}`",
        f"**CMS fingerprint:** `{fp}`",
        f"**Statuses:** {', '.join(evaluation.statuses)}",
        f"**Summary:** {evaluation.summary}",
        "",
        "### CMS CURRENT",
        f"- released: `{cms.get('released')}`",
        f"- modified: `{cms.get('modified')}`",
        f"- nextUpdateDate: `{cms.get('next_update_date')}`",
        f"- temporal/coverage: `{cms.get('temporal')}`",
        f"- distribution filename: `{cms.get('distribution_filename')}`",
        f"- distribution URL: `{cms.get('distribution_url')}`",
        f"- data vintage label: `{cms.get('data_vintage_label')}`",
        "",
        "### PBJ320 CURRENT",
        f"- production vintage: `{prod.get('vintage_label')}`",
        f"- known: `{prod.get('status_known')}`",
        f"- detail: `{json.dumps(prod.get('detail') or {}, sort_keys=True)}`",
        "",
        "### Affected PBJ320 systems",
    ]
    for surface in evaluation.affected_surfaces:
        lines.append(f"- `{surface}`")
    lines.extend(["", "### Downstream artifacts expected to need refresh"])
    for art in evaluation.affected_downstream:
        lines.append(
            f"- **{art.get('name')}** (`{art.get('path')}`) — "
            f"persistence=`{art.get('persistence')}` freshness=`{art.get('freshness')}`"
        )
    lines.extend(
        [
            "",
            "### Notes",
            "- This watcher does **not** download, ingest, rebuild indexes, mutate policy, or deploy.",
            "- Durable dedup record is this issue (open or closed) keyed by the fingerprint marker below.",
            "- If freshness is `UNKNOWN`, prove activation via the Quarter Release Playbook / ownership policy before claiming CURRENT.",
            "",
            fingerprint_marker(evaluation.source_id, fp),
        ]
    )
    return "\n".join(lines) + "\n"


def _default_gh_api(
    method: str,
    path: str,
    *,
    token: str,
    body: dict[str, Any] | None = None,
) -> Any:
    url = f"https://api.github.com{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "PBJ320-cms-release-watcher",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else None


def _repo_slug_from_env() -> str | None:
    slug = os.environ.get("GITHUB_REPOSITORY")
    if slug:
        return slug
    try:
        out = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    if out.endswith(".git"):
        out = out[:-4]
    if "github.com/" in out:
        return out.split("github.com/", 1)[1]
    if "github.com:" in out:
        return out.split("github.com:", 1)[1]
    return None


def should_alert(evaluation: SourceEvaluation) -> bool:
    """Alert only when production lags CMS (not on CURRENT / unknown-only checks)."""
    if "CHECK_FAILED" in evaluation.statuses:
        return False
    return "PRODUCTION_BEHIND" in evaluation.statuses


def find_issue_by_fingerprint(
    repo: str,
    source_id: str,
    fingerprint: str,
    token: str,
    *,
    gh_api: GhApi | None = None,
) -> dict[str, Any] | None:
    """Find open OR closed watcher issue for this source+fingerprint."""
    api = gh_api or _default_gh_api
    marker = fingerprint_marker(source_id, fingerprint)
    # Search all issues (no is:open) so closed issues still dedupe.
    q = f'repo:{repo} is:issue label:{ISSUE_LABEL} cms-release-watcher:{source_id}:'
    path = f"/search/issues?q={urllib.parse.quote(q)}&per_page=50"
    try:
        result = api("GET", path, token=token)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, urllib.error.HTTPError):
        return None
    items = (result or {}).get("items") or []
    for item in items:
        body = item.get("body") or ""
        if marker in body:
            return item
        # Fallback: parse any watcher markers in body
        for match in FINGERPRINT_RE.finditer(body):
            if match.group(1) == source_id and match.group(2) == fingerprint:
                return item
    return None


def ensure_label(repo: str, token: str, *, gh_api: GhApi | None = None) -> None:
    api = gh_api or _default_gh_api
    owner, name = repo.split("/", 1)
    try:
        api("GET", f"/repos/{owner}/{name}/labels/{urllib.parse.quote(ISSUE_LABEL)}", token=token)
        return
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            return
    try:
        api(
            "POST",
            f"/repos/{owner}/{name}/labels",
            token=token,
            body={
                "name": ISSUE_LABEL,
                "color": "0E8A16",
                "description": "Automated CMS release detection (read-only watcher)",
            },
        )
    except (urllib.error.URLError, TimeoutError, OSError, urllib.error.HTTPError):
        pass


def maybe_create_issue(
    evaluation: SourceEvaluation,
    *,
    token: str | None = None,
    repo: str | None = None,
    dry_run: bool = False,
    gh_api: GhApi | None = None,
    existing_issue: dict[str, Any] | None = None,
    skip_remote_lookup: bool = False,
) -> dict[str, Any]:
    """Create one issue per CMS fingerprint when production is behind.

    Dedup: open **and** closed issues with the same fingerprint marker.
    Never commits to git / never touches Render.
    """
    if not should_alert(evaluation):
        return {"action": "skipped", "reason": "not PRODUCTION_BEHIND"}

    cms = evaluation.cms or {}
    fingerprint = str(cms.get("raw_fingerprint") or "")
    if not fingerprint:
        return {"action": "skipped", "reason": "missing CMS fingerprint"}

    token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repo = repo or _repo_slug_from_env()
    title = issue_title(evaluation)
    body = issue_body(evaluation)

    # Allow tests to inject an existing issue without GitHub.
    existing = existing_issue
    if existing is None and not skip_remote_lookup and token and repo and not dry_run:
        existing = find_issue_by_fingerprint(
            repo, evaluation.source_id, fingerprint, token, gh_api=gh_api
        )
    elif existing is None and not skip_remote_lookup and token and repo and dry_run:
        # Dry-run still consults GitHub when credentials exist (safe read).
        existing = find_issue_by_fingerprint(
            repo, evaluation.source_id, fingerprint, token, gh_api=gh_api
        )

    if existing:
        return {
            "action": "exists",
            "title": title,
            "url": existing.get("html_url"),
            "number": existing.get("number"),
            "state": existing.get("state"),
            "fingerprint": fingerprint,
            "would_set_new_release": False,
        }

    if dry_run or not token or not repo:
        return {
            "action": "dry_run" if dry_run or not token else "skipped",
            "reason": None if (dry_run or token) else "missing token/repo",
            "title": title,
            "body": body,
            "repo": repo,
            "fingerprint": fingerprint,
            "would_set_new_release": True,
        }

    api = gh_api or _default_gh_api
    ensure_label(repo, token, gh_api=api)
    # Re-check once more before create (race against another runner).
    existing = find_issue_by_fingerprint(
        repo, evaluation.source_id, fingerprint, token, gh_api=api
    )
    if existing:
        return {
            "action": "exists",
            "title": title,
            "url": existing.get("html_url"),
            "number": existing.get("number"),
            "state": existing.get("state"),
            "fingerprint": fingerprint,
            "would_set_new_release": False,
        }

    owner, name = repo.split("/", 1)
    created = api(
        "POST",
        f"/repos/{owner}/{name}/issues",
        token=token,
        body={"title": title, "body": body, "labels": [ISSUE_LABEL]},
    )
    return {
        "action": "created",
        "title": title,
        "url": (created or {}).get("html_url"),
        "number": (created or {}).get("number"),
        "fingerprint": fingerprint,
        "would_set_new_release": True,
    }
