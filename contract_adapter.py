#!/usr/bin/env python3
"""
Contract Adapter for pbj-contract (READ-ONLY, OBSERVATIONAL)

This module loads and exposes the shared contract in pbj-contract/ as a structured,
read-only object. It does NOT enforce behavior. Existing JSON/CSV guide files
remain authoritative until promoted. Enforcement will come later.

Usage:
    from contract_adapter import contract, run_passive_comparison

    # Read contract values (may be None if missing)
    label = contract.definitions.metric_labels.get("Total_Nurse_HPRD")

    # Optionally run observational comparison (logs warnings only)
    run_passive_comparison()
"""

import logging
import os
from types import SimpleNamespace
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------------------
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CONTRACT_DIR = os.path.join(_BASE_DIR, "pbj-contract")
_CONTRACT_FILES = [
    "definitions.yaml",
    "formatting.yaml",
    "quarter_rules.yaml",
    "disclaimers.yaml",
]
_VERSION_FILE = "VERSION"


def _load_yaml(path: str) -> Optional[dict]:
    """Load YAML file; return None and warn if missing or parse fails."""
    try:
        import yaml
    except ImportError:
        logger.warning(
            "[contract_adapter] PyYAML not installed. Install with: pip install PyYAML. "
            "Contract files will not be loaded."
        )
        return None

    if not os.path.isfile(path):
        logger.warning("[contract_adapter] Contract file not found: %s", path)
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning("[contract_adapter] Failed to parse %s: %s", path, e)
        return None


def _dict_to_namespace(d: Any) -> Any:
    """Convert dict to SimpleNamespace recursively for read-only access."""
    if d is None:
        return None
    if isinstance(d, dict):
        return SimpleNamespace(**{k: _dict_to_namespace(v) for k, v in d.items()})
    if isinstance(d, list):
        return [_dict_to_namespace(item) for item in d]
    return d


def _load_contract() -> SimpleNamespace:
    """Load all contract files and expose as read-only namespace."""
    result = SimpleNamespace(
        definitions=None,
        formatting=None,
        quarter_rules=None,
        disclaimers=None,
        version=None,
        _loaded=[],
    )

    for name in _CONTRACT_FILES:
        path = os.path.join(_CONTRACT_DIR, name)
        data = _load_yaml(path)
        if data is not None:
            key = name.replace(".yaml", "").replace("-", "_")
            setattr(result, key, _dict_to_namespace(data))
            result._loaded.append(name)
        else:
            setattr(result, name.replace(".yaml", "").replace("-", "_"), None)

    version_path = os.path.join(_CONTRACT_DIR, _VERSION_FILE)
    if os.path.isfile(version_path):
        try:
            with open(version_path, "r", encoding="utf-8") as f:
                result.version = f.read().strip().split("\n")[0]
            result._loaded.append(_VERSION_FILE)
        except Exception as e:
            logger.warning("[contract_adapter] Failed to read VERSION: %s", e)
            result.version = None
    else:
        logger.warning("[contract_adapter] VERSION file not found: %s", version_path)
        result.version = None

    return result


# Singleton read-only contract instance
contract = _load_contract()


