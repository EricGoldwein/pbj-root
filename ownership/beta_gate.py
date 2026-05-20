"""Ownership / CHOW visibility: Connecticut public launch, broader states for internal preview.

Published externally (production default):
  - State-page ownership blocks, provider ownership sections, and /owners/<pac> profiles
    for facilities and organizations tied to Connecticut (CT).

Internal preview (local dev or explicit env / admin key):
  - Same UI for additional states (e.g. Minnesota) without treating them as published.

Environment:
  PBJ_OWNERSHIP_PREVIEW=1|all|on     — enable preview (all states with data when no list set)
  PBJ_OWNERSHIP_PREVIEW_STATES=MN,WI — optional comma-separated USPS codes (still includes CT)

On non-Render hosts, app.py setdefaults PBJ_OWNERSHIP_PREVIEW=1 so local runs see all states.

Optional request bypass (staging): ?ownership_preview=1&key=<ADMIN_VIEW_KEY>
"""
from __future__ import annotations

import os
from typing import Any

OWNERSHIP_PUBLIC_STATES = frozenset({"CT"})
# Back-compat alias
OWNERSHIP_BETA_STATE = "CT"


def normalize_state_code(state_code: str | None) -> str:
    return (state_code or "").strip().upper()[:2]


def _preview_env_enabled() -> bool:
    raw = (os.environ.get("PBJ_OWNERSHIP_PREVIEW") or "").strip().lower()
    return raw in ("1", "true", "yes", "on", "all", "*")


def _preview_state_allowlist() -> frozenset[str] | None:
    """None means all states allowed when preview is on; empty frozenset means CT + env list only."""
    raw = (os.environ.get("PBJ_OWNERSHIP_PREVIEW_STATES") or "").strip().upper()
    if not raw:
        return None
    codes = frozenset(
        normalize_state_code(part)
        for part in raw.replace(";", ",").split(",")
        if normalize_state_code(part)
    )
    return codes | OWNERSHIP_PUBLIC_STATES if codes else None


def _request_preview_enabled() -> bool:
    try:
        from flask import has_request_context, request
    except ImportError:
        return False
    if not has_request_context():
        return False
    admin_key = (os.environ.get("ADMIN_VIEW_KEY") or "").strip()
    if not admin_key:
        return False
    supplied = (
        (request.args.get("ownership_preview_key") or "").strip()
        or (request.args.get("key") or "").strip()
        or (request.cookies.get("pbj_ownership_preview") or "").strip()
    )
    if request.args.get("ownership_preview") in ("1", "true", "yes") and supplied == admin_key:
        return True
    return supplied == admin_key and request.args.get("ownership_preview") is not None


def ownership_preview_enabled() -> bool:
    return _preview_env_enabled() or _request_preview_enabled()


def ownership_public_enabled_for_state(state_code: str | None) -> bool:
    return normalize_state_code(state_code) in OWNERSHIP_PUBLIC_STATES


def ownership_visible_for_state(state_code: str | None) -> bool:
    st = normalize_state_code(state_code)
    if not st:
        return False
    if ownership_public_enabled_for_state(st):
        return True
    if not ownership_preview_enabled():
        return False
    allow = _preview_state_allowlist()
    if allow is None:
        return True
    return st in allow


def ownership_beta_enabled_for_state(state_code: str | None) -> bool:
    """Whether ownership UI and /owners/<pac> are available for this state (public + preview)."""
    return ownership_visible_for_state(state_code)


def _profile_state_codes(profile: dict[str, Any] | None) -> list[str]:
    if not profile:
        return []
    states = profile.get("states") or []
    if states:
        return [normalize_state_code(s) for s in states if normalize_state_code(s)]
    by_state = (profile.get("portfolio_summary") or {}).get("by_state") or []
    return [normalize_state_code(st) for st, _ in by_state if normalize_state_code(st)]


def profile_has_public_state(profile: dict[str, Any] | None) -> bool:
    return any(ownership_public_enabled_for_state(s) for s in _profile_state_codes(profile))


def profile_is_visible(profile: dict[str, Any] | None) -> bool:
    codes = _profile_state_codes(profile)
    if not codes:
        return False
    return any(ownership_visible_for_state(s) for s in codes)


def profile_has_beta_state(profile: dict[str, Any] | None) -> bool:
    """Back-compat: True when profile should be reachable (not 404)."""
    return profile_is_visible(profile)
