"""
Facility map preparation for owner profiles (not yet rendered on site).

Gathers coordinates from enriched facility rows, classifies geographic scope,
and decides whether a future map widget should show (desktop-only, scope-aware).
"""
from __future__ import annotations

import json
import math
from typing import Any

# Minimum facilities before map UI is considered (future).
FACILITY_MAP_MIN_FACILITIES = 5

# Minimum geocoded points required to draw anything meaningful.
FACILITY_MAP_MIN_COORDINATES = 2

# Future: only render map at this viewport width and above (see owner-profile.css).
FACILITY_MAP_DESKTOP_MIN_PX = 900


def _parse_coord(value: Any) -> float | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in ("nan", "none", "—", "-"):
        return None
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    return v


def facility_coordinates(fac: dict[str, Any]) -> tuple[float, float] | None:
    """Return (lat, lon) when both are present and in US bounds."""
    lat = _parse_coord(fac.get("latitude"))
    lon = _parse_coord(fac.get("longitude"))
    if lat is None or lon is None:
        return None
    if not (24.0 <= lat <= 50.0 and -125.0 <= lon <= -66.0):
        return None
    return lat, lon


def gather_facility_map_points(
    facilities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Normalized map markers from enriched facilities (no external geocoding)."""
    points: list[dict[str, Any]] = []
    for fac in facilities:
        coords = facility_coordinates(fac)
        if not coords:
            continue
        lat, lon = coords
        ccn = str(fac.get("ccn") or "").strip().zfill(6)[-6:]
        label = str(fac.get("provider_name") or fac.get("facility_name") or "").strip()
        points.append(
            {
                "ccn": ccn,
                "label": label,
                "state": str(fac.get("state") or "").strip().upper()[:2],
                "city": str(fac.get("city") or "").strip(),
                "latitude": lat,
                "longitude": lon,
            }
        )
    return points


def classify_geographic_scope(
    facilities: list[dict[str, Any]],
    *,
    points: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Infer how a future map should be framed.

    Returns scope hints: single_state (e.g. all NY), multi_state_regional,
    national, plus spread metrics for bounding-box zoom.
    """
    states = sorted(
        {
            str(f.get("state") or "").strip().upper()[:2]
            for f in facilities
            if str(f.get("state") or "").strip()
        }
    )
    pts = points if points is not None else gather_facility_map_points(facilities)
    n_fac = len(facilities)
    n_geo = len(pts)

    if not states and not pts:
        return {
            "scope": "unknown",
            "recommended_map": "none",
            "primary_state": "",
            "state_codes": [],
            "n_facilities": n_fac,
            "n_with_coordinates": n_geo,
            "bounds": None,
            "spread_miles_approx": None,
        }

    primary_state = states[0] if len(states) == 1 else ""
    if len(states) == 1:
        scope = "single_state"
        recommended = "state"
    elif len(states) <= 3:
        scope = "multi_state_regional"
        recommended = "regional"
    else:
        scope = "national"
        recommended = "us"

    bounds = None
    spread_mi = None
    if pts:
        lats = [p["latitude"] for p in pts]
        lons = [p["longitude"] for p in pts]
        bounds = {
            "min_lat": min(lats),
            "max_lat": max(lats),
            "min_lon": min(lons),
            "max_lon": max(lons),
        }
        mid_lat = (bounds["min_lat"] + bounds["max_lat"]) / 2.0
        dlat_mi = abs(bounds["max_lat"] - bounds["min_lat"]) * 69.0
        dlon_mi = (
            abs(bounds["max_lon"] - bounds["min_lon"])
            * 69.0
            * max(0.2, math.cos(math.radians(mid_lat)))
        )
        spread_mi = max(dlat_mi, dlon_mi)
        if spread_mi < 45 and scope == "national":
            recommended = "regional"
        if spread_mi < 12 and len(states) == 1:
            recommended = "metro"
        if spread_mi < 6 and len(states) == 1:
            recommended = "city"

    return {
        "scope": scope,
        "recommended_map": recommended,
        "primary_state": primary_state,
        "state_codes": states,
        "n_facilities": n_fac,
        "n_with_coordinates": n_geo,
        "bounds": bounds,
        "spread_miles_approx": round(spread_mi, 1) if spread_mi is not None else None,
    }


def should_prepare_facility_map(facilities: list[dict[str, Any]]) -> bool:
    """Whether we have enough data to eventually show a portfolio map."""
    if len(facilities) < FACILITY_MAP_MIN_FACILITIES:
        return False
    pts = gather_facility_map_points(facilities)
    return len(pts) >= FACILITY_MAP_MIN_COORDINATES


def build_facility_map_context(facilities: list[dict[str, Any]]) -> dict[str, Any]:
    """Attachable profile context for a future map widget (no map library yet)."""
    points = gather_facility_map_points(facilities)
    geo = classify_geographic_scope(facilities, points=points)
    ready = should_prepare_facility_map(facilities)
    return {
        "ready": ready,
        "show_placeholder": ready,
        "desktop_only": True,
        "min_facilities": FACILITY_MAP_MIN_FACILITIES,
        "min_coordinates": FACILITY_MAP_MIN_COORDINATES,
        "geography": geo,
        "points": points,
        "points_json": json.dumps(points, separators=(",", ":")),
        "geography_json": json.dumps(geo, separators=(",", ":")),
    }


def attach_facility_map_context(profile: dict[str, Any]) -> dict[str, Any]:
    """Add facility_map block to owner profile after facilities are enriched."""
    facilities = list(profile.get("facilities") or [])
    profile["facility_map"] = build_facility_map_context(facilities)
    ow = profile.get("owner_control_section")
    if isinstance(ow, dict) and ow.get("facilities"):
        ow["facility_map"] = build_facility_map_context(list(ow["facilities"]))
    return profile
