"""Optional local observation helpers (NOT used by GitHub Actions).

Durable release dedup for the scheduled watcher is GitHub issues only.
Do not commit watcher state to ``master`` — that branch auto-deploys Render.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Legacy path — must not be written by CI. Prefer issues for dedup.
DEFAULT_STATE_REL = Path("data/cms_watcher/watcher_state.json")
STATE_VERSION = 1


def default_state_path(root: Path | None = None) -> Path:
    base = root or Path(__file__).resolve().parents[1]
    return base / DEFAULT_STATE_REL


def load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "version": STATE_VERSION,
            "sources": {},
            "last_run_at": None,
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("watcher state must be a JSON object")
    data.setdefault("version", STATE_VERSION)
    data.setdefault("sources", {})
    return data


def save_state(path: Path, state: dict[str, Any]) -> None:
    """Write local scratch state only. Never call from the Actions workflow."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(state)
    payload["version"] = STATE_VERSION
    payload["last_run_at"] = datetime.now(timezone.utc).isoformat()
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def update_source_observation(
    state: dict[str, Any],
    *,
    source_id: str,
    cms_fingerprint: str,
    cms_snapshot: dict[str, Any],
    production_snapshot: dict[str, Any],
    statuses: list[str],
) -> None:
    sources = state.setdefault("sources", {})
    prev = sources.get(source_id) if isinstance(sources.get(source_id), dict) else {}
    sources[source_id] = {
        "cms_fingerprint": cms_fingerprint,
        "cms": cms_snapshot,
        "production": production_snapshot,
        "statuses": statuses,
        "previous_cms_fingerprint": prev.get("cms_fingerprint"),
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
