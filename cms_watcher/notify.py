"""GitHub issue notifications for genuine new CMS releases (deduplicated)."""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .compare import SourceEvaluation

ISSUE_LABEL = "cms-release-watcher"
TITLE_PREFIX = "CMS release detected:"


def issue_title(evaluation: SourceEvaluation) -> str:
    cms = evaluation.cms or {}
    vintage = cms.get("data_vintage_label") or cms.get("distribution_filename") or "unknown"
    return f"{TITLE_PREFIX} {evaluation.title} — {vintage}"


def issue_body(evaluation: SourceEvaluation) -> str:
    cms = evaluation.cms or {}
    prod = evaluation.production or {}
    lines = [
        "## CMS release detected (read-only watcher)",
        "",
        f"**Source:** {evaluation.title} (`{evaluation.source_id}`)",
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
            "- If freshness is `UNKNOWN`, prove activation via the Quarter Release Playbook / ownership policy before claiming CURRENT.",
            "",
            f"<!-- cms-release-watcher:{evaluation.source_id}:{cms.get('raw_fingerprint', '')} -->",
        ]
    )
    return "\n".join(lines) + "\n"


def _gh_api(
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
    # https://github.com/org/repo.git or git@github.com:org/repo.git
    if out.endswith(".git"):
        out = out[:-4]
    if "github.com/" in out:
        return out.split("github.com/", 1)[1]
    if "github.com:" in out:
        return out.split("github.com:", 1)[1]
    return None


def find_open_issue(repo: str, title: str, token: str) -> dict[str, Any] | None:
    q = f'repo:{repo} is:issue is:open label:{ISSUE_LABEL} in:title "{title}"'
    path = f"/search/issues?q={urllib.parse.quote(q)}"
    try:
        result = _gh_api("GET", path, token=token)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    items = (result or {}).get("items") or []
    for item in items:
        if item.get("title") == title:
            return item
    return items[0] if items else None


def ensure_label(repo: str, token: str) -> None:
    owner, name = repo.split("/", 1)
    try:
        _gh_api("GET", f"/repos/{owner}/{name}/labels/{urllib.parse.quote(ISSUE_LABEL)}", token=token)
        return
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            return
    try:
        _gh_api(
            "POST",
            f"/repos/{owner}/{name}/labels",
            token=token,
            body={
                "name": ISSUE_LABEL,
                "color": "0E8A16",
                "description": "Automated CMS release detection (read-only watcher)",
            },
        )
    except (urllib.error.URLError, TimeoutError, OSError):
        pass


def maybe_create_issue(
    evaluation: SourceEvaluation,
    *,
    token: str | None = None,
    repo: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Create a deduplicated GitHub issue when NEW_RELEASE is present."""
    if "NEW_RELEASE" not in evaluation.statuses:
        return {"action": "skipped", "reason": "no NEW_RELEASE status"}

    token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repo = repo or _repo_slug_from_env()
    title = issue_title(evaluation)
    body = issue_body(evaluation)

    if dry_run or not token or not repo:
        return {
            "action": "dry_run" if dry_run or not token else "skipped",
            "reason": None if (dry_run or token) else "missing token/repo",
            "title": title,
            "body": body,
            "repo": repo,
        }

    ensure_label(repo, token)
    existing = find_open_issue(repo, title, token)
    if existing:
        return {
            "action": "exists",
            "title": title,
            "url": existing.get("html_url"),
            "number": existing.get("number"),
        }

    owner, name = repo.split("/", 1)
    created = _gh_api(
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
    }
