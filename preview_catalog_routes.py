"""Central PBJ-ready facility preview catalog routes (PoC)."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any

from flask import abort, render_template, send_file

if TYPE_CHECKING:
    from flask import Flask, Response

try:
    from jinja2 import ChoiceLoader, FileSystemLoader
except ImportError:  # pragma: no cover
    ChoiceLoader = None  # type: ignore[misc, assignment]
    FileSystemLoader = None  # type: ignore[misc, assignment]

_CCN_RE = re.compile(r"^\d{6}$")
_PUBLIC_ROW_KEYS = frozenset(
    {
        "ccn",
        "legal_name",
        "display_name",
        "compact_name",
        "city",
        "state",
        "county",
        "entity_id",
        "entity_name",
        "ownership_type",
        "provider_page_url",
        "entity_page_url",
        "care_compare_url",
    }
)


def _catalog_dir(app_root: str) -> Path:
    override = (os.environ.get("PBJ_PREVIEW_CATALOG_DIR") or "").strip()
    if override:
        return Path(override)
    return Path(app_root) / "data" / "preview_catalog" / "poc"


def _sqlite_path(app_root: str) -> Path:
    override = (os.environ.get("PBJ_PREVIEW_CATALOG_SQLITE") or "").strip()
    if override:
        return Path(override)
    return _catalog_dir(app_root) / "preview_catalog_poc.sqlite"


def _global_config_path(app_root: str) -> Path:
    override = (os.environ.get("PBJ_PREVIEW_GLOBAL_CONFIG") or "").strip()
    if override:
        return Path(override)
    return _catalog_dir(app_root) / "preview_global_v1.json"


def load_global_config(app_root: str) -> dict[str, Any]:
    path = _global_config_path(app_root)
    if not path.is_file():
        abort(503)
    return json.loads(path.read_text(encoding="utf-8"))


def load_public_facility_row(app_root: str, ccn: str) -> dict[str, str] | None:
    path = _sqlite_path(app_root)
    if not path.is_file():
        abort(503)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            """
            SELECT ccn, legal_name, display_name, compact_name, city, state, county,
                   entity_id, entity_name, ownership_type,
                   provider_page_url, entity_page_url, care_compare_url
            FROM preview_facilities WHERE ccn = ?
            """,
            (ccn,),
        )
        row = cur.fetchone()
        if not row:
            return None
        keys = (
            "ccn",
            "legal_name",
            "display_name",
            "compact_name",
            "city",
            "state",
            "county",
            "entity_id",
            "entity_name",
            "ownership_type",
            "provider_page_url",
            "entity_page_url",
            "care_compare_url",
        )
        out = dict(zip(keys, row))
        cleaned = {k: ("" if v is None else str(v)) for k, v in out.items()}
        return _sanitize_facility_row(cleaned)
    finally:
        conn.close()


def _clean_public_text(val: object) -> str:
    if val is None:
        return ""
    text = str(val).strip()
    if text.lower() in ("", "nan", "none", "null", "<na>"):
        return ""
    return text


def _sanitize_facility_row(row: dict[str, str]) -> dict[str, str]:
    out = {k: _clean_public_text(v) for k, v in row.items()}
    if not out.get("entity_name") or not out.get("entity_id"):
        out["entity_name"] = ""
        out["entity_id"] = ""
        out["entity_page_url"] = ""
    return out


def _cta_href(global_config: dict[str, Any], ccn: str) -> str:
    cta = global_config.get("cta") or {}
    template = str(cta.get("href_template") or "/premium?open=premium&ccn={ccn}")
    return template.replace("{ccn}", ccn)


def _cta_label(global_config: dict[str, Any], display_name: str) -> str:
    cta = global_config.get("cta") or {}
    template = str(cta.get("label") or "Request the full facility dashboard")
    if "{facility_name}" in template:
        return template.replace("{facility_name}", display_name)
    if display_name and "facility dashboard" in template.lower():
        return template.replace("facility dashboard", f"{display_name} dashboard", 1)
    return f"Request the full {display_name} dashboard"


def _configure_preview_template_loader(app: Flask, app_root: str) -> None:
    """Load central preview shell from pbj-root + canonical Superdynamic partials from PBJapp."""
    if ChoiceLoader is None or FileSystemLoader is None:
        return
    pbjapp_templates = Path(app_root).resolve().parent / "PBJapp" / "templates"
    if not pbjapp_templates.is_dir():
        return
    app.jinja_loader = ChoiceLoader(
        [
            FileSystemLoader(str(Path(app_root) / "templates")),
            FileSystemLoader(str(pbjapp_templates)),
        ]
    )


def register_preview_catalog_routes(app: Flask, app_root: str) -> None:
    """Register GET /preview/<ccn> for PBJ-ready eligible facilities only."""
    _configure_preview_template_loader(app, app_root)

    @app.route("/preview-central-overrides.css")
    def preview_central_overrides_css():
        css_path = Path(app_root) / "static" / "preview_central_overrides.css"
        if not css_path.is_file():
            abort(404)
        return send_file(css_path, mimetype="text/css")

    @app.route("/preview-superdynamic-layout.css")
    def preview_superdynamic_layout_css():
        css_path = Path(app_root) / "static" / "preview_superdynamic_layout.css"
        if not css_path.is_file():
            abort(404)
        return send_file(css_path, mimetype="text/css")

    @app.route("/preview-superdynamic-core.css")
    def preview_superdynamic_core_css():
        css_path = Path(app_root) / "static" / "preview_superdynamic_core.css"
        if not css_path.is_file():
            abort(404)
        return send_file(css_path, mimetype="text/css")

    @app.route("/preview-access.js")
    def preview_access_js():
        js_path = Path(app_root) / "static" / "preview_access.js"
        if not js_path.is_file():
            abort(404)
        return send_file(js_path, mimetype="application/javascript")

    @app.route("/preview-dashboard.css")
    def preview_dashboard_css():
        css_path = Path(app_root) / "static" / "preview_dashboard.css"
        if not css_path.is_file():
            abort(404)
        return send_file(css_path, mimetype="text/css")

    @app.route("/preview/<ccn>")
    def preview_facility_page(ccn: str) -> Response | str:
        prov = str(ccn or "").strip()
        if not _CCN_RE.fullmatch(prov):
            abort(404)
        row = load_public_facility_row(app_root, prov)
        if not row:
            abort(404)
        global_config = load_global_config(app_root)
        cta = global_config.get("cta") or {}
        display_name = row.get("display_name") or row.get("legal_name") or prov
        context = {
            "facility": {k: row[k] for k in _PUBLIC_ROW_KEYS if k in row},
            "preview_status_label": global_config.get("preview_status_label"),
            "preview_locked_copy": global_config.get("preview_locked_copy"),
            "preview_pod_explainer": global_config.get("preview_pod_explainer")
            or "Staffing metrics, benchmarks, and compliance findings are available in the full facility dashboard with authorized access.",
            "preview_hprd_lock_message": global_config.get("preview_hprd_lock_message"),
            "universal_modules": global_config.get("universal_modules") or [],
            "optional_modules": global_config.get("optional_modules") or [],
            "optional_modules_disclaimer": global_config.get("optional_modules_disclaimer"),
            "static_period_label": global_config.get("static_period_label") or "2025",
            "static_years": global_config.get("static_years") or ["2025", "2024", "2023", "2022", "2021"],
            "provider_roster_label": global_config.get("provider_roster_label") or "2026-06",
            "cta_label": _cta_label(global_config, display_name),
            "preview_cta_label": _cta_label(global_config, display_name),
            "cta_href": _cta_href(global_config, prov),
            "cta_new_tab": bool(cta.get("new_tab")),
        }
        extra = set(context["facility"]) - _PUBLIC_ROW_KEYS
        if extra:
            abort(500)
        return render_template("preview_superdynamic_shell.html", **context)
