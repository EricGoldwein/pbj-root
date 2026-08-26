"""Fetch official CMS machine-readable metadata only (no webpage scrape, no dataset download)."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Callable
from urllib.parse import urlparse

from .registry import CmsSource

METASTORE_ITEM_TMPL = (
    "https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/{dataset_id}"
)
DATA_JSON_URL = "https://data.cms.gov/data.json"

_USER_AGENT = "PBJ320-cms-release-watcher/1.0 (+https://www.pbj320.com; read-only metadata)"


@dataclass(frozen=True)
class CmsObservedState:
    source_id: str
    title: str
    stable_key: str
    catalog: str
    released: str | None
    modified: str | None
    next_update_date: str | None
    temporal: str | None
    distribution_filename: str | None
    distribution_url: str | None
    distribution_identifier: str | None
    data_vintage_label: str | None
    raw_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


Fetcher = Callable[[str, dict[str, str] | None], Any]


def _default_fetch_json(url: str, headers: dict[str, str] | None = None) -> Any:
    req_headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.load(resp)


def _basename_from_url(url: str | None) -> str | None:
    if not url:
        return None
    path = urlparse(url).path
    name = path.rsplit("/", 1)[-1].strip()
    return name or None


def _vintage_from_filename(name: str | None) -> str | None:
    if not name:
        return None
    # NH_ProviderInfo_Aug2026.csv
    m = re.search(r"NH_ProviderInfo_([A-Za-z]{3})(\d{4})", name, re.I)
    if m:
        return f"{m.group(1).title()} {m.group(2)}"
    # ProviderInfoNorm not expected from CMS current CSV but keep pattern
    m = re.search(r"ProviderInfoNorm_(\d{4})_(\d{2})", name, re.I)
    if m:
        months = [
            "",
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]
        mo = int(m.group(2))
        if 1 <= mo <= 12:
            return f"{months[mo]} {m.group(1)}"
    # PBJ_dailynursestaffing_CY2026Q1.csv
    m = re.search(r"CY(\d{4})Q([1-4])", name, re.I)
    if m:
        return f"{m.group(1)}Q{m.group(2)}"
    # SNF_All_Owners_2026.07.31.csv / SNF_Enrollments_2026.07.31.csv / SNF_CHOW_2026.07.17.csv
    m = re.search(r"(20\d{2})[._-](\d{2})[._-](\d{2})", name)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # Chain_Performance_20260812.csv
    m = re.search(r"Chain_Performance_(\d{4})(\d{2})(\d{2})", name, re.I)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # Nursing_Home_Chain_Performance_Measures_Jun_2026.csv
    m = re.search(r"Performance_Measures_([A-Za-z]{3})_(\d{4})", name, re.I)
    if m:
        return f"{m.group(1).title()} {m.group(2)}"
    return None


def _fingerprint(
    *,
    stable_key: str,
    modified: str | None,
    released: str | None,
    filename: str | None,
    url: str | None,
) -> str:
    return "|".join(
        [
            stable_key,
            released or "",
            modified or "",
            filename or "",
            url or "",
        ]
    )


def fetch_provider_data_metastore(
    source: CmsSource,
    fetch_json: Fetcher | None = None,
) -> CmsObservedState:
    fetch = fetch_json or _default_fetch_json
    url = METASTORE_ITEM_TMPL.format(dataset_id=source.stable_key)
    try:
        payload = fetch(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"metastore fetch failed for {source.source_id}: {exc}") from exc

    released = payload.get("released")
    modified = payload.get("modified")
    next_update = payload.get("nextUpdateDate")
    temporal = payload.get("temporal")

    dist_url = None
    dist_id = None
    filename = None
    distributions = payload.get("distribution") or []
    if distributions:
        # Metastore wraps distribution as {"identifier": ..., "data": {...}}
        first = distributions[0]
        data = first.get("data") if isinstance(first, dict) and "data" in first else first
        if isinstance(data, dict):
            dist_url = data.get("downloadURL") or data.get("accessURL")
            dist_id = first.get("identifier") if isinstance(first, dict) else None
            filename = _basename_from_url(dist_url)

    vintage = _vintage_from_filename(filename)
    fp = _fingerprint(
        stable_key=source.stable_key,
        modified=str(modified) if modified else None,
        released=str(released) if released else None,
        filename=filename,
        url=dist_url,
    )
    return CmsObservedState(
        source_id=source.source_id,
        title=source.title,
        stable_key=source.stable_key,
        catalog=source.catalog,
        released=str(released) if released else None,
        modified=str(modified) if modified else None,
        next_update_date=str(next_update) if next_update else None,
        temporal=str(temporal) if temporal else None,
        distribution_filename=filename,
        distribution_url=dist_url,
        distribution_identifier=str(dist_id) if dist_id else None,
        data_vintage_label=vintage,
        raw_fingerprint=fp,
    )


def _pick_current_csv_distribution(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Prefer newest CSV downloadURL; fall back to first distribution with a URL."""
    dists = entry.get("distribution") or []
    csv_dists: list[dict[str, Any]] = []
    for dist in dists:
        if not isinstance(dist, dict):
            continue
        url = dist.get("downloadURL") or ""
        if url.lower().endswith(".csv"):
            csv_dists.append(dist)
    if csv_dists:
        # data.json lists current/newest CSV first for these CMS datasets.
        return csv_dists[0]
    for dist in dists:
        if isinstance(dist, dict) and (dist.get("downloadURL") or dist.get("accessURL")):
            return dist
    return None


