"""Thin HTTPX wrapper that executes a ToolSpec against a real FHIR REST API."""

from typing import Any

import httpx

from specmcp.generator import ToolSpec


def execute(base_url: str, tool: ToolSpec, params: dict[str, Any]) -> dict[str, Any]:
    remaining = dict(params)
    path = tool.path

    for p in tool.path_params:
        if p not in remaining:
            raise ValueError(f"missing path param '{p}' for tool '{tool.name}'")
        path = path.replace("{" + p + "}", str(remaining.pop(p)))

    body = None
    if tool.has_body:
        body = remaining.pop("resource", None)
        if body is None:
            raise ValueError(f"missing 'resource' body for tool '{tool.name}'")

    query = {q: remaining[q] for q in tool.query_params if q in remaining}

    url = f"{base_url.rstrip('/')}{path}"
    with httpx.Client(timeout=10.0) as client:
        response = client.request(tool.method, url, params=query, json=body)
    response.raise_for_status()
    return response.json() if response.content else {}