# ------------------------------------------------------------------------------
# Proto-contract awareness (documentation only)
# ------------------------------------------------------------------------------
#
# The following files in pbj-root act as label dictionaries, ordering guides,
# formatting rules, boilerplate sources, or chart defaults. They remain
# authoritative until promoted to pbj-contract. This adapter does NOT modify them.
#
# | File Path                          | What it controls                  | Where consumed                | Overlap with pbj-contract          |
# |------------------------------------|-----------------------------------|-------------------------------|------------------------------------|
# | quarters_list.json                 | Quarter ordering, display format  | index.html                    | Yes (quarter_rules.yaml)           |
# | states_list.json                   | State list ordering               | index.html, generate_search   | No                                 |
# | latest_quarter_data.json           | Latest quarter, top states        | index.html, app.py api_dates  | Yes (quarter_rules, fallbacks)     |
# | macpac_state_standards_clean.csv   | State min/max HPRD, Display_Text  | app.py, pbj-wrapped           | Yes (definitions schema)           |
# | state_standards.json               | Same (derived)                    | app.py, dataLoader.ts         | Yes                                |
# | cms_region_state_mapping.csv       | State ↔ CMS region                | report.html, app.py, wrapped  | No                                 |
# | national_quarterly_metrics.csv     | Metric column names               | report.html, insights, gen    | Yes (definitions.metric_labels)    |
# | state_quarterly_metrics.csv        | Same + median columns             | report.html, insights         | Yes                                |
# | report.html (metricLabels, etc.)   | Metric labels, color thresholds   | report.html                   | Yes (definitions, formatting)      |
# | insights.html (stateAbbreviations) | State name ↔ abbr                 | insights.html                 | Partial (contract has no mapping)  |
# | index.html (stateAbbreviations)    | Same                              | index.html                    | Partial                            |
# | about.html                         | Methodology, HPRD explanation     | about.html                    | Yes (disclaimers)                  |
# | PBJPedia/*.md                      | Canonical definitions, caveats    | PBJPedia pages                | Yes (source for contract)          |
# | utils/seo_utils.py (STATE_ABBR_TO_NAME) | State abbr → full name       | app.py, templates             | Partial                            |
# | generate_search_index.py (STATE_*) | State name → abbr                 | generate_search_index         | Partial                            |
# | generate_dynamic_data_json.py (STATE_NAMES) | State abbr → full name    | generate_dynamic_data_json    | Partial                            |
# | pbj-wrapped/* (STATE_ABBR_TO_NAME) | Same, duplicated in many cards    | wrapped components            | Partial                            |
# | utils/date_utils.py                | Fallback dates, data range        | app.py, templates             | Yes (quarter_rules.fallbacks)      |
# | app.py (api_dates)                 | pbj_quarter_display, sff_posting  | SFF page, etc.                | Yes                                |
#


# ------------------------------------------------------------------------------
# Passive comparison (observational only)
# ------------------------------------------------------------------------------
#
# Known local presentation values at specific locations. When contract is present,
# compare and log warnings on divergence. Does NOT change behavior or reconcile.
#

_LOCAL_COMPARISON_POINTS = [
    {
        "location": "report.html (metricLabels, ~line 7293)",
        "local_value": {"Total_Nurse_HPRD": "Total Nurse HPRD", "Nurse_Assistant_HPRD": "Nurse Aide HPRD", "Contract_Percentage": "Contract Staff %"},
        "contract_path": ("definitions", "metric_labels"),
        "divergence_note": "report uses 'Contract Staff %' (with % suffix); contract has 'Contract Staff'. Could confuse users if other surfaces omit %.",
    },
    {
        "location": "report.html (getValueColor, ~line 6116)",
        "local_value": {"hprd_thresholds": [3.0, 3.5, 4.0, 4.5]},
        "contract_path": ("formatting", "color_thresholds", "hprd_high_good"),
        "extract_contract": lambda c: [c.light_red, c.yellow, c.light_green, c.green] if c else None,
        "divergence_note": "Map/table coloring relies on these thresholds. Drift could make green/red semantics inconsistent.",
    },
    {
        "location": "report.html (formatValue, ~line 6112)",
        "local_value": {"hprd_decimals": 2, "percent_decimals": 1},
        "contract_path": ("formatting", "decimals"),
        "extract_contract": lambda c: {"hprd": c.hprd, "percentage": c.percentage} if c else None,
        "divergence_note": "Rounding differences could produce inconsistent numbers across reports.",
    },
    {
        "location": "about.html (Methodology section)",
        "local_value": {"has_hprd_formula": True, "has_staffing_categories": True},
        "contract_path": ("disclaimers", "hprd_formula"),
        "divergence_note": "Methodology text in about.html should align with contract disclaimers for legal/journalistic consistency.",
        "informational_only": True,  # No direct comparison; both define methodology
    },
    {
        "location": "app.py / utils/date_utils.py (fallbacks)",
        "local_value": {"pbj_quarter_display": "Q3 2025", "sff_posting": "Jan. 2026"},
        "contract_path": ("quarter_rules", "fallbacks"),
        "extract_contract": lambda c: {"pbj_quarter_display": c.pbj_quarter_display, "sff_posting": c.sff_posting} if c else None,
        "divergence_note": "Date fallbacks used when JSON unavailable. Drift could show stale quarter or posting dates.",
    },
]


