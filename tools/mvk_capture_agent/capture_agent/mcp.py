"""Minimal local MCP JSON-RPC stdio transport; outputs no sensitive bytes in logs."""
from __future__ import annotations
import json
import sys
from .config import CaptureError
from .session import CaptureService
from . import __version__

TOOLS = [
    {"name": "mvk_capture_discover", "description": "Read-only discovery of original MVKView.exe windows.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "mvk_capture_start", "description": "Begin local read-only observation of MVKView; requires explicit operator acknowledgement.",
     "inputSchema": {"type": "object", "properties": {
         "acknowledge_local_capture": {"type": "boolean"},
         "config_path": {"type": "string"}, "pid": {"type": "integer", "minimum": 1}},
         "required": ["acknowledge_local_capture"], "additionalProperties": False}},
    {"name": "mvk_capture_snapshot", "description": "Read-only UI screenshot and optional allowlisted memory reads; no GUI actions.",
     "inputSchema": {"type": "object", "properties": {
         "include_memory": {"type": "boolean", "default": False}}, "additionalProperties": False}},
    {"name": "mvk_capture_status", "description": "Read local recording status and output folder.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "mvk_capture_stop", "description": "Stop observing the original application.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "mvk_capture_export", "description": "Export a stopped local session with SHA256 file manifest; never uploads.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "mvk_capture_import_debugger", "description": "Import existing operator-approved x32dbg JSONL/log file; does not control debugger.",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}},
                     "required": ["path"], "additionalProperties": False}},
]
BY_NAME = {t["name"]: t for t in TOOLS}


def result(rid, content):
    return {"jsonrpc": "2.0", "id": rid, "result": content}


def rpc_error(rid, code, message):
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": code, "message": message}}


def handle(service: CaptureService, message):
    if not isinstance(message, dict):
        return rpc_error(None, -32600, "Invalid request")
    if "id" not in message:
        return None
    rid = message["id"]
    method = message.get("method")
    if method == "initialize":
        return result(rid, {"protocolVersion": "2025-06-18",
                            "capabilities": {"tools": {"listChanged": False}},
                            "serverInfo": {"name": "mvk-capture-agent", "version": __version__},
                            "instructions": "Local user-consented, target-bound MVKView observation. No mouse clicks, no device commands, no debugger writes, no cloud upload."})
    if method == "ping":
        return result(rid, {})
    if method == "tools/list":
        return result(rid, {"tools": TOOLS})
    if method in ("resources/list", "prompts/list"):
        return result(rid, {"resources": []} if method == "resources/list" else {"prompts": []})
    if method != "tools/call":
        return rpc_error(rid, -32601, "Method not found")
    params = message.get("params") or {}
    if not isinstance(params, dict) or params.get("name") not in BY_NAME:
        return rpc_error(rid, -32602, "Unknown capture tool")
    name = params["name"]
    kwargs = params.get("arguments") or {}
    if not isinstance(kwargs, dict):
        return rpc_error(rid, -32602, "Arguments must be an object")
    schema = BY_NAME[name]["inputSchema"]
    if set(kwargs) - set(schema["properties"]) or not all(k in kwargs for k in schema.get("required", [])):
        return rpc_error(rid, -32602, "Unexpected or missing tool argument")
    try:
        if name == "mvk_capture_discover":
            payload = {"targets": service.discover()}
        elif name == "mvk_capture_start":
            payload = service.start(**kwargs)
        elif name == "mvk_capture_snapshot":
            payload = service.snapshot(**kwargs)
        elif name == "mvk_capture_status":
            payload = service.status()
        elif name == "mvk_capture_stop":
            payload = service.stop()
        elif name == "mvk_capture_export":
            payload = service.export()
        elif name == "mvk_capture_import_debugger":
            payload = service.import_debugger(kwargs["path"])
        else:
            return rpc_error(rid, -32601, "Tool not found")
    except (CaptureError, OSError, ValueError, TypeError) as exc:
        return result(rid, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
    return result(rid, {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, allow_nan=False)}],
                        "structuredContent": payload, "isError": False})


def serve(service=None, source=None, sink=None):
    service = service or CaptureService()
    source = source or sys.stdin
    sink = sink or sys.stdout
    for line in source:
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            reply = handle(service, data)
        except ValueError:
            reply = rpc_error(None, -32700, "Invalid JSON")
        except Exception as exc:
            print("MCP internal error: " + type(exc).__name__, file=sys.stderr, flush=True)
            reply = rpc_error(None, -32603, "Internal error")
        if reply is not None:
            sink.write(json.dumps(reply, ensure_ascii=False, separators=(",", ":")) + "\n")
            sink.flush()