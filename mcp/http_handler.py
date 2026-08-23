"""Minimal MCP Streamable HTTP JSON-RPC handler for Flask (read-only tools)."""

from __future__ import annotations

import json
import os
import time
from typing import Any

from flask import Request, Response, jsonify

from mcp.rate_limit import mcp_rate_limit_exceeded
from mcp.tools_registry import call_tool, list_tools, result_to_mcp_content

SERVER_NAME = "PBJ320"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"


def _jsonrpc_result(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _jsonrpc_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _handle_initialize(params: dict[str, Any] | None) -> dict[str, Any]:
    _ = params
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        "instructions": (
            "PBJ320 public read-only research MCP. Responses include CMS source metadata. "
            "Use get_staffing_evidence for audit-ready daily PBJ provenance."
        ),
    }


def _handle_tools_list(_params: dict[str, Any] | None) -> dict[str, Any]:
    return {"tools": list_tools()}


def _handle_tools_call(params: dict[str, Any] | None) -> dict[str, Any]:
    params = params or {}
    name = str(params.get("name") or "")
    arguments = params.get("arguments")
    payload = call_tool(name, arguments if isinstance(arguments, dict) else {})
    return {"content": result_to_mcp_content(payload), "isError": not payload.get("ok", True)}


def dispatch_message(msg: dict[str, Any]) -> dict[str, Any]:
    req_id = msg.get("id")
    method = str(msg.get("method") or "")
    params = msg.get("params") if isinstance(msg.get("params"), dict) else {}

    if method == "initialize":
        return _jsonrpc_result(req_id, _handle_initialize(params))
    if method == "notifications/initialized":
        return _jsonrpc_result(req_id, {})
    if method == "tools/list":
        return _jsonrpc_result(req_id, _handle_tools_list(params))
    if method == "tools/call":
        return _jsonrpc_result(req_id, _handle_tools_call(params))
    if method == "ping":
        return _jsonrpc_result(req_id, {})

    return _jsonrpc_error(req_id, -32601, f"Method not found: {method}")


def handle_mcp_http(request: Request) -> Response:
    retry = mcp_rate_limit_exceeded()
    if retry is not None:
        resp = jsonify({"error": "rate_limit_exceeded"})
        resp.status_code = 429
        resp.headers["Retry-After"] = str(retry)
        return resp

    if request.method == "GET":
        body = {
            "service": SERVER_NAME,
            "transport": "streamable-http",
            "tools": [t["name"] for t in list_tools()],
            "endpoints": {"mcp": "/mcp"},
            "read_only": True,
        }
        return jsonify(body)

    if request.method != "POST":
        return Response("Method Not Allowed", status=405)

    try:
        payload = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify(_jsonrpc_error(None, -32700, "Parse error")), 400

    if isinstance(payload, list):
        out = [dispatch_message(m) for m in payload if isinstance(m, dict)]
        return jsonify(out)

    if not isinstance(payload, dict):
        return jsonify(_jsonrpc_error(None, -32600, "Invalid Request")), 400

    result = dispatch_message(payload)
    return jsonify(result)
