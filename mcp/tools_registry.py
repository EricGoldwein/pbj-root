"""Read-only MCP tool registry for PBJ320 public research API."""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from pbj_public_query.evidence import get_staffing_evidence
from pbj_public_query.facility import compare_facilities, get_facility_record, normalize_ccn_input, search_facilities
from pbj_public_query.owner import get_owner_portfolio, search_owners
from pbj_public_query.provenance import attach_citation_envelope

ToolFn = Callable[[dict[str, Any]], dict[str, Any]]

_CCN_RE = re.compile(r"^[A-Z0-9]{6}$")
_PAC_RE = re.compile(r"^\d{10}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _err(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": code, "message": message}


def _tool_search_facilities(args: dict[str, Any]) -> dict[str, Any]:
    result = search_facilities(
        query=str(args.get("query") or args.get("name") or ""),
        ccn=args.get("ccn"),
        city=args.get("city"),
        state=args.get("state"),
        zip_code=args.get("zip"),
        owner_pac=args.get("owner_pac") or args.get("pac"),
        limit=args.get("limit"),
    )
    q = result.get("period", {}).get("quarter")
    return attach_citation_envelope(
        {"ok": True, **result},
        quarter=q,
        methodology_url="/data-sources",
    )


def _validate_ccn_arg(raw: str) -> tuple[str, dict[str, Any] | None]:
    core = str(raw or "").strip().upper().split(".")[0]
    if len(core) < 4 or not re.fullmatch(r"[A-Z0-9]{4,6}", core):
        return "", _err("invalid_ccn", "CCN must be a 6-character CMS certification number")
    ccn = normalize_ccn_input(core)
    if not ccn or not _CCN_RE.match(ccn):
        return "", _err("invalid_ccn", "CCN must be a 6-character CMS certification number")
    return ccn, None


def _tool_get_facility(args: dict[str, Any]) -> dict[str, Any]:
    ccn, err = _validate_ccn_arg(str(args.get("ccn") or ""))
    if err:
        return err
    rec = get_facility_record(ccn)
    if not rec:
        return _err("not_found", f"No facility data for CCN {ccn}")
    return attach_citation_envelope(
        {"ok": True, **rec},
        canonical_url=rec.get("canonical_url", ""),
        quarter=(rec.get("period") or {}).get("quarter"),
        methodology_url="/data-sources#methodology",
    )


def _tool_compare_facilities(args: dict[str, Any]) -> dict[str, Any]:
    raw = args.get("ccns") or args.get("facilities") or []
    if isinstance(raw, str):
        raw = [x.strip() for x in raw.split(",") if x.strip()]
    if not isinstance(raw, list) or not raw:
        return _err("invalid_input", "Provide ccns as a list of CMS certification numbers")
    if len(raw) > 10:
        raw = raw[:10]
    for c in raw:
        prov, err = _validate_ccn_arg(str(c))
        if err:
            return err
    result = compare_facilities([str(c) for c in raw])
    return attach_citation_envelope(
        {"ok": True, **result},
        quarter=(result.get("period") or {}).get("quarter"),
        methodology_url="/data-sources#methodology",
    )


def _tool_search_owners(args: dict[str, Any]) -> dict[str, Any]:
    q = str(args.get("query") or args.get("name") or args.get("pac") or "")
    result = search_owners(query=q, state=args.get("state"), limit=args.get("limit"))
    return attach_citation_envelope(
        {"ok": True, **result},
        methodology_url="/data-sources#ownership",
        ownership_release=result.get("ownership_release"),
    )


def _tool_get_owner_portfolio(args: dict[str, Any]) -> dict[str, Any]:
    from ownership.owner_profile import normalize_associate_id

    pac = normalize_associate_id(str(args.get("pac") or args.get("associate_id") or ""))
    if not pac or not _PAC_RE.match(pac):
        return _err("invalid_pac", "PAC must be a 10-digit CMS associate ID")
    result = get_owner_portfolio(pac)
    if not result:
        return _err("not_found", f"No owner portfolio for PAC {pac}")
    return attach_citation_envelope(
        {"ok": True, **result},
        canonical_url=result.get("canonical_url", ""),
        ownership_release=result.get("ownership_release"),
        methodology_url="/data-sources#ownership",
    )