def _get_nested(obj: Any, path: tuple) -> Any:
    """Get nested attribute by path like ('formatting', 'decimals', 'hprd')."""
    for key in path:
        if obj is None:
            return None
        obj = getattr(obj, key, None)
    return obj


def _compare_and_warn(
    location: str,
    local_val: Any,
    contract_val: Any,
    divergence_note: str,
) -> None:
    """Compare local vs contract; log warning if divergent."""
    if contract_val is None:
        return  # Contract silent; no comparison
    if local_val == contract_val:
        return
    logger.warning(
        "[contract_adapter] DIVERGENCE at %s: local=%s, contract=%s. %s",
        location,
        local_val,
        contract_val,
        divergence_note,
    )


def run_passive_comparison() -> None:
    """
    Compare known local presentation behavior to pbj-contract (or proto-contract).

    Logs WARNINGs only when divergence is detected. Does NOT change behavior,
    reconcile differences, or pick a winner. Call optionally at startup or on demand.
    """
    for point in _LOCAL_COMPARISON_POINTS:
        location = point["location"]
        local_value = point["local_value"]
        contract_path = point["contract_path"]
        divergence_note = point.get("divergence_note", "May cause inconsistent presentation.")

        # 1. Metric labels (report.html metricLabels vs definitions.metric_labels)
        if "metric_labels" in str(contract_path) and contract.definitions:
            contract_labels = getattr(contract.definitions, "metric_labels", None)
            if contract_labels:
                for key, local_label in local_value.items():
                    attr_name = key.replace(".", "_")
                    c_label = getattr(contract_labels, attr_name, None)
                    if c_label is not None and local_label != c_label:
                        _compare_and_warn(
                            location, {key: local_label}, {key: c_label},
                            divergence_note,
                        )
            continue

        # 2. Decimals (report.html formatValue vs formatting.decimals)
        if "decimals" in str(contract_path) and contract.formatting:
            decimals = getattr(contract.formatting, "decimals", None)
            if decimals:
                if local_value.get("hprd_decimals") is not None:
                    c_hprd = getattr(decimals, "hprd", None)
                    if c_hprd is not None and local_value["hprd_decimals"] != c_hprd:
                        _compare_and_warn(location, local_value, {"hprd": c_hprd}, divergence_note)
                if local_value.get("percent_decimals") is not None:
                    c_pct = getattr(decimals, "percentage", None)
                    if c_pct is not None and local_value["percent_decimals"] != c_pct:
                        _compare_and_warn(location, local_value, {"percentage": c_pct}, divergence_note)
            continue

        # 3. Color thresholds (report.html getValueColor vs formatting.color_thresholds)
        if "color_thresholds" in str(contract_path) and contract.formatting:
            c_thresh = _get_nested(contract, ("formatting", "color_thresholds", "hprd_high_good"))
            if c_thresh and "hprd_thresholds" in local_value:
                c_list = [
                    getattr(c_thresh, "light_red", 3.0),
                    getattr(c_thresh, "yellow", 3.5),
                    getattr(c_thresh, "light_green", 4.0),
                    getattr(c_thresh, "green", 4.5),
                ]
                local_list = local_value["hprd_thresholds"]
                if sorted(local_list) != sorted(c_list):
                    _compare_and_warn(location, local_value, {"contract": c_list}, divergence_note)
            continue

        # 4. Fallbacks (app.py / date_utils vs quarter_rules.fallbacks)
        if "fallbacks" in str(contract_path) and contract.quarter_rules:
            fallbacks = getattr(contract.quarter_rules, "fallbacks", None)
            if fallbacks:
                for k in ("pbj_quarter_display", "sff_posting"):
                    lv = local_value.get(k)
                    cv = getattr(fallbacks, k, None)
                    if lv is not None and cv is not None and lv != cv:
                        _compare_and_warn(location, {k: lv}, {k: cv}, divergence_note)
            continue

        # 5. Informational points (e.g., about.html) - no direct comparison
        if point.get("informational_only"):
            continue

        # 6. Other
        contract_val = _get_nested(contract, contract_path)
        extract = point.get("extract_contract")
        if extract and contract_val is not None:
            contract_val = extract(contract_val)
        if contract_val is not None:
            _compare_and_warn(location, local_value, contract_val, divergence_note)