def fetch_from_data_json(
    source: CmsSource,
    fetch_json: Fetcher | None = None,
    catalog_cache: dict[str, Any] | None = None,
) -> CmsObservedState:
    fetch = fetch_json or _default_fetch_json
    try:
        if catalog_cache is not None and "dataset" in catalog_cache:
            catalog = catalog_cache
        else:
            catalog = fetch(DATA_JSON_URL)
            if catalog_cache is not None:
                catalog_cache.clear()
                catalog_cache.update(catalog)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"data.json fetch failed for {source.source_id}: {exc}") from exc

    title = source.data_json_title or source.title
    entry = None
    for item in catalog.get("dataset") or []:
        if not isinstance(item, dict):
            continue
        ident = str(item.get("identifier") or "")
        if source.stable_key and source.stable_key in ident:
            entry = item
            break
        if item.get("title") == title:
            entry = item
            break
    if entry is None:
        raise RuntimeError(f"dataset not found in data.json: {source.source_id} ({title})")

    modified = entry.get("modified")
    released = entry.get("issued") or entry.get("released")
    temporal = entry.get("temporal")
    dist = _pick_current_csv_distribution(entry) or {}
    dist_url = dist.get("downloadURL") or dist.get("accessURL")
    filename = _basename_from_url(dist_url)
    # Prefer distribution-level temporal/modified when present
    if dist.get("temporal"):
        temporal = dist.get("temporal")
    if dist.get("modified") and not modified:
        modified = dist.get("modified")

    vintage = _vintage_from_filename(filename)
    if not vintage and temporal:
        # Use temporal end as coverage vintage hint, e.g. 2017-01-01/2026-03-31 → 2026-03-31
        m = re.search(r"/(\d{4}-\d{2}-\d{2})$", str(temporal))
        if m:
            vintage = m.group(1)

    fp = _fingerprint(
        stable_key=source.stable_key,
        modified=str(modified) if modified else None,
        released=str(released) if released else None,
        filename=filename,
        url=dist_url,
    )
    return CmsObservedState(
        source_id=source.source_id,
        title=source.title,
        stable_key=source.stable_key,
        catalog=source.catalog,
        released=str(released) if released else None,
        modified=str(modified) if modified else None,
        next_update_date=None,  # data.json entries typically omit nextUpdateDate
        temporal=str(temporal) if temporal else None,
        distribution_filename=filename,
        distribution_url=dist_url,
        distribution_identifier=None,
        data_vintage_label=vintage,
        raw_fingerprint=fp,
    )


def fetch_cms_state(
    source: CmsSource,
    fetch_json: Fetcher | None = None,
    catalog_cache: dict[str, Any] | None = None,
) -> CmsObservedState:
    if source.catalog == "provider_data_metastore":
        return fetch_provider_data_metastore(source, fetch_json=fetch_json)
    if source.catalog == "cms_data_json":
        return fetch_from_data_json(source, fetch_json=fetch_json, catalog_cache=catalog_cache)
    raise ValueError(f"unsupported catalog kind: {source.catalog}")