def _tool_get_staffing_evidence(args: dict[str, Any]) -> dict[str, Any]:
    # Strict single-day bound: reject range / bulk extraction keys if present.
    forbidden = (
        "start_date",
        "end_date",
        "date_from",
        "date_to",
        "from",
        "to",
        "days",
        "all_days",
        "offset",
        "page",
        "cursor",
        "limit",
    )
    for key in forbidden:
        if key in args and args.get(key) not in (None, "", [], {}):
            return _err(
                "extraction_not_allowed",
                "get_staffing_evidence is bounded to one CCN + one date + one metric; "
                f"argument '{key}' is not supported.",
            )
    ccn, err = _validate_ccn_arg(str(args.get("ccn") or ""))
    if err:
        return err
    date = str(args.get("date") or args.get("work_date") or "").strip()
    if not _DATE_RE.match(date):
        return _err("invalid_date", "date must be ISO YYYY-MM-DD")
    metric = str(args.get("metric") or "RN_HPRD").strip()
    period = args.get("period") or args.get("quarter")
    result = get_staffing_evidence(ccn, date, metric, period=period)
    if not result:
        return _err("not_found", f"No day evidence for CCN {ccn} on {date} ({metric})")
    if result.get("ok") is False:
        return result
    return {"ok": True, **result}


TOOLS: dict[str, dict[str, Any]] = {
    "search_facilities": {
        "description": "Search nursing homes by name, CCN, city, state, ZIP, or owner PAC.",
        "handler": _tool_search_facilities,
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "ccn": {"type": "string"},
                "city": {"type": "string"},
                "state": {"type": "string"},
                "zip": {"type": "string"},
                "owner_pac": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 60, "default": 20},
            },
        },
    },
    "get_facility": {
        "description": "Structured facility profile with latest quarterly staffing, CMS context, and canonical URL.",
        "handler": _tool_get_facility,
        "inputSchema": {
            "type": "object",
            "properties": {"ccn": {"type": "string"}},
            "required": ["ccn"],
        },
    },
    "compare_facilities": {
        "description": "Compare explicit CCNs using canonical quarterly metrics; includes state percentile context when available.",
        "handler": _tool_compare_facilities,
        "inputSchema": {
            "type": "object",
            "properties": {
                "ccns": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 10},
            },
            "required": ["ccns"],
        },
    },
    "search_owners": {
        "description": "Search CMS SNF owner records by name or 10-digit PAC.",
        "handler": _tool_search_owners,
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "state": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 60, "default": 20},
            },
        },
    },
    "get_owner_portfolio": {
        "description": "Facilities attributable to a PAC under PBJ320 ownership methodology and active release policy.",
        "handler": _tool_get_owner_portfolio,
        "inputSchema": {
            "type": "object",
            "properties": {"pac": {"type": "string"}},
            "required": ["pac"],
        },
    },
    "get_staffing_evidence": {
        "description": (
            "Audit-ready CMS PBJ daily staffing evidence for exactly one facility, "
            "one ISO date, and one metric. Not a bulk daily export API. Optional period "
            "(e.g. CY2026Q1) must match a loaded evidence quarter or returns "
            "evidence_unavailable_for_period (never substitutes another quarter)."
        ),
        "handler": _tool_get_staffing_evidence,
        "inputSchema": {
            "type": "object",
            "properties": {
                "ccn": {"type": "string"},
                "date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "metric": {
                    "type": "string",
                    "enum": [
                        "CNA_HPRD",
                        "RN_HPRD",
                        "LPN_HPRD",
                        "Total_Nurse_Aide_HPRD",
                        "Total_RN_HPRD",
                    ],
                    "default": "RN_HPRD",
                },
                "period": {
                    "type": "string",
                    "description": "Optional evidence period e.g. CY2026Q1 or 2026Q1",
                },
            },
            "required": ["ccn", "date"],
            "additionalProperties": False,
        },
    },
}


def list_tools() -> list[dict[str, Any]]:
    return [
        {"name": name, "description": meta["description"], "inputSchema": meta["inputSchema"]}
        for name, meta in TOOLS.items()
    ]


def call_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    if name not in TOOLS:
        return _err("unknown_tool", f"Unknown tool: {name}")
    args = arguments if isinstance(arguments, dict) else {}
    try:
        return TOOLS[name]["handler"](args)
    except Exception as exc:
        return _err("internal_error", str(exc))


def result_to_mcp_content(payload: dict[str, Any]) -> list[dict[str, Any]]:
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    return [{"type": "text", "text": text}]
