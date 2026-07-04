"""Precomputed geographic intelligence bundles for /geo pages."""



from __future__ import annotations



import gzip

import json

import os

import sys

from typing import Any



BUNDLE_VERSION = 3

SUPPORTED_VERSIONS = frozenset({1, 2, 3})

DEFAULT_DIR = os.path.join("data", "geo_intelligence")





def _pbjapp_root() -> str:

    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "PBJapp")





def _ensure_pbjapp_path() -> None:

    root = _pbjapp_root()

    if os.path.isdir(root) and root not in sys.path:

        sys.path.insert(0, root)





def bundle_path(app_root: str, state_slug: str) -> str:

    override = (os.environ.get("PBJ_GEO_INTELLIGENCE_PATH") or "").strip()

    if override:

        return override if os.path.isabs(override) else os.path.join(app_root, override.replace("/", os.sep))

    slug = (state_slug or "").strip().lower()

    filename = f"{slug}.json.gz"

    candidates = [

        os.path.join(_pbjapp_root(), "data", "geo", "derived", f"geo_intelligence_{slug}.json.gz"),

        os.path.join(_pbjapp_root(), DEFAULT_DIR.replace("/", os.sep), filename),

        os.path.join(app_root, DEFAULT_DIR.replace("/", os.sep), filename),

    ]

    for path in candidates:

        if os.path.isfile(path):

            return path

    return candidates[-1]





def _normalize_loaded_bundle(data: dict[str, Any]) -> dict[str, Any]:

    _ensure_pbjapp_path()

    try:

        from geo_intelligence.compat import normalize_bundle



        return normalize_bundle(data)

    except ImportError:

        return data





def load_bundle(app_root: str, state_slug: str) -> dict[str, Any] | None:

    path = bundle_path(app_root, state_slug)

    if not os.path.isfile(path):

        print(f"[geo_intelligence_bundle] bundle missing: {path}", flush=True)

        return None

    try:

        with gzip.open(path, "rt", encoding="utf-8") as fh:

            data = json.load(fh)

    except Exception as exc:

        print(f"[geo_intelligence_bundle] load failed {path}: {exc}", flush=True)

        return None

    if not isinstance(data, dict):

        return None

    version = int(data.get("version") or data.get("bundle_version") or 0)

    if version not in SUPPORTED_VERSIONS:

        print(f"[geo_intelligence_bundle] unsupported version {version!r}", flush=True)

        return None

    if version < 2:

        print("[geo_intelligence_bundle] warning: bundle v1 lacks coverage_by_quarter; rebuild recommended", flush=True)

    if version < 3:

        print("[geo_intelligence_bundle] warning: bundle v2 lacks metric_families; rebuild recommended", flush=True)

    return _normalize_loaded_bundle(data)





def inspect_bundle_status(app_root: str, state_slug: str) -> dict[str, Any]:

    path = bundle_path(app_root, state_slug)

    out: dict[str, Any] = {

        "bundle_path": path.replace("\\", "/"),

        "bundle_exists": os.path.isfile(path),

        "bundle_bytes": os.path.getsize(path) if os.path.isfile(path) else 0,

        "state_slug": state_slug,

    }

    if not out["bundle_exists"]:

        return out

    bundle = load_bundle(app_root, state_slug)

    if bundle:

        out["version"] = int(bundle.get("version") or bundle.get("bundle_version") or 0)

        out["canonical_quarter"] = bundle.get("canonical_quarter")

        out["quarters"] = bundle.get("quarters")

        out["state_code"] = bundle.get("state_code")

        out["default_metric_id"] = bundle.get("default_metric_id")

    return out


